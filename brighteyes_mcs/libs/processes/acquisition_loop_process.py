import multiprocessing as mp
import os
import threading
import time
import multiprocessing.queues

VIZTRACER_ON = False
if VIZTRACER_ON: from viztracer import VizTracer

import psutil
import numpy as np

# from ..is_parent_alive import CheckParentAlive
from ..h5manager import H5Manager

# import pprofile

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


def decode_pointer_list(pointer_start, gap, timebinsPerPixel, shape, snake_walk_xy=False, snake_walk_z=False,
                        clk_multiplier=1, delay=0):
    """
    Decode pointer indices into list_b_digital, list_x_digital, list_y_digital, list_z_digital, list_rep_digital.

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
        (list_b_digital, list_x_digital, list_y_digital, list_z_digital, list_rep_digital)
    """

    list_pointer = np.arange(pointer_start, pointer_start + gap)
    list_pointer_shifted = list_pointer + (delay * timebinsPerPixel)
    list_pixel = list_pointer_shifted // timebinsPerPixel
    list_b_digital = list_pointer_shifted % timebinsPerPixel
    if clk_multiplier != 1:
        list_b_digital = list_b_digital % (timebinsPerPixel // clk_multiplier)
    list_x_digital = list_pixel % shape[0]
    list_y_digital = (list_pixel // shape[0]) % shape[1]

    if snake_walk_xy:
        list_x_digital = list_x_digital + (list_y_digital % 2) * (-2 * list_x_digital + shape[0] - 1)

    list_z_digital = list_pixel // (shape[0] * shape[1])
    list_rep_digital = list_z_digital // shape[2]

    if snake_walk_z:
        list_z_digital = (list_z_digital + (list_rep_digital % 2) * (-2 * list_z_digital + shape[2] - 1)) % shape[2]
    else:
        list_z_digital = list_z_digital % shape[2]

    return list_b_digital, list_x_digital, list_y_digital, list_z_digital, list_rep_digital


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
        super().__init__()
        self.gap_analog_in_sample = 0
        self.gap_digital_in_sample = 0
        self.daemon = True
        set_debug(debug)
        print_dec("AcquisitionLoopProcess INIT")

        self.DATA_WORDS_PER_SAMPLE_ANALOG = 1

        if channels == 25:
            print_dec("Found 25 channels -> DATA_WORDS_PER_SAMPLE_DIGITAL = 2")
            self.channels = 25
            self.DATA_WORDS_PER_SAMPLE_DIGITAL = 2
        elif channels == 49:
            print_dec("Found 49 channels -> DATA_WORDS_PER_SAMPLE_DIGITAL = 8")
            self.channels = 49
            self.DATA_WORDS_PER_SAMPLE_DIGITAL = 8
        else:
            print_dec("Found NOT STANDARD NUMBER OF CHANNELS FALLBACK TO DATA_WORDS_PER_SAMPLE_DIGITAL = 2")
            self.channels = 25
            self.DATA_WORDS_PER_SAMPLE_DIGITAL = 2

        self.shm_activated_fifos_list = shared_objects["activated_fifos_list"]
        self.shm_autocorrelation = shared_objects["shared_autocorrelation"]
        self.shm_loc_acquired = shared_objects["loc_acquired"]
        self.shm_loc_previewed = shared_objects["loc_previewed"]

        self.current_frame_digital = 0
        self.current_frame_analog = 0

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
        self.imposed_data_shift = shared_objects["imposed_data_shift"]


        self.timebinsPerPixel = shared_dict["timebins_per_pixel"] * \
                                shared_dict["circ_repetition"] * \
                                shared_dict["circ_points"]

        self.time_resolution = shared_dict["time_resolution"]
        self.expected_words_data_digital = shared_dict["expected_words_data_digital"]
        self.expected_words_data_analog = shared_dict["expected_words_data_analog"]
        self.expected_words_data_per_frame_digital = shared_dict["expected_words_data_per_frame_digital"]
        self.expected_words_data_per_frame_analog = shared_dict["expected_words_data_per_frame_analog"]

        self.DFD_Activate = shared_dict["DFD_Activate"]
        self.DFD_nbins = shared_dict["DFD_nbins"]

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

        self.current_pointer_in_sample_digital = 0
        self.current_pointer_in_sample_analog = 0

        self.stop_event = mp.Event()
        self.local_fifo_done = {}

        self.trace_reset_event = mp.Event()
        self.FCS_reset_event = mp.Event()

        self.buffer_size_in_sample_digital = shared_dict["preview_buffer_size_in_sample"]  # 15000
        self.buffer_size_in_sample_analog = self.buffer_size_in_sample_digital

        self.buffer_size_in_words_digital = self.timebinsPerPixel * self.buffer_size_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL
        self.buffer_size_in_words_analog = self.timebinsPerPixel * self.buffer_size_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG

        if self.channels == 25:
            self.buffer_digital = np.zeros((self.buffer_size_in_words_digital, 25 + 2), dtype=np.uint64)
            self.saturation = np.zeros(25 + 2, dtype=np.uint64)
            self.buffer_sum_SPAD_ch = np.zeros(self.buffer_size_in_words_digital, dtype=np.uint64)

        if self.channels == 49:
            self.buffer_digital = np.zeros((self.buffer_size_in_words_digital, 49 + 2), dtype=np.uint64)
            self.saturation = np.zeros(49 + 2, dtype=np.uint64)
            self.buffer_sum_SPAD_ch = np.zeros(self.buffer_size_in_words_digital, dtype=np.uint64)

        self.buffer_analog = np.zeros((self.buffer_size_in_words_analog, 2), dtype=np.int32)

        self.last_packet_size = shared_dict["last_packet_size"]

        self.total_photon = 0

        self.data_queue = data_queue

        self.do_not_save = do_not_save

        self.buffer_for_save_digital = None
        self.buffer_for_save_digital_extra_ch = None
        self.buffer_analog_for_save = None

        self.channels_analog = 2

        print_dec("AcquisitionLoopProcess INIT DONE")

    def run(self):

        stop_event_proxy = threading.Event()
        trace_reset_event_proxy = threading.Event()
        FCS_reset_event_proxy = threading.Event()

        def thread_update_event_proxy(mp_event, threading_event):
            threading_event.clear()
            while True:
                mp_event.wait()
                threading_event.set()
                mp_event.clear()

        def thread_update_stop_event_proxy(mp_event, threading_event):
            threading_event.clear()
            mp_event.wait()
            threading_event.set()

        threading.Thread(target=thread_update_stop_event_proxy, args=(self.stop_event, stop_event_proxy),
                         daemon=True).start()
        threading.Thread(target=thread_update_event_proxy, args=(self.trace_reset_event, trace_reset_event_proxy),
                         daemon=True).start()
        threading.Thread(target=thread_update_event_proxy, args=(self.FCS_reset_event, FCS_reset_event_proxy),
                         daemon=True).start()

        if VIZTRACER_ON: self.tracer = VizTracer(log_func_with_objprint=True)

        if VIZTRACER_ON: self.tracer.start()

        # self.profiler = pprofile.StatisticalProfile()
        # with self.profiler():

        p = psutil.Process(os.getpid())
        p.nice(psutil.HIGH_PRIORITY_CLASS)
        print_dec("AcquisitionLoopProcess RUN - PID:", os.getpid(), p.nice())

        stop_event_proxy.clear()
        self.current_pointer_in_sample_digital = 0  # self.timebinsPerPixel * self.DATA_WORDS_PER_SAMPLE_DIGITAL
        self.current_pointer_in_sample_analog = 0  # self.timebinsPerPixel * self.DATA_WORDS_PER_SAMPLE_ANALOG

        self.current_frame_digital = 0
        self.current_frame_analog = 0

        print_dec(stop_event_proxy.is_set())
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

        # in h5file the first dimension as "free size" is the fastest way to write on disk
        # if self.DFD_Activate:
        #     self.timebinsPerPixel = self.DFD_nbins

        if not self.do_not_save:
            self.h5mgr = H5Manager(
                self.filenameh5, shm_number_of_threads_h5=self.shm_number_of_threads_h5
            )
            # self.h5file = h5py.File(self.filenameh5, "w")
            print_dec("Filename:", self.filenameh5)

            if "FIFO" in self.shm_activated_fifos_list:
                self.h5mgr.init_dataset(
                    "data", self.shape, self.timebinsPerPixel // self.clk_multiplier, self.channels, np.uint16
                )
                self.h5mgr.init_dataset(
                    "data_channels_extra",
                    self.shape,
                    self.timebinsPerPixel // self.clk_multiplier, # clk_multiplier can be != 1 only when DFD is active
                    self.channels_extra,
                    np.uint8,
                )
            if "FIFOAnalog" in self.shm_activated_fifos_list:
                self.h5mgr.init_dataset(
                    "data_analog",
                    self.shape,
                    self.timebinsPerPixel, # Do not make sense clk multiplier in analog situation
                    self.channels_analog,
                    np.int32,
                )

            self.buffer_for_save_digital = np.zeros(
                (
                    self.shape[1],
                    self.shape[0],
                    self.timebinsPerPixel // self.clk_multiplier,  # clk_multiplier can be != 1 only when DFD is active
                    self.channels,
                ),
                dtype="uint16",
            )

            self.buffer_for_save_digital_extra_ch = np.zeros(
                (
                    self.shape[1],
                    self.shape[0],
                    self.timebinsPerPixel // self.clk_multiplier, # clk_multiplier can be != 1 only when DFD is active
                    self.channels_extra,
                ),
                dtype="uint8",
            )

            self.buffer_analog_for_save = np.zeros(
                (
                    self.shape[1],
                    self.shape[0],
                    self.timebinsPerPixel, # Do not make sense clk multiplier in analog situation
                    self.channels_analog,
                ),
                dtype="int32",
            )
            print_dec("BUFFER SIZE")
            print_dec("buffer_for_save size = %.3f GB" % (
                        self.buffer_for_save_digital.size * self.buffer_for_save_digital.itemsize / 1024 / 1024 / 1024))
            print_dec("buffer_for_save_channels_extra size = %.3f GB" % (
                        self.buffer_for_save_digital_extra_ch.size * self.buffer_for_save_digital_extra_ch.itemsize / 1024 / 1024 / 1024))
            print_dec("buffer_analog_for_save size = %.3f GB" % (
                        self.buffer_analog_for_save.size * self.buffer_analog_for_save.itemsize / 1024 / 1024 / 1024))

        self.total_photon = 0

        self.shared_dict.update(
            {
                "current_z_digital": 0,
                "current_rep_digital": 0,
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

        self.gap_digital_in_sample = 0
        self.gap_analog_in_sample = 0

        # create a dictionary for the frameComplete={"FIFO": False, "FIFOAnalog": False})
        frameComplete = dict((name, False) for name in self.shm_activated_fifos_list)

        internal_buffer_digital = (
            None  # This buffer is used only when the data cross two frames
        )
        internal_buffer_analog = (
            None  # This buffer is used only when the data cross two frames
        )

        print_dec("expected_words_data_digital", self.expected_words_data_digital,
                  "\nexpected_words_data_per_frame_digital", self.expected_words_data_per_frame_digital,
                  "\nexpected_words_data_analog", self.expected_words_data_analog,
                  "\nexpected_words_data_per_frame_analog", self.expected_words_data_per_frame_analog, "\n")

        print_dec("shm_activated_fifos_list", self.shm_activated_fifos_list)
        print_dec("self.activate_show_preview", self.activate_show_preview)

        # self.data_queue["FIFO"] = self.data_queue["FIFO"]
        # self.shm_loc_acquired["FIFO"] = self.shm_loc_acquired["FIFO"]

        self.shared_dict_proxy = {}
        self.update_dictionary_slowly(0.1)

        # This seams redundant but it is for optimize the performances
        channels = self.channels
        channels_y = int(sqrt(self.channels))
        channels_x = channels_y
        print_dec("Channels ", channels, channels_x, channels_y)

        if channels == 25:
            converter = convertRawDataToCountsDirect
        if channels == 49:
            converter = convertRawDataToCountsDirect49

        clk_multiplier = self.clk_multiplier

        print_dec("SHAPE before while", self.shape)

        self.selected_channel = self.shared_dict["channel"]

        def finalize_frame_fifo():
            print_dec("finalize_frame_fifo()")
            try:
                # reset and finalize fingerprints (same block as original)
                frameComplete["FIFO"] = False
                self.fingerprint[3, :, :] = self.fingerprint[0, :, :]
                self.fingerprint[0, :, :] = 0
                self.fingerprint[1, :, :] = 0
                self.fingerprint[2, :, :] = 0
                self.fingerprint[4, :, :] = 0

                current_z_digital = (self.current_frame_digital - 1) % self.shape[2]
                current_rep_digital = (self.current_frame_digital - 1) // self.shape[2]
                print_dec("FRAME [FIFO] ", current_z_digital, current_rep_digital, " DONE")

                self.shared_dict_proxy.update(
                    {
                        "current_z_digital": current_z_digital,
                        "current_rep_digital": current_rep_digital,
                        "total_photon": self.total_photon,
                        "last_packet_size": self.gap_digital_in_sample,
                    }
                )

                if not self.do_not_save:
                    self.h5mgr.add_to_dataset(
                        "data",
                        np.copy(self.buffer_for_save_digital),
                        current_rep_digital,
                        current_z_digital,
                    )
                    self.h5mgr.add_to_dataset(
                        "data_channels_extra",
                        np.copy(self.buffer_for_save_digital_extra_ch),
                        current_rep_digital,
                        current_z_digital,
                    )
                    self.buffer_for_save_digital[:] = 0
                    self.buffer_for_save_digital_extra_ch[:] = 0
                    print_dec("done digital add_to_dataset")
                    print_dec(self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL)
            except Exception as e:
                print_dec("Error in finalize_frame_fifo:", e)

        def finalize_frame_fifo_analog():
            print_dec("finalize_frame_fifo_analog()")
            try:
                frameComplete["FIFOAnalog"] = False

                current_z_analog = (self.current_frame_analog - 1) % self.shape[2]
                current_rep_analog = (self.current_frame_analog - 1) // self.shape[2]
                print_dec("FRAME [FIFOAnalog] ", current_z_analog, current_rep_analog, " DONE")

                self.shared_dict_proxy.update(
                    {
                        "current_z_analog": current_z_analog,
                        "current_rep_analog": current_rep_analog,
                        "last_packet_size": self.gap_analog_in_sample
                    }
                )
                if not self.do_not_save:

                    self.h5mgr.add_to_dataset(
                        "data_analog",
                        np.copy(self.buffer_analog_for_save),
                        current_rep_analog,
                        current_z_analog,
                    )
                    self.buffer_analog_for_save[:] = 0
                    print_dec("done analog add_to_dataset")
                    print_dec(self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG, self.expected_words_data_analog)
            except Exception as e:
                print_dec("Error in finalize_frame_fifo_analog:", e)

        while not stop_event_proxy.is_set():
            selected_channel = self.selected_channel

            if self.do_not_save:
                self.shm_number_of_threads_h5.value = -1

            self.shared_dict_proxy["FIFO_status"] = self.data_queue["FIFO"].qsize()
            self.shared_dict_proxy["FIFOAnalog_status"] = self.data_queue["FIFOAnalog"].qsize()

            if "FIFO" in self.shm_activated_fifos_list:
                max_gap_frame_digital_in_words = self.expected_words_data_per_frame_digital * (
                        self.current_frame_digital + 1
                )

                if not self.data_queue["FIFO"].empty():
                    remaining_digital_in_words = max_gap_frame_digital_in_words - (self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL)

                    # handle previously split buffer first
                    if (
                            internal_buffer_digital is not None and internal_buffer_digital.size != 0
                    ):  # if the previous queue data was between two frames

                        print_dec(
                            len(internal_buffer_digital),
                            remaining_digital_in_words,
                            max_gap_frame_digital_in_words,
                            (self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL),
                        )
                        # if remaining_digital_in_words <= 0 means we already completed the frame before consuming internal_buffer_digital
                        if remaining_digital_in_words < 0:
                            print_dec("THIS IS DEEPLY WRONG!! remaining_digital_in_words < 0, ", remaining_digital_in_words)

                        elif remaining_digital_in_words == 0:
                            frameComplete["FIFO"] = True
                            self.current_frame_digital += 1
                            max_gap_frame_digital_in_words = self.expected_words_data_per_frame_digital * (self.current_frame_digital + 1)
                            remaining_digital_in_words = max_gap_frame_digital_in_words - (self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL)
                        #if
                        elif remaining_digital_in_words > 0:
                            data_from_queue_digital = internal_buffer_digital[: remaining_digital_in_words]
                            self.gap_digital_in_sample = data_from_queue_digital.shape[0] // self.DATA_WORDS_PER_SAMPLE_DIGITAL
                            internal_buffer_digital = internal_buffer_digital[remaining_digital_in_words:]
                        else:
                            # remaining_digital_in_words still zero (rare): put nothing to decode here
                            data_from_queue_digital = None
                            self.gap_digital_in_sample = 0
                            internal_buffer_digital = None

                    # standard path: get a new packet from the queue
                    if  internal_buffer_digital is None:  # standard case (no previous split data)
                        data_from_queue_digital = self.data_queue["FIFO"].get()
                        self.gap_digital_in_sample = data_from_queue_digital.shape[0] // self.DATA_WORDS_PER_SAMPLE_DIGITAL

                        # recalc remaining_digital_in_words because current_frame_digital might have changed above
                        remaining_digital_in_words = max_gap_frame_digital_in_words - (self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL)

                        if remaining_digital_in_words == 0:
                            # nothing left in this frame: finalize it
                            frameComplete["FIFO"] = True
                            self.current_frame_digital += 1
                            # push the whole packet to next frame (store for next iteration)
                            internal_buffer_digital = data_from_queue_digital  # push entire packet to next frame
                            # advance pointer to end of last frame, so stop condition can be satisfied
                            self.current_pointer_in_sample_digital = max_gap_frame_digital_in_words // self.DATA_WORDS_PER_SAMPLE_DIGITAL
                            self.gap_digital_in_sample = 0
                            # run finalize immediately to keep state consistent (we didn't process any buffer_up_to_gap_digital)
                            finalize_frame_fifo()
                            # skip decoding for this iteration (we set gap=0)
                            data_from_queue_digital = None
                        else:
                            # normal split case: packet crosses frame boundary
                            if (self.current_pointer_in_sample_digital + self.gap_digital_in_sample) * self.DATA_WORDS_PER_SAMPLE_DIGITAL >= max_gap_frame_digital_in_words:
                                print_dec(
                                    f"(self.current_pointer_in_sample_digital + self.gap_digital_in_sample) * self.DATA_WORDS_PER_SAMPLE_DIGITAL = {(self.current_pointer_in_sample_digital + self.gap_digital_in_sample) * self.DATA_WORDS_PER_SAMPLE_DIGITAL}, "
                                    f"self.gap_digital_in_sample = {self.gap_digital_in_sample}, "
                                    f"max_gap_frame_digital_in_words = {max_gap_frame_digital_in_words}"
                                )

                                print_dec(
                                    f"data_from_queue_digital.shape = {data_from_queue_digital.shape}, "
                                    f"remaining_digital_in_words = {remaining_digital_in_words}, "
                                    f"(self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL) = {(self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL)}"
                                )

                                internal_buffer_digital = data_from_queue_digital[remaining_digital_in_words:]
                                data_from_queue_digital = data_from_queue_digital[:remaining_digital_in_words]
                                self.gap_digital_in_sample = data_from_queue_digital.shape[0] // self.DATA_WORDS_PER_SAMPLE_DIGITAL

                                frameComplete["FIFO"] = True

                                self.current_frame_digital += 1

                    # normalize internal_buffer_digital emptiness
                    if internal_buffer_digital is not None and internal_buffer_digital.size == 0:
                        internal_buffer_digital = None

                    # safety: if we would exceed expected_words_data_digital, truncate gap
                    if self.expected_words_data_digital < (self.current_pointer_in_sample_digital + self.gap_digital_in_sample) * self.DATA_WORDS_PER_SAMPLE_DIGITAL:
                        self.gap_digital_in_sample = max_gap_frame_digital_in_words // self.DATA_WORDS_PER_SAMPLE_DIGITAL - self.current_pointer_in_sample_digital
                        print_dec("MISTERY!!!")
                        print_dec("New GAP", self.gap_digital_in_sample)

                    # If there's no data to decode (gap==0 or data_from_queue_digital is None) skip decoding section.
                    if self.gap_digital_in_sample > 0 and data_from_queue_digital is not None:
                        #
                        # Generation of list_pixel, list_b_digital, list_x_digital, list_y_digital, list_z_digital
                        #
                        list_b_digital, list_x_digital, list_y_digital, list_z_digital, list_rep_digital = decode_pointer_list(
                            self.current_pointer_in_sample_digital,
                            self.gap_digital_in_sample,
                            self.timebinsPerPixel,
                            self.shape,
                            snake_walk_xy=self.snake_walk_xy,
                            snake_walk_z=self.snake_walk_z,
                            clk_multiplier=clk_multiplier,
                            delay=self.imposed_data_shift.value
                        )

                        self.shared_dict_proxy["last_packet_size"] = self.gap_digital_in_sample

                        if self.gap_digital_in_sample == 0:
                            print_dec("self.gap_digital_in_sample = 0")
                        if self.gap_digital_in_sample * self.DATA_WORDS_PER_SAMPLE_DIGITAL > self.buffer_size_in_words_digital:
                            print_dec(
                                "ERROR: Too many data larger than the buffer. GAP",
                                self.gap_digital_in_sample,
                                "buffer_size_in_words_digital",
                                self.buffer_size_in_words_digital,
                            )

                        self.saturation[:] = 0

                        # convert data -> buffer
                        if (
                                converter(
                                    data = data_from_queue_digital,
                                    start = 0,
                                    stop = self.gap_digital_in_sample * self.DATA_WORDS_PER_SAMPLE_DIGITAL,
                                    buffer_out = self.buffer_digital,
                                    buffer_sum = self.buffer_sum_SPAD_ch,
                                    fingerprint_saturation = self.saturation,
                                    mask = self.fingerprint_mask,
                                )
                                == -1
                        ):
                            print_dec(
                                "==============DISASTER IN THE PREVIEW====================="
                            )

                        buffer_up_to_gap_digital = self.buffer_digital[: self.gap_digital_in_sample]

                        if buffer_up_to_gap_digital.size != 0:
                            if isinstance(selected_channel, int):
                                if (selected_channel < (channels + 2)):
                                    if (self.activate_show_preview == True):
                                        self.image_xy_lock.acquire()
                                        self.image_xy[list_y_digital, list_x_digital] = 0
                                        np.add.at(
                                            self.image_xy,
                                            (list_y_digital, list_x_digital),
                                            buffer_up_to_gap_digital[:, selected_channel],
                                        )
                                        self.image_xy_lock.release()

                                        cond_x_central = list_x_digital == (self.shape[0] // 2)
                                        self.image_zy_lock.acquire()
                                        self.image_zy[
                                            list_y_digital[cond_x_central], list_z_digital[cond_x_central]
                                        ] = 0
                                        np.add.at(
                                            self.image_zy,
                                            (list_y_digital[cond_x_central], list_z_digital[cond_x_central]),
                                            buffer_up_to_gap_digital[cond_x_central, selected_channel],
                                        )
                                        self.image_zy_lock.release()

                                        cond_y_central = list_y_digital == (self.shape[1] // 2)
                                        self.image_xz_lock.acquire()
                                        self.image_xz[
                                            list_z_digital[cond_y_central], list_x_digital[cond_y_central]
                                        ] = 0
                                        np.add.at(
                                            self.image_xz,
                                            (list_z_digital[cond_y_central], list_x_digital[cond_y_central]),
                                            buffer_up_to_gap_digital[cond_y_central, selected_channel],
                                        )
                                        self.image_xz_lock.release()

                                    if self.active_autocorrelation:
                                        correlator.add(buffer_up_to_gap_digital[:, selected_channel])
                                        self.autocorrelation[
                                            1, :
                                        ] = correlator.get_correlation_normalized()
                                    if self.activate_trace:
                                        temporalBinner.add(buffer_up_to_gap_digital[:, selected_channel])
                                        self.trace_pos.value = (
                                            temporalBinner.get_current_position_bins()
                                        )
                                        self.trace[1, :] = temporalBinner.get_bins()

                            elif selected_channel.startswith("Sum"):
                                if self.activate_show_preview == True:
                                    self.image_xy_lock.acquire()
                                    self.image_xy[list_y_digital, list_x_digital] = 0
                                    np.add.at(
                                        self.image_xy,
                                        (list_y_digital, list_x_digital),
                                        self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample],
                                    )
                                    self.image_xy_lock.release()

                                    cond_x_central = list_x_digital == (self.shape[0] // 2)
                                    self.image_zy_lock.acquire()
                                    self.image_zy[
                                        list_y_digital[cond_x_central], list_z_digital[cond_x_central]
                                    ] = 0
                                    np.add.at(
                                        self.image_zy,
                                        (list_y_digital[cond_x_central], list_z_digital[cond_x_central]),
                                        self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample][cond_x_central],
                                    )
                                    self.image_zy_lock.release()

                                    cond_y_central = list_y_digital == (self.shape[1] // 2)
                                    self.image_xz_lock.acquire()
                                    self.image_xz[
                                        list_z_digital[cond_y_central], list_x_digital[cond_y_central]
                                    ] = 0
                                    np.add.at(
                                        self.image_xz,
                                        (list_z_digital[cond_y_central], list_x_digital[cond_y_central]),
                                        self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample][cond_y_central],
                                    )
                                    self.image_xz_lock.release()

                                if self.active_autocorrelation:
                                    correlator.add(self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample])
                                    self.autocorrelation[
                                        1, :
                                    ] = correlator.get_correlation_normalized()
                                if self.activate_trace:
                                    temporalBinner.add(self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample])
                                    self.trace_pos.value = (
                                        temporalBinner.get_current_position_bins()
                                    )
                                    self.trace[1, :] = temporalBinner.get_bins()

                            elif selected_channel.startswith("RGB"):
                                if selected_channel.startswith("RGB "):
                                    if self.activate_show_preview == True:
                                        channelA = int(selected_channel.split(" ")[1])
                                        channelB = int(selected_channel.split(" ")[2])
                                        channelC = int(selected_channel.split(" ")[3])

                                        self.image_xy_rgb_lock.acquire()
                                        self.image_xy_rgb[list_y_digital, list_x_digital, 0] = 0
                                        self.image_xy_rgb[list_y_digital, list_x_digital, 1] = 0
                                        self.image_xy_rgb[list_y_digital, list_x_digital, 2] = 0

                                        np.add.at(
                                            self.image_xy_rgb[:, :, 0],
                                            (list_y_digital, list_x_digital),
                                            buffer_up_to_gap_digital[:, channelA],
                                        )
                                        np.add.at(
                                            self.image_xy_rgb[:, :, 1],
                                            (list_y_digital, list_x_digital),
                                            buffer_up_to_gap_digital[:, channelB],
                                        )
                                        np.add.at(
                                            self.image_xy_rgb[:, :, 2],
                                            (list_y_digital, list_x_digital),
                                            buffer_up_to_gap_digital[:, channelC],
                                        )
                                        self.image_xy_rgb_lock.release()
                                if selected_channel.startswith("RGB2"):
                                    if self.activate_show_preview == True:
                                        self.image_xy_rgb_lock.acquire()
                                        self.image_xy_rgb[list_y_digital, list_x_digital, 0] = 0
                                        self.image_xy_rgb[list_y_digital, list_x_digital, 1] = 0
                                        self.image_xy_rgb[list_y_digital, list_x_digital, 2] = 0

                                        if self.buffer_sum_SPAD_ch.shape[0] > 2:
                                            np.add.at(
                                                self.image_xy_rgb[:, :, 0],
                                                (list_y_digital[::3], list_x_digital[::3]),
                                                self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample:3],
                                            )

                                            np.add.at(
                                                self.image_xy_rgb[:, :, 1],
                                                (list_y_digital[1::3], list_x_digital[1::3]),
                                                self.buffer_sum_SPAD_ch[1: self.gap_digital_in_sample:3],
                                            )

                                            np.add.at(
                                                self.image_xy_rgb[:, :, 2],
                                                (list_y_digital[2::3], list_x_digital[2::3]),
                                                self.buffer_sum_SPAD_ch[2: self.gap_digital_in_sample:3],
                                            )

                                        self.image_xy_rgb_lock.release()
                                if selected_channel.startswith("RGB3"):
                                    self.image_xy_rgb_lock.acquire()
                                    self.image_xy_rgb[list_y_digital, list_x_digital, 0] = 0
                                    self.image_xy_rgb[list_y_digital, list_x_digital, 1] = 0
                                    self.image_xy_rgb[list_y_digital, list_x_digital, 2] = 0
                                    if self.buffer_sum_SPAD_ch.shape[0] > 2:
                                        np.add.at(
                                            self.image_xy_rgb[:, :, 0],
                                            (list_y_digital[::3], list_x_digital[::3]),
                                            self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample:3],
                                        )

                                        np.add.at(
                                            self.image_xy_rgb[:, :, 1],
                                            (list_y_digital[1::3], list_x_digital[1::3]),
                                            self.buffer_sum_SPAD_ch[1: self.gap_digital_in_sample:3],
                                        )

                                        np.add.at(
                                            self.image_xy_rgb[:, :, 2],
                                            (list_y_digital[2::3], list_x_digital[2::3]),
                                            self.buffer_sum_SPAD_ch[2: self.gap_digital_in_sample:3],
                                        )

                                    self.image_xy_rgb_lock.release()

                                if selected_channel.startswith("RGBDFD"):
                                    self.image_xy_rgb_lock.acquire()
                                    self.image_xy_rgb[list_y_digital, list_x_digital, 0] = 0
                                    self.image_xy_rgb[list_y_digital, list_x_digital, 1] = 0
                                    self.image_xy_rgb[list_y_digital, list_x_digital, 2] = 0

                                    tparts = 3
                                    tbins = self.timebinsPerPixel
                                    gbins = tbins // tparts

                                    if self.buffer_sum_SPAD_ch.shape[0] > 2:
                                        cond0 = list_b_digital < gbins

                                        np.add.at(
                                            self.image_xy_rgb[:, :, 0],
                                            (list_y_digital[::][cond0], list_x_digital[::][cond0]),
                                            self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample:][cond0],
                                        )

                                        cond0 = (list_b_digital >= gbins) & (list_b_digital < 2 * gbins)

                                        np.add.at(
                                            self.image_xy_rgb[:, :, 1],
                                            (list_y_digital[::][cond0], list_x_digital[::][cond0]),
                                            self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample:][cond0],
                                        )

                                        cond0 = list_b_digital >= 2 * gbins

                                        np.add.at(
                                            self.image_xy_rgb[:, :, 2],
                                            (list_y_digital[::][cond0], list_x_digital[::][cond0]),
                                            self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample:][cond0],
                                        )

                                    self.image_xy_rgb_lock.release()

                                if self.active_autocorrelation:
                                    correlator.add(self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample])
                                    self.autocorrelation[
                                        1, :
                                    ] = correlator.get_correlation_normalized()
                                if self.activate_trace:
                                    temporalBinner.add(self.buffer_sum_SPAD_ch[: self.gap_digital_in_sample])
                                    self.trace_pos.value = (
                                        temporalBinner.get_current_position_bins()
                                    )
                                    self.trace[1, :] = temporalBinner.get_bins()

                            if not self.do_not_save:
                                # This is for debug purpose

                                np.add.at(self.buffer_for_save_digital, (list_y_digital, list_x_digital, list_b_digital),
                                          buffer_up_to_gap_digital[:,:channels])
                                np.add.at(self.buffer_for_save_digital_extra_ch, (list_y_digital, list_x_digital, list_b_digital),
                                          buffer_up_to_gap_digital[:,channels:])

                                # self.buffer_for_save_digital[
                                #     list_y_digital, list_x_digital, list_b_digital, :
                                # ] = buffer_up_to_gap_digital[:, :channels]
                                # self.buffer_for_save_digital_extra_ch[
                                #     list_y_digital, list_x_digital, list_b_digital, :
                                # ] = buffer_up_to_gap_digital[:, channels:]

                                # self.buffer_for_save_digital[list_y_digital, list_x_digital, list_b_digital] = buffer_up_to_gap_digital[:, :channels]
                                # self.buffer_for_save_digital_extra_ch[list_y_digital, list_x_digital, list_b_digital] = buffer_up_to_gap_digital[:, channels:]
                                #
                                # np.add.at(
                                #     self.buffer_for_save_digital,
                                #     (list_y_digital, list_x_digital, list_b_digital),
                                #     buffer_up_to_gap_digital[:, :channels],
                                # )
                                #
                                # np.add.at(
                                #     self.buffer_for_save_digital_extra_ch,
                                #     (list_y_digital, list_x_digital, list_b_digital),
                                #     buffer_up_to_gap_digital[:, channels:],
                                # )

                                # print_dec(
                                #     self.current_pointer_in_sample_digital,
                                #     self.current_pointer_in_sample_digital + self.gap_digital_in_sample,
                                #     self.buffer_digital.shape,
                                #     buffer_up_to_gap_digital.shape,
                                # )
                                # print(self.buffer_digital.shape , buffer_up_to_gap_digital.shape, list_y_digital.shape)
                                # print_dec(
                                #     self.current_frame_digital,
                                #     self.gap_digital_in_sample,
                                #     list_y_digital.max(),
                                #     list_x_digital.max(),
                                #     list_b_digital.max(),
                                # )

                            sum_tmp = buffer_up_to_gap_digital[:, :channels].sum(axis=0).reshape(channels_x, channels_y)

                            self.total_photon = np.sum(sum_tmp)

                            self.fingerprint[0, :, :] += sum_tmp
                            try:
                                self.fingerprint[1, :, :] = buffer_up_to_gap_digital[-1, :channels].reshape(
                                    channels_x, channels_y
                                )
                            except:
                                print_dec("buffer_up_to_gap_digital", buffer_up_to_gap_digital)
                                self.fingerprint[1, :, :] = 0

                            if self.gap_digital_in_sample > 10000:
                                self.fingerprint[2, :, :] = (
                                    self.buffer_digital[:10000, :channels].sum(axis=0).reshape(channels_x, channels_y)
                                )

                            self.fingerprint[4, :, :] += self.saturation[:channels].reshape(channels_x, channels_y)
                            self.current_pointer_in_sample_digital += self.gap_digital_in_sample
                            self.shm_loc_previewed["FIFO"].value = self.current_pointer_in_sample_digital
                            # print_dec(self.current_pointer_in_sample_digital*2, self.gap_digital_in_sample*2, (self.current_pointer_in_sample_digital + self.gap_digital_in_sample)*2)

                            if frameComplete["FIFO"]:
                                # we still run the same finalization here for the normal path
                                finalize_frame_fifo()


            if "FIFOAnalog" in self.shm_activated_fifos_list:
                max_gap_frame_analog_in_words = self.expected_words_data_per_frame_analog * (
                        self.current_frame_analog + 1

                )
                if not self.data_queue["FIFOAnalog"].empty():
                    remaining_analog_in_words = max_gap_frame_analog_in_words - (self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG)

                    if (
                            internal_buffer_analog is not None and internal_buffer_analog.size != 0
                    ):  # if the previous queue data was between two frames

                        if remaining_analog_in_words < 0:
                            print_dec("THIS IS DEEPLY WRONG!! remaining_analog_in_words < 0, ", remaining_analog_in_words)

                        elif remaining_analog_in_words == 0:
                            frameComplete["FIFOAnalog"] = True
                            self.current_frame_analog += 1
                            max_gap_frame_analog_in_words = self.expected_words_data_per_frame_analog * (self.current_frame_analog + 1)
                            remaining_analog_in_words = max_gap_frame_analog_in_words - (self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG)
                        # if
                        elif remaining_analog_in_words > 0:
                            data_from_queue_analog = internal_buffer_analog[: remaining_analog_in_words]
                            self.gap_analog_in_sample = data_from_queue_analog.shape[0] // self.DATA_WORDS_PER_SAMPLE_ANALOG
                            internal_buffer_analog = internal_buffer_analog[remaining_analog_in_words:]
                        else:
                            data_from_queue_analog = None
                            self.gap_analog_in_sample = 0
                            internal_buffer_analog = None

                    if internal_buffer_analog is None:
                        data_from_queue_analog = self.data_queue["FIFOAnalog"].get()
                        self.gap_analog_in_sample = data_from_queue_analog.shape[0] // self.DATA_WORDS_PER_SAMPLE_ANALOG

                        # recompute remaining_analog_in_words (current_frame_analog could have changed)
                        remaining_analog_in_words = max_gap_frame_analog_in_words - (self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG)

                        if remaining_analog_in_words == 0:
                            # nothing left in this analog frame
                            frameComplete["FIFOAnalog"] = True
                            self.current_frame_analog += 1
                            # push whole analog packet to next frame
                            internal_buffer_analog = data_from_queue_analog  # CORRECT: use analog variable
                            # advance analog pointer to frame boundary so stopping condition can be reached
                            self.current_pointer_in_sample_analog = max_gap_frame_analog_in_words // self.DATA_WORDS_PER_SAMPLE_ANALOG
                            self.gap_analog_in_sample = 0
                            # finalize analog frame now
                            finalize_frame_fifo_analog()
                            data_from_queue_analog = None
                        else:
                            if (self.current_pointer_in_sample_analog + self.gap_analog_in_sample) * self.DATA_WORDS_PER_SAMPLE_ANALOG >= max_gap_frame_analog_in_words:
                                print_dec(
                                    f"(self.current_pointer_in_sample_analog + self.gap_analog_in_sample) * self.DATA_WORDS_PER_SAMPLE_ANALOG = {(self.current_pointer_in_sample_analog + self.gap_analog_in_sample) * self.DATA_WORDS_PER_SAMPLE_ANALOG}, "
                                    f"self.gap_analog_in_sample = {self.gap_analog_in_sample}, "
                                    f"max_gap_frame_analog_in_words = {max_gap_frame_analog_in_words}"
                                )

                                print_dec(
                                    f"data_from_queue_analog.shape = {data_from_queue_analog.shape}, "
                                    f"remaining_analog_in_words = {remaining_analog_in_words}, "
                                    f"(self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG) = {(self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG)}"
                                )

                                internal_buffer_analog = data_from_queue_analog[remaining_analog_in_words:]
                                data_from_queue_analog = data_from_queue_analog[:remaining_analog_in_words]
                                self.gap_analog_in_sample = data_from_queue_analog.shape[0] // self.DATA_WORDS_PER_SAMPLE_ANALOG

                                frameComplete["FIFOAnalog"] = True

                                self.current_frame_analog += 1

                    if internal_buffer_analog is not None and internal_buffer_analog.size == 0:
                        internal_buffer_analog = None

                    if self.expected_words_data_analog < (self.current_pointer_in_sample_analog + self.gap_analog_in_sample) * self.DATA_WORDS_PER_SAMPLE_ANALOG:
                        self.gap_analog_in_sample = max_gap_frame_analog_in_words // self.DATA_WORDS_PER_SAMPLE_ANALOG - self.current_pointer_in_sample_analog
                        print_dec("MISTERY")
                        print_dec("New GAP", self.gap_analog_in_sample)

                    # Only decode analog if we have a positive gap and data
                    if self.gap_analog_in_sample > 0 and data_from_queue_analog is not None:
                        list_b_analog, list_x_analog, list_y_analog, list_z_analog, list_rep_analog = decode_pointer_list(
                            self.current_pointer_in_sample_analog,
                            self.gap_analog_in_sample,
                            self.timebinsPerPixel,
                            self.shape,
                            snake_walk_xy=self.snake_walk_xy,
                            snake_walk_z=self.snake_walk_z,
                            delay=self.imposed_data_shift.value
                        )

                        self.shared_dict_proxy["last_packet_size"] = self.gap_analog_in_sample

                        if self.gap_analog_in_sample == 0:
                            print_dec("self.gap_analog_in_sample = 0")
                        if self.gap_analog_in_sample * self.DATA_WORDS_PER_SAMPLE_ANALOG > self.buffer_size_in_words_analog:
                            print_dec(
                                "Too many data larger than the buffer. GAP",
                                self.gap_analog_in_sample,
                                "buffer_size_in_words_analog",
                                self.buffer_size_in_words_analog,
                            )

                        if (
                                convertDataFromAnalogFIFO(
                                    data = data_from_queue_analog,
                                    start = 0,
                                    stop = self.gap_analog_in_sample * self.DATA_WORDS_PER_SAMPLE_ANALOG,
                                    buffer_out = self.buffer_analog,
                                    force_positive = 0,
                                )
                                == -1
                        ):
                            print_dec(
                                "==============DISASTER IN THE PREVIEW====================="
                            )

                        buffer_up_to_gap_analog = self.buffer_analog[: self.gap_analog_in_sample]

                        if buffer_up_to_gap_analog.size != 0:
                            if "Analog" in selected_channel:
                                if self.activate_show_preview == True:
                                    if selected_channel[-1:] == "A":
                                        analog_ch = 0
                                    else:
                                        analog_ch = 1

                                    self.image_xy_lock.acquire()
                                    self.image_xy[list_y_analog, list_x_analog] = 0
                                    np.add.at(
                                        self.image_xy,
                                        (list_y_analog, list_x_analog),
                                        buffer_up_to_gap_analog[:, analog_ch],
                                    )
                                    self.image_xy_lock.release()

                                    cond_x_central = list_x_analog == (self.shape[0] // 2)
                                    self.image_zy_lock.acquire()
                                    self.image_zy[list_y_analog[cond_x_central], list_z_analog[cond_x_central]] = 0
                                    np.add.at(
                                        self.image_zy,
                                        (list_y_analog[cond_x_central], list_z_analog[cond_x_central]),
                                        buffer_up_to_gap_analog[:, analog_ch][cond_x_central],
                                    )
                                    self.image_zy_lock.release()

                                    cond_y_central = list_y_analog == (self.shape[0] // 2)
                                    self.image_xz_lock.acquire()
                                    self.image_xz[list_z_analog[cond_y_central], list_x_analog[cond_y_central]] = 0
                                    np.add.at(
                                        self.image_xz,
                                        (list_z_analog[cond_y_central], list_x_analog[cond_y_central]),
                                        buffer_up_to_gap_analog[:, analog_ch][cond_y_central],
                                    )
                                    self.image_xz_lock.release()

                                if self.active_autocorrelation:
                                    correlator.add(buffer_up_to_gap_analog[:, analog_ch])
                                    self.autocorrelation[
                                        1, :
                                    ] = correlator.get_correlation_normalized()
                                if self.activate_trace:
                                    temporalBinner.add(buffer_up_to_gap_analog[:, analog_ch])
                                    self.trace_pos.value = (
                                        temporalBinner.get_current_position_bins()
                                    )
                                    self.trace[1, :] = temporalBinner.get_bins()

                            if not self.do_not_save:
                                self.buffer_analog_for_save[
                                    list_y_analog, list_x_analog, list_b_analog, :
                                ] = buffer_up_to_gap_analog

                            self.current_pointer_in_sample_analog += self.gap_analog_in_sample
                            self.shm_loc_previewed["FIFOAnalog"].value = self.current_pointer_in_sample_analog

                            self.shared_dict_proxy.update({"total_photon": self.total_photon})
                            if frameComplete["FIFOAnalog"]:
                                # finalize analog frame on the normal path
                                finalize_frame_fifo_analog()
                            #print_dec("self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG >= self.expected_words_data_analog:",
                            #         self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG, self.expected_words_data_analog)


            cond_digital = (self.current_pointer_in_sample_digital * self.DATA_WORDS_PER_SAMPLE_DIGITAL >= self.expected_words_data_digital)
            cond_analog  = (self.current_pointer_in_sample_analog * self.DATA_WORDS_PER_SAMPLE_ANALOG >= self.expected_words_data_analog)

            if not(
                    ("FIFO" in self.shm_activated_fifos_list and not cond_digital)
                    or
                    ("FIFOAnalog" in self.shm_activated_fifos_list and not cond_analog)
            ):
                self.stop_event.set()
                stop_event_proxy.set()

            if trace_reset_event_proxy.is_set():
                print_dec("trace_reset_event.is_set()")
                temporalBinner.reset()
                trace_reset_event_proxy.clear()
            if FCS_reset_event_proxy.is_set():
                correlator.reset()
                FCS_reset_event_proxy.clear()

            time.sleep(0.000001)
        # self.profiler.disable()
        # self.profiler.print_stats()
        # self.profiler.dump_stats("dumpspeed.txt")
        # self.profiler.dump_stats("cachegrind.out.prova")

        self.stop_update_dictionary_slowly()

        self.acquisition_almost_done.set()

        if not self.do_not_save:
            # self.h5file.close()
            self.h5mgr.close()
        self.acquisition_done.set()
        print_dec("Acquisition done")
        stop_event_proxy.clear()

        print_dec("run() acquisition_loop_process stopped")

        if VIZTRACER_ON: self.tracer.stop()
        if VIZTRACER_ON: self.tracer.save()

    def stop(self):
        print_dec("AcquisitionLoopProcess STOP")
        self.stop_event.set()

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
        while not (self.stop_event.is_set() or self.thread_for_dict_stop.is_set()):
            # print(self.shared_dict_proxy)
            self.selected_channel = self.shared_dict["channel"]
            self.shared_dict.update(self.shared_dict_proxy)
            time.sleep(timeout)
            # print("updated")

    def stop_update_dictionary_slowly(self):
        self.thread_for_dict_stop.set()
