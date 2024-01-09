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

class AcquisitionLoopProcess(mp.Process):
    def __init__(
        self,
        channels,
        shared_objects,
        activate_preview,
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
        self.shm_autocorrelation = shared_objects["shared_autocorrelation"]
        self.shm_loc_acquired = shared_objects["loc_acquired"]
        self.shm_loc_previewed = shared_objects["loc_previewed"]
        self.current_x = 0
        self.current_y = 0
        self.current_f = 0
        self.current_pixel = 0
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

        self.timebinsPerPixel = shared_dict["timebins_per_pixel"]
        self.time_resolution = shared_dict["time_resolution"]
        self.expected_raw_data = shared_dict["expected_raw_data"]
        self.expected_raw_data_per_frame = shared_dict["expected_raw_data_per_frame"]

        self.DFD_Activate = shared_dict["DFD_Activate"]
        self.DFD_nbins = 120

        self.snake_walk = shared_dict["snake_walk"]

        self.filenameh5 = shared_dict["filenameh5"]

        self.acquisition_done = acquisition_done
        self.acquisition_done.clear()

        self.acquisition_almost_done = acquisition_almost_done
        self.acquisition_almost_done.clear()

        self.shared_dict = shared_dict

        self.shape = shared_dict["shape"]
        self.channels = shared_dict["channels"]
        self.channels_extra = 2

        self.current_pointer = 0
        self.current_pointer_analog = 0
        self.stop_event = mp.Event()
        self.trace_reset_event = mp.Event()
        self.FCS_reset_event = mp.Event()

        self.buffer_size_in_words = shared_dict["preview_buffer_size_in_words"]  # 15000
        self.buffer_size = self.timebinsPerPixel * self.buffer_size_in_words * self.DATA_WORDS_DIGITAL
        
        
        if self.channels == 25:            
            self.buffer = np.zeros((self.buffer_size, 25 + 2), dtype=np.uint64)
            self.saturation = np.zeros(25 + 2, dtype=np.uint64)
            self.buffer_sum_SPAD_ch = np.zeros(self.buffer_size, dtype=np.uint64)
            
        if self.channels == 49:
            self.buffer = np.zeros((self.buffer_size, 49 + 2), dtype=np.uint64)
            self.saturation = np.zeros(49 + 2, dtype=np.uint64)
            self.buffer_sum_SPAD_ch = np.zeros(self.buffer_size, dtype=np.uint64)

        self.buffer_analog = np.zeros((self.buffer_size, 2), dtype=np.int32)

        self.last_packet_size = shared_dict["last_packet_size"]

        self.total_photon = 0

        self.data_queue = data_queue

        self.activate_preview = activate_preview

        self.buffer_for_save = None
        self.buffer_for_save_channels_extra = None
        self.buffer_analog_for_save = None

        self.channels_analog = 2

        super().__init__()
        print_dec("AcquisitionLoopProcess INIT DONE")

    def run(self):
        # self.profiler = pprofile.StatisticalProfile()
        # with self.profiler():
        print_dec(
            "AcquisitionLoopProcess RUN - PID:",
            os.getpid(),
            "    <======================================================",
        )

        self.stop_event.clear()
        self.current_pointer = 0  # self.timebinsPerPixel * self.DATA_WORDS_DIGITAL
        self.current_pointer_analog = 0  # self.timebinsPerPixel * self.DATA_WORDS_ANALOG

        self.current_pixel = 0
        self.current_frame = 0

        print_dec(self.stop_event.is_set())
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
        if self.DFD_Activate:
            self.timebinsPerPixel = self.DFD_nbins

        if not self.activate_preview:
            self.h5mgr = H5Manager(
                self.filenameh5, shm_number_of_threads_h5=self.shm_number_of_threads_h5
            )
            # self.h5file = h5py.File(self.filenameh5, "w")
            print_dec("Filename:", self.filenameh5)

            if "FIFO" in self.shm_activated_fifos_list:
                self.h5mgr.init_dataset(
                    "data", self.shape, self.timebinsPerPixel, self.channels, np.uint16
                )
                self.h5mgr.init_dataset(
                    "data_channels_extra",
                    self.shape,
                    self.timebinsPerPixel,
                    self.channels_extra,
                    np.uint8,
                )
            if "FIFOAnalog" in self.shm_activated_fifos_list:
                self.h5mgr.init_dataset(
                    "data_analog",
                    self.shape,
                    self.timebinsPerPixel,
                    self.channels_analog,
                    np.int32,
                )

            self.buffer_for_save = np.zeros(
                (
                    self.shape[1],
                    self.shape[0],
                    self.timebinsPerPixel,
                    self.channels,
                ),
                dtype="uint16",
            )

            self.buffer_for_save_channels_extra = np.zeros(
                (
                    self.shape[1],
                    self.shape[0],
                    self.timebinsPerPixel,
                    self.channels_extra,
                ),
                dtype="uint8",
            )

            self.buffer_analog_for_save = np.zeros(
                (
                    self.shape[1],
                    self.shape[0],
                    self.timebinsPerPixel,
                    self.channels_analog,
                ),
                dtype="int32",
            )

        self.total_photon = 0

        self.shared_dict.update(
            {
                "current_z": 0,
                "current_rep": 0,
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

        self.gap = 0
        self.gap_analog = 0

        # create a dictionary for the frameComplete={"FIFO": False, "FIFOAnalog": False})
        frameComplete = dict((name, False) for name in self.shm_activated_fifos_list)

        internal_buffer = (
            None  # This buffer is used only when the data cross two frames
        )
        internal_buffer_analog = (
            None  # This buffer is used only when the data cross two frames
        )

        print_dec(self.expected_raw_data_per_frame, self.expected_raw_data)
        print_dec("shm_activated_fifos_list", self.shm_activated_fifos_list)
        print_dec("self.activate_show_preview", self.activate_show_preview)

        # self.data_queue["FIFO"] = self.data_queue["FIFO"]
        # self.shm_loc_acquired["FIFO"] = self.shm_loc_acquired["FIFO"]

        self.shared_dict_proxy = {}

        self.update_dictionary_slowly(0.1)

        #This seams redundant but it is for optimize the performances
        channels = self.channels
        channels_y = int(sqrt(self.channels))
        channels_x = channels_y
        print("Channels ", channels, channels_x, channels_y)

        if channels == 25:
            converter = convertRawDataToCountsDirect
        if channels == 49:
            converter = convertRawDataToCountsDirect49
        print_dec("SHAPE before while", self.shape )
        while not self.stop_event.is_set():
            selected_channel = self.shared_dict["channel"]

            if self.activate_preview:
                self.shm_number_of_threads_h5.value = -1

            self.shared_dict_proxy["FIFO_status"] = self.data_queue["FIFO"].qsize()
            self.shared_dict_proxy["FIFOAnalog_status"] = self.data_queue[
                "FIFOAnalog"
            ].qsize()

            if "FIFO" in self.shm_activated_fifos_list:
                max_gap_frame = self.expected_raw_data_per_frame * (
                    self.current_frame + 1
                )

                if not self.data_queue["FIFO"].empty():
                    if (
                        internal_buffer is not None
                    ):  # if the previous queue data was between two frames
                        print_dec(
                            len(internal_buffer),
                            max_gap_frame - (self.current_pointer * self.DATA_WORDS_DIGITAL),
                            max_gap_frame,
                            (self.current_pointer * self.DATA_WORDS_DIGITAL),
                        )
                        if max_gap_frame - (self.current_pointer * self.DATA_WORDS_DIGITAL) == 0:
                            self.gap = 0
                            internal_buffer = None
                        else:
                            data_from_queue = internal_buffer[
                                : max_gap_frame - (self.current_pointer * self.DATA_WORDS_DIGITAL)
                            ]
                            self.gap = data_from_queue.shape[0] // self.DATA_WORDS_DIGITAL
                            internal_buffer = internal_buffer[
                                max_gap_frame - (self.current_pointer * self.DATA_WORDS_DIGITAL) :
                            ]

                    if (
                        internal_buffer is None
                    ):  # standard case (no previous split data)
                        data_from_queue = self.data_queue["FIFO"].get()
                        self.gap = data_from_queue.shape[0] // self.DATA_WORDS_DIGITAL
                        #
                        # print_dec(
                        #     None,
                        #     len(data_from_queue),
                        #     (self.current_pointer + self.gap) * self.DATA_WORDS_DIGITAL - max_gap_frame,
                        # )
                        if (self.current_pointer + self.gap) * self.DATA_WORDS_DIGITAL >= max_gap_frame:
                            print_dec(
                                " c ",
                                (self.current_pointer + self.gap) * self.DATA_WORDS_DIGITAL,
                                self.gap,
                                max_gap_frame,
                            )
                            print_dec(
                                data_from_queue.shape,
                                max_gap_frame - (self.current_pointer * self.DATA_WORDS_DIGITAL),
                            )

                            internal_buffer = data_from_queue[
                                max_gap_frame - (self.current_pointer * self.DATA_WORDS_DIGITAL) :
                            ]
                            data_from_queue = data_from_queue[
                                : max_gap_frame - (self.current_pointer * self.DATA_WORDS_DIGITAL)
                            ]
                            self.gap = data_from_queue.shape[0] // self.DATA_WORDS_DIGITAL

                            frameComplete["FIFO"] = True

                            self.current_frame += 1

                    if internal_buffer is not None:
                        if internal_buffer.size == 0:
                            print_dec("internal_buffer.size == 0")
                            internal_buffer = None


                    if self.expected_raw_data < (self.current_pointer + self.gap) * self.DATA_WORDS_DIGITAL:
                        self.gap = max_gap_frame // self.DATA_WORDS_DIGITAL - self.current_pointer
                        print_dec("MISTERY!!!")
                        print_dec("New GAP", self.gap)

                    if self.snake_walk == True:
                        list_pointer = np.arange(
                            self.current_pointer, self.current_pointer + self.gap
                        )
                        list_pixel = list_pointer // self.timebinsPerPixel
                        list_b = list_pointer % self.timebinsPerPixel
                        list_x = list_pixel % self.shape[0]
                        list_y = (list_pixel // self.shape[0]) % self.shape[1]
                        list_x = list_x + (list_y % 2) * (
                            -2 * list_x + self.shape[0] - 1
                        )
                        list_z = (
                            list_pixel
                            // (self.shape[0] * self.shape[1])
                            % self.shape[2]
                        )
                    else:
                        list_pointer = np.arange(
                            self.current_pointer, self.current_pointer + self.gap
                        )
                        list_pixel = list_pointer // self.timebinsPerPixel
                        list_b = list_pointer % self.timebinsPerPixel
                        list_x = list_pixel % self.shape[0]
                        list_y = (list_pixel // self.shape[0]) % self.shape[1]
                        list_z = (
                            list_pixel
                            // (self.shape[0] * self.shape[1])
                            % self.shape[2]
                        )

                    if self.gap > self.buffer_size:
                        print_dec(
                            "ERROR: Too many data larger than the buffer. GAP",
                            self.gap,
                            "buffer_size",
                            self.buffer_size,
                        )

                    self.saturation[:] = 0

                    print("data_from_queue", data_from_queue.shape)
                    print("self.gap * self.DATA_WORDS_DIGITAL", self.gap * self.DATA_WORDS_DIGITAL)
                    print("self.buffer", self.buffer.shape)
                    print("self.buffer_sum_SPAD_ch", self.buffer_sum_SPAD_ch.shape)
                    print("self.saturation", self.saturation.shape)
                    print("self.fingerprint_mask", self.fingerprint_mask.shape)

                    if (
                        converter(
                            data_from_queue,
                            0,
                            self.gap * self.DATA_WORDS_DIGITAL,
                            self.buffer,
                            self.buffer_sum_SPAD_ch,
                            self.saturation,
                            self.fingerprint_mask,
                        )
                        == -1
                    ):
                        print_dec(
                            "==============DISASTER IN THE PREVIEW====================="
                        )


                    buffer_up_to_gap = self.buffer[: self.gap]


                    if isinstance(selected_channel, int):
                        if self.activate_show_preview == True:
                            self.image_xy_lock.acquire()
                            self.image_xy[list_y, list_x] = 0
                            np.add.at(
                                self.image_xy,
                                (list_y, list_x),
                                buffer_up_to_gap[:, selected_channel],
                            )
                            self.image_xy_lock.release()

                            cond_x_central = list_x == (self.shape[0] // 2)
                            self.image_zy_lock.acquire()
                            self.image_zy[
                                list_y[cond_x_central], list_z[cond_x_central]
                            ] = 0
                            np.add.at(
                                self.image_zy,
                                (list_y[cond_x_central], list_z[cond_x_central]),
                                buffer_up_to_gap[cond_x_central, selected_channel],
                            )
                            self.image_zy_lock.release()

                            cond_y_central = list_y == (self.shape[1] // 2)
                            self.image_xz_lock.acquire()
                            self.image_xz[
                                list_z[cond_y_central], list_x[cond_y_central]
                            ] = 0
                            np.add.at(
                                self.image_xz,
                                (list_z[cond_y_central], list_x[cond_y_central]),
                                buffer_up_to_gap[cond_y_central, selected_channel],
                            )
                            self.image_xz_lock.release()

                        if self.active_autocorrelation:
                            correlator.add(buffer_up_to_gap[:, selected_channel])
                            self.autocorrelation[
                                1, :
                            ] = correlator.get_correlation_normalized()
                        if self.activate_trace:
                            temporalBinner.add(buffer_up_to_gap[:, selected_channel])
                            self.trace_pos.value = (
                                temporalBinner.get_current_position_bins()
                            )
                            self.trace[1, :] = temporalBinner.get_bins()

                    elif selected_channel.startswith("Sum"):
                        if self.activate_show_preview == True:
                            self.image_xy_lock.acquire()
                            self.image_xy[list_y, list_x] = 0
                            np.add.at(
                                self.image_xy,
                                (list_y, list_x),
                                self.buffer_sum_SPAD_ch[: self.gap],
                            )
                            self.image_xy_lock.release()

                            cond_x_central = list_x == (self.shape[0] // 2)
                            self.image_zy_lock.acquire()
                            self.image_zy[
                                list_y[cond_x_central], list_z[cond_x_central]
                            ] = 0
                            np.add.at(
                                self.image_zy,
                                (list_y[cond_x_central], list_z[cond_x_central]),
                                self.buffer_sum_SPAD_ch[: self.gap][cond_x_central],
                            )
                            self.image_zy_lock.release()

                            cond_y_central = list_y == (self.shape[1] // 2)
                            self.image_xz_lock.acquire()
                            self.image_xz[
                                list_z[cond_y_central], list_x[cond_y_central]
                            ] = 0
                            np.add.at(
                                self.image_xz,
                                (list_z[cond_y_central], list_x[cond_y_central]),
                                self.buffer_sum_SPAD_ch[: self.gap][cond_y_central],
                            )
                            self.image_xz_lock.release()

                        if self.active_autocorrelation:
                            correlator.add(self.buffer_sum_SPAD_ch[: self.gap])
                            self.autocorrelation[
                                1, :
                            ] = correlator.get_correlation_normalized()
                        if self.activate_trace:
                            temporalBinner.add(self.buffer_sum_SPAD_ch[: self.gap])
                            self.trace_pos.value = (
                                temporalBinner.get_current_position_bins()
                            )
                            self.trace[1, :] = temporalBinner.get_bins()

                    elif selected_channel.startswith("RGB"):
                        if self.activate_show_preview == True:
                            channelA = int(selected_channel.split(" ")[1])
                            channelB = int(selected_channel.split(" ")[2])
                            channelC = int(selected_channel.split(" ")[3])

                            self.image_xy_rgb_lock.acquire()
                            self.image_xy_rgb[list_y, list_x, 0] = 0
                            self.image_xy_rgb[list_y, list_x, 1] = 0
                            self.image_xy_rgb[list_y, list_x, 2] = 0

                            np.add.at(
                                self.image_xy_rgb[:, :, 0],
                                (list_y, list_x),
                                buffer_up_to_gap[:, channelA],
                            )
                            np.add.at(
                                self.image_xy_rgb[:, :, 1],
                                (list_y, list_x),
                                buffer_up_to_gap[:, channelB],
                            )
                            np.add.at(
                                self.image_xy_rgb[:, :, 2],
                                (list_y, list_x),
                                buffer_up_to_gap[:, channelC],
                            )
                            self.image_xy_rgb_lock.release()

                        if self.active_autocorrelation:
                            correlator.add(self.buffer_sum_SPAD_ch[: self.gap])
                            self.autocorrelation[
                                1, :
                            ] = correlator.get_correlation_normalized()
                        if self.activate_trace:
                            temporalBinner.add(self.buffer_sum_SPAD_ch[: self.gap])
                            self.trace_pos.value = (
                                temporalBinner.get_current_position_bins()
                            )
                            self.trace[1, :] = temporalBinner.get_bins()

                    if not self.activate_preview:
                        # This is for debug purpose
                        # np.add.at(self.buffer_for_save, (list_y, list_x, list_b),
                        #           buffer_up_to_gap[:,:channels])
                        # np.add.at(self.buffer_for_save_channels_extra, (list_y, list_x, list_b),
                        #           buffer_up_to_gap[:,channels:])

                        self.buffer_for_save[
                            list_y, list_x, list_b, :
                        ] = buffer_up_to_gap[:, :channels]
                        self.buffer_for_save_channels_extra[
                            list_y, list_x, list_b, :
                        ] = buffer_up_to_gap[:, channels:]

                        print_dec(
                            self.current_pointer,
                            self.current_pointer + self.gap,
                            self.buffer.shape,
                            buffer_up_to_gap.shape,
                        )
                        # print(self.buffer.shape , buffer_up_to_gap.shape, list_y.shape)
                        print_dec(
                            self.current_frame,
                            self.gap,
                            list_y.max(),
                            list_x.max(),
                            list_b.max(),
                        )

                    sum_tmp = buffer_up_to_gap[:, :channels].sum(axis=0).reshape(channels_x, channels_y)

                    self.total_photon = np.sum(sum_tmp)

                    self.fingerprint[0, :, :] += sum_tmp
                    try:
                        self.fingerprint[1, :, :] = buffer_up_to_gap[-1, :channels].reshape(
                            channels_x, channels_y
                        )
                    except:
                        print_dec("buffer_up_to_gap", buffer_up_to_gap)
                        self.fingerprint[1, :, :] = 0

                    if self.gap > 10000:
                        self.fingerprint[2, :, :] = (
                            self.buffer[:10000, :channels].sum(axis=0).reshape(channels_x, channels_y)
                        )

                    self.fingerprint[4, :, :] += self.saturation[:channels].reshape(channels_x, channels_y)
                    self.current_pointer += self.gap
                    self.shm_loc_previewed["FIFO"].value = self.current_pointer
                    # print_dec(self.current_pointer*2, self.gap*2, (self.current_pointer + self.gap)*2)

                    if frameComplete["FIFO"]:
                        frameComplete["FIFO"] = False
                        self.fingerprint[3, :, :] = self.fingerprint[0, :, :]
                        self.fingerprint[0, :, :] = 0
                        self.fingerprint[1, :, :] = 0
                        self.fingerprint[2, :, :] = 0
                        self.fingerprint[4, :, :] = 0

                        current_z = (self.current_frame - 1) % self.shape[2]
                        current_rep = (self.current_frame - 1) // self.shape[2]
                        print_dec("FRAME ", current_z, current_rep, " DONE")

                        self.shared_dict_proxy.update(
                            {
                                "current_z": current_z,
                                "current_rep": current_rep,
                                "total_photon": self.total_photon,
                                "last_packet_size": self.gap,
                            }
                        )

                        if not self.activate_preview:
                            self.h5mgr.add_to_dataset(
                                "data",
                                np.copy(self.buffer_for_save),
                                current_rep,
                                current_z,
                            )
                            self.h5mgr.add_to_dataset(
                                "data_channels_extra",
                                np.copy(self.buffer_for_save_channels_extra),
                                current_rep,
                                current_z,
                            )
                            self.buffer_for_save[:] = 0
                            self.buffer_for_save_channels_extra[:] = 0
                            print_dec("done add_to_dataset")
                            print_dec(self.current_pointer * self.DATA_WORDS_DIGITAL)

                    if self.current_pointer * self.DATA_WORDS_DIGITAL >= self.expected_raw_data:
                        self.stop_event.set()

            if "FIFOAnalog" in self.shm_activated_fifos_list:
                if not self.data_queue["FIFOAnalog"].empty():
                    max_gap_frame = (self.expected_raw_data_per_frame) * (
                        self.current_frame + 1
                    )

                    if (
                        internal_buffer_analog is not None
                    ):  # if the previous queue data was between two frames
                        # data_from_queue = internal_buffer_analog
                        # self.gap_analog = data_from_queue.shape[0]
                        # internal_buffer_analog = None
                        #
                        data_from_queue = internal_buffer_analog[
                            : max_gap_frame - self.current_pointer
                        ]
                        self.gap_analog = data_from_queue.shape[0] // 2
                        internal_buffer_analog = internal_buffer_analog[
                            max_gap_frame - self.current_pointer :
                        ]

                    else:  # standard case (no previous split data)
                        data_from_queue = self.data_queue["FIFOAnalog"].get()
                        self.gap_analog = data_from_queue.shape[0]
                        # in the case the current queue data overflow in the next frame the data are split

                        # max_gap_frame = self.expected_raw_data_per_frame * (self.current_frame+1)
                        # if (self.current_pointer + self.gap) * self.DATA_WORDS_ANALOG  >= max_gap_frame:
                        #     print_dec(" c ", (self.current_pointer + self.gap) * self.DATA_WORDS_ANALOG,
                        #           max_gap_frame)
                        #     print(data_from_queue.shape, max_gap_frame-(self.current_pointer*2))
                        #
                        #     internal_buffer = data_from_queue[max_gap_frame - (self.current_pointer * self.DATA_WORDS_ANALOG):]
                        #     data_from_queue = data_from_queue[:max_gap_frame - (self.current_pointer * self.DATA_WORDS_ANALOG)]

                        if (
                            self.current_pointer_analog + self.gap_analog
                        ) *2 >= max_gap_frame:
                            print_dec(
                                " c ",
                                (self.current_pointer_analog + self.gap_analog),
                                max_gap_frame,
                            )

                            internal_buffer_analog = data_from_queue[
                                max_gap_frame - self.current_pointer :
                            ]
                            self.gap_analog = data_from_queue.shape[0]
                            data_from_queue = data_from_queue[
                                : max_gap_frame - self.current_pointer
                            ]

                            frameComplete["FIFOAnalog"] = True

                            self.current_frame += 1

                    if internal_buffer_analog is not None:
                        if internal_buffer_analog.size == 0:
                            print_dec("internal_buffer_analog.size == 0")
                            internal_buffer_analog = None

                    if (
                        self.expected_raw_data
                        - (self.current_pointer_analog + self.gap_analog)
                        < 0
                    ):
                        self.gap_analog = (
                            self.expected_raw_data // 2 - self.current_pointer_analog
                        )
                        print_dec("MISTERY")
                        print_dec("New GAP", self.gap_analog)
                    #
                    # if self.snake_walk == True:
                    #     list_pointer = np.arange(self.current_pointer, self.current_pointer + self.gap)
                    #     list_pixel = list_pointer // self.timebinsPerPixel
                    #     list_b = list_pointer % self.timebinsPerPixel
                    #     list_x = list_pixel % self.shape[0]
                    #     list_y = (list_pixel // self.shape[0]) % self.shape[1]
                    #     list_x = list_x + (list_y % 2) * (-2 * list_x + self.shape[0] - 1)
                    #     list_z = list_pixel // (self.shape[0] * self.shape[1]) % self.shape[2]
                    # else:
                    #     list_pointer = np.arange(self.current_pointer, self.current_pointer + self.gap)
                    #     list_pixel = list_pointer // self.timebinsPerPixel
                    #     list_b = list_pointer % self.timebinsPerPixel
                    #     list_x = list_pixel % self.shape[0]
                    #     list_y = (list_pixel // self.shape[0]) % self.shape[1]
                    #     list_z = list_pixel // (self.shape[0] * self.shape[1]) % self.shape[2]

                    if self.snake_walk == True:
                        list_pointer_analog = np.arange(
                            self.current_pointer_analog,
                            self.current_pointer_analog + self.gap_analog,
                        )
                        list_pixel_analog = list_pointer_analog // (self.timebinsPerPixel*2)
                        list_b_analog = list_pointer_analog % (self.timebinsPerPixel *2)
                        list_x_analog = list_pixel_analog % self.shape[0]
                        list_y_analog = (
                            list_pixel_analog // self.shape[0]
                        ) % self.shape[1]
                        list_x_analog = list_x_analog + (list_y_analog % 2) * (
                            -2 * list_x_analog + self.shape[0] - 1
                        )
                        list_z_analog = (
                            list_pixel_analog
                            // (self.shape[0] * self.shape[1])
                            % self.shape[2]
                        )
                    else:
                        list_pointer_analog = np.arange(
                            self.current_pointer_analog,
                            self.current_pointer_analog + self.gap_analog,
                        )
                        list_pixel_analog = list_pointer_analog // self.timebinsPerPixel
                        list_b_analog = list_pointer_analog % self.timebinsPerPixel
                        list_x_analog = list_pixel_analog % self.shape[0]
                        list_y_analog = (
                            list_pixel_analog // self.shape[0]
                        ) % self.shape[1]
                        list_z_analog = (
                            list_pixel_analog
                            // (self.shape[0] * self.shape[1])
                            % self.shape[2]
                        )

                    self.shared_dict_proxy["last_packet_size"] = self.gap_analog
                    if self.gap_analog > self.buffer_size:
                        print_dec(
                            "Too many data larger than the buffer. GAP",
                            self.gap_analog,
                            "buffer_size",
                            self.buffer_size,
                        )
                    if (
                        convertDataFromAnalogFIFO(
                            data_from_queue,
                            0,
                            self.gap_analog,
                            self.buffer_analog,
                            force_positive=0,
                        )
                        == -1
                    ):
                        print_dec(
                            "==============DISASTER IN THE PREVIEW====================="
                        )

                    buffer_up_to_gap = self.buffer_analog[: self.gap_analog]

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
                                buffer_up_to_gap[:, analog_ch],
                            )
                            self.image_xy_lock.release()

                            cond_x_central = list_x_analog == (self.shape[0] // 2)
                            self.image_zy_lock.acquire()
                            self.image_zy[list_y_analog[cond_x_central], list_z_analog[cond_x_central]] = 0
                            np.add.at(
                                self.image_zy,
                                (list_y_analog[cond_x_central], list_z_analog[cond_x_central]),
                                buffer_up_to_gap[:, analog_ch][cond_x_central],
                            )
                            self.image_zy_lock.release()

                            cond_y_central = list_y_analog == (self.shape[0] // 2)
                            self.image_xz_lock.acquire()
                            self.image_xz[list_z_analog[cond_y_central], list_x_analog[cond_y_central]] = 0
                            np.add.at(
                                self.image_xz,
                                (list_z_analog[cond_y_central], list_x_analog[cond_y_central]),
                                buffer_up_to_gap[:, analog_ch][cond_y_central],
                            )
                            self.image_xz_lock.release()

                        if self.active_autocorrelation:
                            correlator.add(buffer_up_to_gap[:, analog_ch])
                            self.autocorrelation[
                                1, :
                            ] = correlator.get_correlation_normalized()
                        if self.activate_trace:
                            temporalBinner.add(buffer_up_to_gap[:, analog_ch])
                            self.trace_pos.value = (
                                temporalBinner.get_current_position_bins()
                            )
                            self.trace[1, :] = temporalBinner.get_bins()

                    if not self.activate_preview:
                        self.buffer_analog_for_save[
                            list_y_analog, list_x_analog, list_b_analog, :
                        ] = buffer_up_to_gap

                    self.current_pointer_analog += self.gap_analog
                    self.shm_loc_previewed[
                        "FIFOAnalog"
                    ].value = self.current_pointer_analog

                    self.shared_dict_proxy.update({"total_photon": self.total_photon})

                    if frameComplete["FIFOAnalog"]:
                        frameComplete["FIFOAnalog"] = False
                        self.fingerprint[3, :, :] = self.fingerprint[0, :, :]
                        self.fingerprint[0, :, :] = 0
                        self.fingerprint[1, :, :] = 0
                        self.fingerprint[2, :, :] = 0
                        self.fingerprint[4, :, :] = 0

                        current_z = (self.current_frame - 1) % self.shape[2]
                        current_rep = (self.current_frame - 1) // self.shape[2]
                        print_dec("FRAME ", current_z, current_rep, " DONE")
                        self.shared_dict_proxy.update(
                            {
                                "current_z": current_z,
                                "current_rep": current_rep,
                                "total_photon": self.total_photon,
                            }
                        )
                        if not self.activate_preview:
                            self.h5mgr.add_to_dataset(
                                "data_analog",
                                np.copy(self.buffer_analog_for_save),
                                current_rep,
                                current_z,
                            )
                            self.buffer_analog_for_save[:] = 0
                            print_dec("done add_to_dataset")
                            print_dec(
                                self.current_pointer_analog * self.DATA_WORDS_ANALOG, self.expected_raw_data
                            )

                    if self.current_pointer_analog * self.DATA_WORDS_ANALOG >= self.expected_raw_data:
                        self.stop_event.set()

            if self.trace_reset_event.is_set():
                print_dec("trace_reset_event.is_set()")
                temporalBinner.reset()
                self.trace_reset_event.clear()
            if self.FCS_reset_event.is_set():
                correlator.reset()
                self.FCS_reset_event.clear()

        # self.profiler.disable()
        # self.profiler.print_stats()
        # self.profiler.dump_stats("dumpspeed.txt")
        # self.profiler.dump_stats("cachegrind.out.prova")

        self.stop_update_dictionary_slowly()

        self.acquisition_almost_done.set()

        if not self.activate_preview:
            # self.h5file.close()
            self.h5mgr.close()
        self.acquisition_done.set()
        print_dec("Acquisition done")
        self.stop_event.clear()

        print_dec("run() acquisition_loop_process stopped")

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
            self.shared_dict.update(self.shared_dict_proxy)
            time.sleep(timeout)
            # print("updated")

    def stop_update_dictionary_slowly(self):
        self.thread_for_dict_stop.set()
