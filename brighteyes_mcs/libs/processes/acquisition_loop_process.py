import multiprocessing as mp
import os
import threading
import time

import psutil
import numpy as np

# from ..is_parent_alive import CheckParentAlive
from ..h5manager import H5Manager
#import pprofile

try:
    from ..cython.fastconverter import (
        convertRawDataToCountsDirect,
        convertRawDataToCountsDirect49,
        convertDataFromAnalogFIFO,
    )
    from ..cython.autocorrelator import Autocorrelator
    from ..cython.timeBinner import timeBinner
except Exception as e:
    print(
        "\n\n"
        "====== ERROR =========================\n"
        "Cython modules not found!\n"
        "Are you sure they are compiled?\n"
        "Please run following command:\n\n"
        "python setup.py build_ext --inplace\n"
        "=====================================\n"
    )
    os._exit(1)

from ..print_dec import print_dec, set_debug
from numpy import sqrt


import numpy as np

def decode_pointer_list(pointer_start, gap, timebinsPerPixel, shape, snake_walk_xy=False, snake_walk_z=False, clk_multiplier=1):
    """
    Decode pointer indices into list_b, list_x, list_y, list_z, list_rep.

    Parameters
    ----------
    pointer_start : int
        Starting pointer index.
    gap : int
        Number of elements to decode.
    timebinsPerPixel : int
        Number of time bins per pixel.
    shape : tuple
        (X, Y, Z) dimensions.
    snake_walk_xy : bool
        Whether to apply XY snake walk.
    snake_walk_z : bool
        Whether to apply Z snake walk.

    Returns
    -------
    tuple of np.ndarray
        (list_b, list_x, list_y, list_z, list_rep)
    """

    list_pointer = np.arange(pointer_start, pointer_start + gap)
    list_pixel = list_pointer // timebinsPerPixel
    list_b = list_pointer % timebinsPerPixel
    if clk_multiplier != 1:
        list_b = list_b % (timebinsPerPixel // clk_multiplier)
    list_x = list_pixel % shape[0]
    list_y = (list_pixel // shape[0]) % shape[1]

    if snake_walk_xy:
        list_x = list_x + (list_y % 2) * (-2 * list_x + shape[0] - 1)

    list_z = list_pixel // (shape[0] * shape[1])
    list_rep = list_z // shape[2]

    if snake_walk_z:
        list_z = (list_z + (list_rep % 2) * (-2 * list_z + shape[2] - 1)) % shape[2]
    else:
        list_z = list_z % shape[2]

    return list_b, list_x, list_y, list_z, list_rep


class AcquisitionLoopProcess(mp.Process):
    def __init__(
        self,
        channels,
        shared_objects,
        do_not_save,
        data_queue,
        acquisition_done,
        acquisition_almost_done,
        shared_dict,
        debug=False,
    ):
        set_debug(debug)
        print_dec("AcquisitionLoopProcess INIT")

        self.DATA_WORDS_ANALOG = 2
        if channels == 25:
            print_dec("Found 25 channels -> DATA_WORDS_DIGITAL = 2")
            self.channels = 25
            self.DATA_WORDS_DIGITAL = 2
        elif channels == 49:
            print_dec("Found 49 channels -> DATA_WORDS_DIGITAL = 8")
            self.channels = 49
            self.DATA_WORDS_DIGITAL = 8
        else:
            print_dec("Found NOT STANDARD NUMBER OF CHANNELS FALLBACK TO DATA_WORDS_DIGITAL = 2")
            self.channels = 25
            self.DATA_WORDS_DIGITAL = 2

        self.shm_activated_fifos_list = shared_objects["activated_fifos_list"]
        self.activated_fifos_list = list(self.shm_activated_fifos_list) #To avoid extra shm call

        self.shm_autocorrelation = shared_objects["shared_autocorrelation"]
        self.shm_loc_acquired = shared_objects["loc_acquired"]
        self.shm_loc_previewed = shared_objects["loc_previewed"]

        self.current_frame = {"FIFO": 0, "FIFOAnalog": 0}

        self.shm_image_xy_rgb = shared_objects["shared_image_xy_rgb"]
        self.shm_image_xy = shared_objects["shared_image_xy"]
        self.shm_image_xz = shared_objects["shared_image_xz"]
        self.shm_image_zy = shared_objects["shared_image_zy"]

        self.shm_fingerprint = shared_objects["shared_fingerprint"]
        self.shm_fingerprint_mask = shared_objects["shared_fingerprint_mask"]

        self.shm_trace = shared_objects["shared_trace"]
        self.shm_number_of_threads_h5 = shared_objects["number_of_threads_h5"]

        self.autocorrelation_maxx = shared_objects["autocorrelation_maxx"]
        self.trace_bins = shared_objects["trace_bins"]
        self.trace_sample_per_bins = shared_objects["trace_sample_per_bins"]
        self.trace_pos = shared_objects["trace_pos"]

        self.timebinsPerPixel = shared_dict["timebins_per_pixel"] * \
                                shared_dict["circ_repetition"] * \
                                shared_dict["circ_points"]

        self.time_resolution = shared_dict["time_resolution"]
        self.expected_raw_data = shared_dict["expected_raw_data"]
        self.expected_raw_data_per_frame = shared_dict["expected_raw_data_per_frame"]

        self.DFD_Activate = shared_dict["DFD_Activate"]
        self.DFD_nbins = shared_dict["DFD_nbins"]

        self.redirect_intensity_to_fifoanalog = bool(shared_dict["Redirect_intensity_to_FIFOAnalog"])
        print_dec("Redirect_intensity_to_FIFOAnalog", type(self.redirect_intensity_to_fifoanalog))

        self.snake_walk_xy = shared_dict["snake_walk_xy"]
        self.snake_walk_z = shared_dict["snake_walk_z"]

        self.clk_multiplier = shared_dict["clk_multiplier"]
        self.dfd_shift = shared_dict["dfd_shift"]

        self.filenameh5 = shared_dict["filenameh5"]

        self.acquisition_done = acquisition_done
        self.acquisition_done.clear()

        self.acquisition_almost_done = acquisition_almost_done
        self.acquisition_almost_done.clear()

        self.shared_dict = shared_dict

        self.shape = shared_dict["shape"]
        self.channels = shared_dict["channels"]
        self.channels_extra = 2

        self.current_pointer = {"FIFO": 0, "FIFOAnalog": 0}
        
        self.stop_events_init(self.activated_fifos_list)

        # self.stop_event = {"FIFO": mp.Event(),
        #                    "FIFOAnalog": mp.Event()
        #                    }
        # self.stop_event = mp.Event()

        self.trace_reset_event = mp.Event()
        self.FCS_reset_event = mp.Event()

        self.buffer_size_in_words = shared_dict["preview_buffer_size_in_words"]  # 15000
        self.buffer_size_in_words_analog = self.buffer_size_in_words

        self.buffer_data = {}
        self.buffer_data_sum = {}
        self.saturation = {}

        self.buffer_data_size = {"FIFO": self.timebinsPerPixel * self.buffer_size_in_words * self.DATA_WORDS_DIGITAL,
                                 "FIFOAnalog": self.timebinsPerPixel * self.buffer_size_in_words_analog * self.DATA_WORDS_ANALOG}

        if self.channels == 25:
            self.buffer_data["FIFO"] = np.zeros((self.buffer_data_size["FIFO"], 25 + 2), dtype=np.uint64)
            self.saturation["FIFO"] = np.zeros(25 + 2, dtype=np.uint64)
            self.buffer_data_sum["FIFO"] = np.zeros(self.buffer_data_size["FIFO"], dtype=np.uint64)

        if self.channels == 49:
            self.buffer_data["FIFO"] = np.zeros((self.buffer_data_size["FIFO"], 49 + 2), dtype=np.uint64)
            self.saturation["FIFO"] = np.zeros(49 + 2, dtype=np.uint64)
            self.buffer_data_sum["FIFO"] = np.zeros(self.buffer_data_size["FIFO"], dtype=np.uint64)

        self.buffer_data["FIFOAnalog"] = np.zeros((self.buffer_data_size["FIFOAnalog"], 2), dtype=np.int32)

        self.total_photon = {"channels": 0}

        self.data_queue = data_queue

        self.do_not_save = do_not_save

        self.buffer_for_save = {"channels": None, "channels_extra": None, "channels_analog": None}

        self.channels_analog = 2

        super().__init__()
        print_dec("AcquisitionLoopProcess INIT DONE")

    def stop_events_init(self, list_fifos=None):
        self.stop_event = {}

        if list_fifos is None:
            list_fifos = ["FIFO", "FIFOAnalog"]

        for s in list_fifos:
            self.stop_event[s] = mp.Event()
        print_dec("stop_event initialized", str(self.stop_event))

    def stop_events_clear(self, list_fifos="all"):
        if list_fifos == "all":
            list_fifos = self.stop_event.keys()
        for s in list_fifos:
            self.stop_event[s].clear()

    def stop_events_set(self, list_fifos="all"):
        if list_fifos == "all":
            list_fifos = self.stop_event.keys()
        for s in list_fifos:
            self.stop_event[s].set()

    def stop_events_is_set_and(self, list_fifos="all"):
        if list_fifos == "all":
            list_fifos = self.stop_event.keys()

        ret = True

        for s in list_fifos:
            ret = ret and self.stop_event[s].is_set()
        return ret

    def stop_events_is_set_or(self, list_fifos="all"):
        if list_fifos == "all":
            list_fifos = self.stop_event.keys()

        ret = False

        for s in list_fifos:
            ret = ret or self.stop_event[s].is_set()
        return ret

    def stop_events_status(self, list_fifos="all"):
        if list_fifos == "all":
            list_fifos = self.stop_event.keys()

        ret ={}

        for s in list_fifos:
            ret[s] = self.stop_event[s].is_set()
        return ret

    def run(self):
        # self.profiler = pprofile.StatisticalProfile()
        # with self.profiler():
        print_dec(
            "AcquisitionLoopProcess RUN - PID:",
            os.getpid(),
            "    <======================================================",
        )

        self.activated_fifos_list = list(self.shm_activated_fifos_list) #To avoid extra shm call

        self.stop_events_clear()

        self.current_pointer["FIFO"] = 0  # self.timebinsPerPixel * self.DATA_WORDS_DIGITAL
        self.current_pointer["FIFOAnalog"] = 0  # self.timebinsPerPixel * self.DATA_WORDS_ANALOG

        self.current_frame["FIFO"] = 0
        self.current_frame["FIFOAnalog"] = 0

        print_dec(str(self.stop_events_status()))

        self.image_xy_rgb = self.shm_image_xy_rgb.get_numpy_handle()
        self.image_xy = self.shm_image_xy.get_numpy_handle()
        self.image_xz = self.shm_image_xz.get_numpy_handle()
        self.image_zy = self.shm_image_zy.get_numpy_handle()
        # self.data = self.shm_data.get_numpy_handle()
        self.fingerprint = self.shm_fingerprint.get_numpy_handle()
        self.autocorrelation = self.shm_autocorrelation.get_numpy_handle()
        self.trace = self.shm_trace.get_numpy_handle()

        self.fingerprint_mask = self.shm_fingerprint_mask.get_numpy_handle()

        self.image_xy_rgb_lock = self.shm_image_xy_rgb.get_lock()
        self.image_xy_lock = self.shm_image_xy.get_lock()
        self.image_xz_lock = self.shm_image_xz.get_lock()
        self.image_zy_lock = self.shm_image_zy.get_lock()
        # self.data_lock = self.shm_data.get_lock()
        self.fingerprint_lock = self.shm_fingerprint.get_lock()
        self.autocorrelation_lock = self.shm_autocorrelation.get_lock()
        self.trace_lock = self.shm_trace.get_lock()

        self.fingerprint_mask_lock = self.shm_fingerprint_mask.get_lock()

        self.activate_show_preview = self.shared_dict["activate_show_preview"]
        self.active_autocorrelation = self.shared_dict["activate_autocorrelation"]
        self.activate_trace = self.shared_dict["activate_trace"]

        selected_channel = self.shared_dict["channel"]
        correlator = Autocorrelator(maxx=self.autocorrelation_maxx, log_step=2)
        temporalBinner = timeBinner(
            bins=self.trace_bins, sample_per_bins=self.trace_sample_per_bins
        )

        if not self.do_not_save:
            self.init_h5_and_buffer_for_save_data()

        self.total_photon["channels"] = 0

        self.shared_dict.update(
            {
                "current_z": {},
                "current_rep": {},
                "total_photon": 0,
            }
        )

        self.fingerprint[0, :, :] = 0
        self.fingerprint[1, :, :] = 0
        self.fingerprint[2, :, :] = 0
        # self.fingerprint[3, :, :] = 0
        self.fingerprint[4, :, :] = 0

        self.autocorrelation[0, :] = correlator.get_delays() * self.time_resolution
        print_dec("correlator:", correlator.get_delays(), self.time_resolution)
        self.autocorrelation[1, :] = 0

        self.trace[0, :] = temporalBinner.get_x()
        self.trace[1, :] = 0

        self.gap = {"FIFO": 0, "FIFOAnalog": 0}

        # create a dictionary for the frameComplete={"FIFO": False, "FIFOAnalog": False})
        frameComplete = dict((name, False) for name in self.activated_fifos_list)

        internal_buffer = (
            None  # This buffer is used only when the data cross two frames
        )
        internal_buffer_analog = (
            None  # This buffer is used only when the data cross two frames
        )

        print_dec(self.expected_raw_data_per_frame, self.expected_raw_data)
        print_dec("activated_fifos_list", self.activated_fifos_list)
        print_dec("self.activate_show_preview", self.activate_show_preview)

        # self.data_queue["FIFO"] = self.data_queue["FIFO"]
        # self.shm_loc_acquired["FIFO"] = self.shm_loc_acquired["FIFO"]

        self.shared_dict_proxy = {}

        self.shared_dict_proxy["current_z"] = {}
        self.shared_dict_proxy["current_rep"] = {}

        self.update_dictionary_slowly(0.1)

        #This seams redundant but it is for optimize the performances
        channels = self.channels
        channels_y = int(sqrt(self.channels))
        channels_x = channels_y
        print("Channels ", channels, channels_x, channels_y)

        if channels == 25:
            converter = convertRawDataToCountsDirect
        elif channels == 49:
            converter = convertRawDataToCountsDirect49
        else:
            print_dec("Wrong number of channel. Data conversion fo Forced to 25 Channels")
            converter = convertRawDataToCountsDirect

        clk_multiplier = self.clk_multiplier
        # print_dec("=================================================================")
        # print_dec("timebinsPerPixel", self.timebinsPerPixel)
        # print_dec("time_resolution", self.time_resolution)
        # print_dec("expected_raw_data", self.expected_raw_data)
        # print_dec("expected_raw_data_per_frame", self.expected_raw_data_per_frame)
        # print_dec("DFD_Activate", self.DFD_Activate)
        # print_dec("DFD_nbins", self.DFD_nbins)
        # print_dec("shared_dict", self.shared_dict)
        # print_dec("shape", self.shape)
        # print_dec("channels", self.channels)
        # print_dec("channels_extra", self.channels_extra)
        # print_dec("current_pointer", self.current_pointer["FIFO"])
        # print_dec("current_pointer_analog", self.current_pointer["FIFOAnalog"])
        # print_dec("buffer_size_in_words", self.buffer_size_in_words)
        # print_dec("buffer_size_in_words_analog", self.buffer_size_in_words_analog)
        # print_dec("buffer_size", self.buffer_data_size["FIFO"])
        # print_dec("buffer_size_analog", self.buffer_data_size["FIFOAnalog"])
        # print_dec("=================================================================")

        print_dec("SHAPE before while", self.shape )
        while not self.stop_events_is_set_and(self.activated_fifos_list):
            selected_channel = self.shared_dict["channel"]

            if self.do_not_save:
                self.shm_number_of_threads_h5.value = -1

            self.shared_dict_proxy["FIFO_status"] = self.data_queue["FIFO"].qsize()
            self.shared_dict_proxy["FIFOAnalog_status"] = self.data_queue["FIFOAnalog"].qsize()

            if "FIFO" in self.activated_fifos_list:
                self.process_FIFO_Digital(channels, channels_x, channels_y, clk_multiplier, converter, correlator,
                                          frameComplete, internal_buffer, selected_channel, temporalBinner)

            if self.redirect_intensity_to_fifoanalog:
                self.process_FIFO_Digital(channels, channels_x, channels_y, clk_multiplier, converter, correlator,
                                          frameComplete, internal_buffer, selected_channel, temporalBinner)
            else:
                if "FIFOAnalog" in self.activated_fifos_list:
                    self.process_FIFO_Analog(correlator, frameComplete, internal_buffer_analog, selected_channel,
                                             temporalBinner)

            if self.trace_reset_event.is_set():
                print_dec("trace_reset_event.is_set()")
                temporalBinner.reset()
                self.trace_reset_event.clear()
            if self.FCS_reset_event.is_set():
                correlator.reset()
                self.FCS_reset_event.clear()

        self.stop_update_dictionary_slowly()

        self.acquisition_almost_done.set()

        if not self.do_not_save:
            self.h5mgr.close()
        self.acquisition_done.set()
        print_dec("Acquisition done")
        self.stop_events_clear()

        print_dec("run() acquisition_loop_process stopped")

    def process_FIFO_Analog(self, correlator, frameComplete, internal_buffer_analog, selected_channel, temporalBinner):
        max_gap_frame_analog = self.expected_raw_data_per_frame * (
                self.current_frame["FIFOAnalog"] + 1

        )
        if not self.data_queue["FIFOAnalog"].empty():
            if (
                    internal_buffer_analog is not None
            ):  # if the previous queue data was between two frames

                data_from_queue_analog = internal_buffer_analog[
                                         : max_gap_frame_analog - self.current_pointer["FIFOAnalog"]
                                         ]
                self.gap["FIFOAnalog"] = data_from_queue_analog.shape[0] // 2
                internal_buffer_analog = internal_buffer_analog[
                                         max_gap_frame_analog - self.current_pointer["FIFOAnalog"]:
                                         ]

            else:  # standard case (no previous split data)
                data_from_queue_analog = self.data_queue["FIFOAnalog"].get()
                self.gap["FIFOAnalog"] = data_from_queue_analog.shape[0]
                # in the case the current queue data overflow in the next frame the data are split

                if (
                        self.current_pointer["FIFOAnalog"] + self.gap["FIFOAnalog"]
                ) * 2 >= max_gap_frame_analog:
                    print_dec(
                        " c ",
                        (self.current_pointer["FIFOAnalog"] + self.gap["FIFOAnalog"]),
                        max_gap_frame_analog,
                    )

                    internal_buffer_analog = data_from_queue_analog[
                                             max_gap_frame_analog - self.current_pointer["FIFOAnalog"]:
                                             ]
                    self.gap["FIFOAnalog"] = data_from_queue_analog.shape[0]
                    data_from_queue_analog = data_from_queue_analog[
                                             : max_gap_frame_analog - self.current_pointer["FIFOAnalog"]
                                             ]

                    frameComplete["FIFOAnalog"] = True

                    self.current_frame["FIFOAnalog"] += 1

            if internal_buffer_analog is not None:
                if internal_buffer_analog.size == 0:
                    print_dec("internal_buffer_analog.size == 0")
                    internal_buffer_analog = None

            if (
                    self.expected_raw_data
                    - (self.current_pointer["FIFOAnalog"] + self.gap["FIFOAnalog"])
                    < 0
            ):
                self.gap["FIFOAnalog"] = (
                        self.expected_raw_data // 2 - self.current_pointer["FIFOAnalog"]
                )
                print_dec("MISTERY")
                print_dec("New GAP", self.gap["FIFOAnalog"])

            list_b_analog, list_x_analog, list_y_analog, list_z_analog, list_rep_analog = decode_pointer_list(
                self.current_pointer["FIFOAnalog"],
                self.gap["FIFOAnalog"],
                self.timebinsPerPixel,
                self.shape,
                snake_walk_xy=self.snake_walk_xy,
                snake_walk_z=self.snake_walk_z
            )

            self.shared_dict_proxy["last_packet_size"] = self.gap["FIFOAnalog"]
            if self.gap["FIFOAnalog"] > self.buffer_data_size["FIFOAnalog"]:
                print_dec(
                    "Too many data larger than the buffer. GAP",
                    self.gap["FIFOAnalog"],
                    "buffer_size_analog",
                    self.buffer_data_size["FIFOAnalog"],
                )
            if (
                    convertDataFromAnalogFIFO(
                        data_from_queue_analog,
                        0,
                        self.gap["FIFOAnalog"],
                        self.buffer_data["FIFOAnalog"],
                        force_positive=0,
                    )
                    == -1
            ):
                print_dec(
                    "==============DISASTER IN THE PREVIEW====================="
                )

            buffer_up_to_gap = self.buffer_data["FIFOAnalog"][: self.gap["FIFOAnalog"]]

            self.generate_preview(
                buffer_up_to_gap,
                correlator,
                list_x_analog,
                list_y_analog,
                list_z_analog,
                selected_channel,  # e.g. "Analog A"
                temporalBinner,
                data_fmt="Analog"
            )

            if not self.do_not_save:
                self.buffer_for_save["channels_analog"][
                list_y_analog, list_x_analog, list_b_analog, :
                ] = buffer_up_to_gap

            self.current_pointer["FIFOAnalog"] += self.gap["FIFOAnalog"]
            self.shm_loc_previewed[
                "FIFOAnalog"
            ].value = self.current_pointer["FIFOAnalog"]

            self.shared_dict_proxy.update({"total_photon": self.total_photon["channels"]})
            # print_dec("frameComplete", frameComplete)
            if frameComplete["FIFOAnalog"]:
                print_dec("frameComplete[FIFOAnalog]")
                frameComplete["FIFOAnalog"] = False
                self.fingerprint[3, :, :] = self.fingerprint[0, :, :]
                self.fingerprint[0, :, :] = 0
                self.fingerprint[1, :, :] = 0
                self.fingerprint[2, :, :] = 0
                self.fingerprint[4, :, :] = 0

                current_z = self.shared_dict_proxy["current_z"]
                current_rep = self.shared_dict_proxy["current_rep"]

                current_z["FIFOAnalog"] = (self.current_frame["FIFOAnalog"] - 1) % self.shape[2]
                current_rep["FIFOAnalog"] = (self.current_frame["FIFOAnalog"] - 1) // self.shape[2]
                print_dec("FRAME [FIFOAnalog] ", current_z, current_rep, " DONE")

                self.shared_dict_proxy.update(
                    {
                        "current_z": current_z,
                        "current_rep": current_rep,
                        "total_photon": self.total_photon["channels"],
                        "last_packet_size": self.gap["FIFOAnalog"]
                    }
                )
                if not self.do_not_save:
                    self.h5mgr.add_to_dataset(
                        "data_analog",
                        np.copy(self.buffer_for_save["channels_analog"]),
                        current_rep["FIFOAnalog"],
                        current_z["FIFOAnalog"],
                    )
                    self.buffer_for_save["channels_analog"][:] = 0
                    print_dec("done analog add_to_dataset")
                    print_dec(
                        self.current_pointer["FIFOAnalog"] * self.DATA_WORDS_ANALOG, self.expected_raw_data
                    )

            if self.current_pointer["FIFOAnalog"] * self.DATA_WORDS_ANALOG >= self.expected_raw_data:
                self.stop_event["FIFOAnalog"].set()

    def process_FIFO_Digital(self, channels, channels_x, channels_y, clk_multiplier, converter, correlator,
                             frameComplete, internal_buffer, selected_channel, temporalBinner, FIFO="FIFO"):
        max_gap_frame = self.expected_raw_data_per_frame * (
                self.current_frame["FIFO"] + 1
        )
        # if (internal_buffer is not None): print_dec(len(internal_buffer))
        #
        # print(max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL),
        #     max_gap_frame,
        #     (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL),
        # )
        data_from_queue = None
        if not self.data_queue[FIFO].empty():
            if (
                    internal_buffer is not None
            ):  # if the previous queue data was between two frames
                print_dec(
                    len(internal_buffer),
                    max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL),
                    max_gap_frame,
                    (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL),
                )
                if max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL) == 0:
                    self.gap["FIFO"] = 0
                    internal_buffer = None
                else:
                    data_from_queue = internal_buffer[
                                      : max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL)
                                      ]
                    self.gap["FIFO"] = data_from_queue.shape[0] // self.DATA_WORDS_DIGITAL
                    internal_buffer = internal_buffer[
                                      max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL):
                                      ]

            if (
                    internal_buffer is None
            ):  # standard case (no previous split data)
                data_from_queue = self.data_queue[FIFO].get()
                self.gap["FIFO"] = data_from_queue.shape[0] // self.DATA_WORDS_DIGITAL
                #
                # print_dec(
                #     None,
                #     len(data_from_queue),
                #     (self.current_pointer["FIFO"] + self.gap["FIFO"]) * self.DATA_WORDS_DIGITAL - max_gap_frame,
                # )
                if (self.current_pointer["FIFO"] + self.gap["FIFO"]) * self.DATA_WORDS_DIGITAL >= max_gap_frame:
                    print_dec(
                        " c ",
                        (self.current_pointer["FIFO"] + self.gap["FIFO"]) * self.DATA_WORDS_DIGITAL,
                        self.gap["FIFO"],
                        max_gap_frame,
                    )
                    print_dec(
                        data_from_queue.shape,
                        max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL),
                    )

                    internal_buffer = data_from_queue[
                                      max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL):
                                      ]
                    data_from_queue = data_from_queue[
                                      : max_gap_frame - (self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL)
                                      ]
                    self.gap["FIFO"] = data_from_queue.shape[0] // self.DATA_WORDS_DIGITAL

                    frameComplete[FIFO] = True

                    self.current_frame["FIFO"] += 1

            if internal_buffer is not None:
                if internal_buffer.size == 0:
                    print_dec("internal_buffer.size == 0")
                    internal_buffer = None

            if self.expected_raw_data < (self.current_pointer["FIFO"] + self.gap["FIFO"]) * self.DATA_WORDS_DIGITAL:
                self.gap["FIFO"] = max_gap_frame // self.DATA_WORDS_DIGITAL - self.current_pointer["FIFO"]
                print_dec("MISTERY!!!")
                print_dec("New GAP", self.gap["FIFO"])

            #
            # Generation of list_pixel, list_b, list_x, list_y, list_z
            #

            list_b, list_x, list_y, list_z, list_rep = decode_pointer_list(
                self.current_pointer["FIFO"],
                self.gap["FIFO"],
                self.timebinsPerPixel,
                self.shape,
                snake_walk_xy=self.snake_walk_xy,
                snake_walk_z=self.snake_walk_z,
                clk_multiplier=clk_multiplier
            )

            if self.gap["FIFO"] > self.buffer_data_size["FIFO"]:
                print_dec(
                    "ERROR: Too many data larger than the buffer. GAP",
                    self.gap["FIFO"],
                    "buffer_size",
                    self.buffer_data_size["FIFO"],
                )

            self.saturation["FIFO"][:] = 0

            # print_dec("self.gap["FIFO"]", self.gap["FIFO"] )
            if data_from_queue is not None:
                if (
                        converter(
                            data_from_queue,
                            0,
                            self.gap["FIFO"] * self.DATA_WORDS_DIGITAL,
                            self.buffer_data["FIFO"],
                            self.buffer_data_sum["FIFO"],
                            self.saturation["FIFO"],
                            self.fingerprint_mask,
                        )
                        == -1
                ):
                    print_dec(
                        "==============DISASTER IN THE PREVIEW====================="
                    )


            buffer_up_to_gap = self.buffer_data["FIFO"][: self.gap["FIFO"]]

            self.generate_preview(
                buffer_up_to_gap,
                correlator,
                list_x,
                list_y,
                list_z,
                selected_channel,  # int, "Sum", "RGB ..."
                temporalBinner,
                channels=channels,
                list_b=list_b,
                data_fmt="Digital"
            )

            if not self.do_not_save:
                # This is for debug purpose

                np.add.at(
                    self.buffer_for_save["channels"],
                    (list_y, list_x, list_b),
                    buffer_up_to_gap[:, :channels],
                )

                np.add.at(
                    self.buffer_for_save["channels_extra"],
                    (list_y, list_x, list_b),
                    buffer_up_to_gap[:, channels:],
                )

            sum_tmp = buffer_up_to_gap[:, :channels].sum(axis=0).reshape(channels_x, channels_y)

            self.total_photon["channels"] = np.sum(sum_tmp)

            self.fingerprint[0, :, :] += sum_tmp
            try:
                self.fingerprint[1, :, :] = buffer_up_to_gap[-1, :channels].reshape(
                    channels_x, channels_y
                )
            except:
                print_dec("buffer_up_to_gap", buffer_up_to_gap)
                self.fingerprint[1, :, :] = 0

            if self.gap["FIFO"] > 10000:
                self.fingerprint[2, :, :] = (
                    self.buffer_data["FIFO"][:10000, :channels].sum(axis=0).reshape(channels_x, channels_y)
                )

            self.fingerprint[4, :, :] += self.saturation["FIFO"][:channels].reshape(channels_x, channels_y)
            self.current_pointer["FIFO"] += self.gap["FIFO"]
            self.shm_loc_previewed["FIFO"].value = self.current_pointer["FIFO"]
            # print_dec(self.current_pointer["FIFO"]*2, self.gap["FIFO"]*2, (self.current_pointer["FIFO"] + self.gap["FIFO"])*2)

            if frameComplete["FIFO"]:
                print_dec("frameComplete[FIFO]")
                frameComplete["FIFO"] = False
                self.fingerprint[3, :, :] = self.fingerprint[0, :, :]
                self.fingerprint[0, :, :] = 0
                self.fingerprint[1, :, :] = 0
                self.fingerprint[2, :, :] = 0
                self.fingerprint[4, :, :] = 0

                current_z = self.shared_dict_proxy["current_z"]
                current_rep = self.shared_dict_proxy["current_rep"]

                current_z["FIFO"] = (self.current_frame["FIFO"] - 1) % self.shape[2]
                current_rep["FIFO"] = (self.current_frame["FIFO"] - 1) // self.shape[2]

                print_dec("FRAME [FIFO] ", current_z, current_rep, " DONE")

                self.shared_dict_proxy.update(
                    {
                        "current_z": current_z,
                        "current_rep": current_rep,
                        "total_photon": self.total_photon["channels"],
                        "last_packet_size": self.gap["FIFO"],
                    }
                )

                if not self.do_not_save:
                    self.h5mgr.add_to_dataset(
                        "data",
                        np.copy(self.buffer_for_save["channels"]),
                        current_rep["FIFO"],
                        current_z["FIFO"],
                    )
                    self.h5mgr.add_to_dataset(
                        "data_channels_extra",
                        np.copy(self.buffer_for_save["channels_extra"]),
                        current_rep["FIFO"],
                        current_z["FIFO"],
                    )
                    self.buffer_for_save["channels"][:] = 0
                    self.buffer_for_save["channels_extra"][:] = 0
                    print_dec("done digital add_to_dataset")
                    print_dec(self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL)

            if self.current_pointer["FIFO"] * self.DATA_WORDS_DIGITAL >= self.expected_raw_data:
                self.stop_event["FIFO"].set()

    def update_views(self, data, list_x, list_y, list_z):
        """Helper to update XY, ZY, XZ projections given data and coords."""
        # XY
        self.image_xy_lock.acquire()
        self.image_xy[list_y, list_x] = 0
        np.add.at(self.image_xy, (list_y, list_x), data)
        self.image_xy_lock.release()

        # ZY (X = center)
        cond_x_central = list_x == (self.shape[0] // 2)
        self.image_zy_lock.acquire()
        self.image_zy[list_y[cond_x_central], list_z[cond_x_central]] = 0
        np.add.at(
            self.image_zy,
            (list_y[cond_x_central], list_z[cond_x_central]),
            data[cond_x_central],
        )
        self.image_zy_lock.release()

        # XZ (Y = center)
        cond_y_central = list_y == (self.shape[1] // 2)
        self.image_xz_lock.acquire()
        self.image_xz[list_z[cond_y_central], list_x[cond_y_central]] = 0
        np.add.at(
            self.image_xz,
            (list_z[cond_y_central], list_x[cond_y_central]),
            data[cond_y_central],
        )
        self.image_xz_lock.release()


    def generate_preview(
            self,
            buffer_up_to_gap,
            correlator,
            list_x,
            list_y,
            list_z,
            selected_channel,
            temporalBinner,
            channels=None,
            list_b=None,
            data_fmt="Digital"
    ):
        """
        Unified preview generator for both Analog and Digital data.
        """

        # ------------------- ANALOG -------------------
        if isinstance(selected_channel, str) and "Analog" in selected_channel and data_fmt == "Analog":
            analog_ch = 0 if selected_channel.endswith("A") else 1
            data = buffer_up_to_gap[:, analog_ch]

            if self.activate_show_preview:
                self.update_views(data, list_x, list_y, list_z)

            if self.active_autocorrelation:
                correlator.add(data)
                self.autocorrelation[1, :] = correlator.get_correlation_normalized()
            if self.activate_trace:
                temporalBinner.add(data)
                self.trace_pos.value = temporalBinner.get_current_position_bins()
                self.trace[1, :] = temporalBinner.get_bins()

        # ------------------- DIGITAL -------------------
        elif isinstance(selected_channel, int) and channels is not None and data_fmt == "Digital":
            if selected_channel < (channels + 2):
                data = buffer_up_to_gap[:, selected_channel]

                if self.activate_show_preview:
                    self.update_views(data, list_x, list_y, list_z)

                if self.active_autocorrelation:
                    correlator.add(data)
                    self.autocorrelation[1, :] = correlator.get_correlation_normalized()
                if self.activate_trace:
                    temporalBinner.add(data)
                    self.trace_pos.value = temporalBinner.get_current_position_bins()
                    self.trace[1, :] = temporalBinner.get_bins()

        # ------------------- SUM -------------------
        elif isinstance(selected_channel, str) and selected_channel.startswith("Sum") and data_fmt == "Digital":
            data = self.buffer_data_sum["FIFO"][: self.gap["FIFO"]]

            if self.activate_show_preview:
                self.update_views(data, list_x, list_y, list_z)

            if self.active_autocorrelation:
                correlator.add(data)
                self.autocorrelation[1, :] = correlator.get_correlation_normalized()
            if self.activate_trace:
                temporalBinner.add(data)
                self.trace_pos.value = temporalBinner.get_current_position_bins()
                self.trace[1, :] = temporalBinner.get_bins()

        # ------------------- RGB / RGB2 / RGB3 / RGBDFD -------------------
        elif isinstance(selected_channel, str) and selected_channel.startswith("RGB") and data_fmt == "Digital":
            self.image_xy_rgb_lock.acquire()
            self.image_xy_rgb[list_y, list_x, :] = 0

            if selected_channel.startswith("RGB "):
                chA, chB, chC = map(int, selected_channel.split(" ")[1:4])
                np.add.at(self.image_xy_rgb[:, :, 0], (list_y, list_x), buffer_up_to_gap[:, chA])
                np.add.at(self.image_xy_rgb[:, :, 1], (list_y, list_x), buffer_up_to_gap[:, chB])
                np.add.at(self.image_xy_rgb[:, :, 2], (list_y, list_x), buffer_up_to_gap[:, chC])

            elif selected_channel.startswith("RGB2") or selected_channel.startswith("RGB3"):
                if self.buffer_data_sum["FIFO"].shape[0] > 2:
                    np.add.at(self.image_xy_rgb[:, :, 0], (list_y[::3], list_x[::3]),
                              self.buffer_data_sum["FIFO"][: self.gap["FIFO"]:3])
                    np.add.at(self.image_xy_rgb[:, :, 1], (list_y[1::3], list_x[1::3]),
                              self.buffer_data_sum["FIFO"][1:self.gap["FIFO"]:3])
                    np.add.at(self.image_xy_rgb[:, :, 2], (list_y[2::3], list_x[2::3]),
                              self.buffer_data_sum["FIFO"][2:self.gap["FIFO"]:3])

            elif selected_channel.startswith("RGBDFD") and list_b is not None:
                tparts = 3
                tbins = self.timebinsPerPixel
                gbins = tbins // tparts
                if self.buffer_data_sum["FIFO"].shape[0] > 2:
                    cond0 = list_b < gbins
                    np.add.at(self.image_xy_rgb[:, :, 0], (list_y[cond0], list_x[cond0]),
                              self.buffer_data_sum["FIFO"][: self.gap["FIFO"]][cond0])
                    cond0 = (list_b >= gbins) & (list_b < 2 * gbins)
                    np.add.at(self.image_xy_rgb[:, :, 1], (list_y[cond0], list_x[cond0]),
                              self.buffer_data_sum["FIFO"][: self.gap["FIFO"]][cond0])
                    cond0 = list_b >= 2 * gbins
                    np.add.at(self.image_xy_rgb[:, :, 2], (list_y[cond0], list_x[cond0]),
                              self.buffer_data_sum["FIFO"][: self.gap["FIFO"]][cond0])

            self.image_xy_rgb_lock.release()

            if self.active_autocorrelation:
                correlator.add(self.buffer_data_sum["FIFO"][: self.gap["FIFO"]])
                self.autocorrelation[1, :] = correlator.get_correlation_normalized()
            if self.activate_trace:
                temporalBinner.add(self.buffer_data_sum["FIFO"][: self.gap["FIFO"]])
                self.trace_pos.value = temporalBinner.get_current_position_bins()
                self.trace[1, :] = temporalBinner.get_bins()

    def init_h5_and_buffer_for_save_data(self):
        self.h5mgr = H5Manager(
            self.filenameh5, shm_number_of_threads_h5=self.shm_number_of_threads_h5
        )
        # self.h5file = h5py.File(self.filenameh5, "w")
        print_dec("Filename:", self.filenameh5)
        if not self.redirect_intensity_to_fifoanalog:
            if "FIFO" in self.activated_fifos_list:

                self.h5mgr.init_dataset(
                    "data",
                    self.shape,
                    self.timebinsPerPixel // self.clk_multiplier,
                    self.channels,
                    np.uint16
                )

                self.h5mgr.init_dataset(
                    "data_channels_extra",
                    self.shape,
                    self.timebinsPerPixel // self.clk_multiplier,
                    self.channels_extra,
                    np.uint8,
                )

                self.buffer_for_save["channels"] = np.zeros(
                    (
                        self.shape[1],
                        self.shape[0],
                        self.timebinsPerPixel // self.clk_multiplier,
                        self.channels,
                    ),
                    dtype="uint16",
                )

                self.buffer_for_save["channels_extra"] = np.zeros(
                    (
                        self.shape[1],
                        self.shape[0],
                        self.timebinsPerPixel // self.clk_multiplier,
                        self.channels_extra,
                    ),
                    dtype="uint8",
                )

            if "FIFOAnalog" in self.activated_fifos_list:

                self.h5mgr.init_dataset(
                    "data_analog",
                    self.shape,
                    self.timebinsPerPixel,
                    self.channels_analog,
                    np.int32,
                )

                self.buffer_for_save["channels_analog"] = np.zeros(
                    (
                        self.shape[1],
                        self.shape[0],
                        self.timebinsPerPixel,
                        self.channels_analog,
                    ),
                    dtype="int32",
                )

            print_dec("BUFFERS FOR SAVING - Initialized")
            for b in self.buffer_for_save:
                if self.buffer_for_save[b] is not None:
                    print_dec(" - buffer_for_save[%s] = %.3f GB" %(b, self.buffer_for_save[b].size  * self.buffer_for_save[b].itemsize / 1024 / 1024 / 1024 ))
            # print_dec("BUFFER SIZE")
            # print_dec("buffer_for_save size = %.3f GB" % (
            #             self.buffer_for_save["channels"].size * self.buffer_for_save["channels"].itemsize / 1024 / 1024 / 1024))
            # print_dec("buffer_for_save_channels_extra size = %.3f GB" % (
            #             self.buffer_for_save["channels_extra"].size * self.buffer_for_save["channels_extra"].itemsize / 1024 / 1024 / 1024))
            # print_dec("buffer_analog_for_save size = %.3f GB" % (
            #             self.buffer_for_save["channels_analog"].size * self.buffer_for_save["channels_analog"].itemsize / 1024 / 1024 / 1024))


    def stop(self):
        print_dec("AcquisitionLoopProcess STOP")
        self.stop_events_set()

    def trace_reset(self):
        print_dec("Trace Reset")
        self.trace_reset_event.set()

    def FCS_reset(self):
        print_dec("FCS Reset")
        self.FCS_reset_event.set()

    def update_dictionary_now(self):
        pass

    def update_dictionary_slowly(self, timeout):
        self.thread_for_dict_stop = threading.Event()
        self.thread_for_dict_stop.clear()
        self.thread_for_dict = threading.Thread(
            target=self.update_dictionary_slowly_thread, args=[timeout]
        )
        self.thread_for_dict.start()

    def update_dictionary_slowly_thread(self, timeout):
        while not (self.stop_events_is_set_and(self.activated_fifos_list) or self.thread_for_dict_stop.is_set()):
            # print(self.shared_dict_proxy)
            self.shared_dict.update(self.shared_dict_proxy)
            time.sleep(timeout)
            # print("updated")

    def stop_update_dictionary_slowly(self):
        self.thread_for_dict_stop.set()
