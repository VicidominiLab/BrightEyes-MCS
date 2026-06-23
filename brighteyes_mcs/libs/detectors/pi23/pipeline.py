"""PI23 acquisition pipeline scaffold."""

import multiprocessing as mp

from ...processes.pi23_acquisition_loop_process import Pi23AcquisitionLoopProcess
from ...processes.pi23_data_pre_process import Pi23DataPreProcess
from ...processes.pi23_raw_stream_writer_process import Pi23RawStreamWriterProcess
from ...processes.pi23_receiver_process import Pi23ReceiverProcess


def pi23_words_per_sample(spad_channels):
    return 8 if int(spad_channels) == 49 else 2


class Pi23DetectorPipeline:
    detector_model = "PI 23"

    def make_receiver_queue(self, mcs_manager):
        return mp.Queue()

    def make_receiver_process(self, mcs_manager, receiver_queue, start_event):
        return Pi23ReceiverProcess(
            receiver_queue,
            mcs_manager.activated_fifos_list,
            start_event,
            mcs_manager.fpga_handle.configuration["fifo_chuck_size_digital"],
            mcs_manager.fpga_handle.configuration["fifo_chuck_size_analog"],
            mcs_manager.fpga_handle.configuration["expected_words_data_digital"],
            mcs_manager.fpga_handle.configuration["expected_words_data_analog"],
            digital_words_per_sample=pi23_words_per_sample(mcs_manager.spad_channels),
            digital_output_channels=mcs_manager.spad_channels,
            debug=mcs_manager.debug,
        )

    def make_data_preprocess(self, mcs_manager, receiver_queue):
        return Pi23DataPreProcess(
            receiver_queue,
            mcs_manager.loc_acquired,
            mcs_manager.last_preprocessed_len,
            mcs_manager.data_queue,
            mcs_manager.dtype_data_queue,
            digital_words_per_sample=pi23_words_per_sample(mcs_manager.spad_channels),
            debug=mcs_manager.debug,
        )

    def make_acquisition_loop(self, mcs_manager, do_not_save):
        return Pi23AcquisitionLoopProcess(
            mcs_manager.spad_channels,
            mcs_manager.shared_objects,
            do_not_save,
            mcs_manager.data_queue,
            mcs_manager.acquisition_done_event,
            mcs_manager.acquisition_almost_done_event,
            mcs_manager.shared_dict,
            debug=mcs_manager.debug,
        )

    def make_raw_stream_writer(self, mcs_manager, receiver_queue):
        return Pi23RawStreamWriterProcess(
            receiver_queue,
            mcs_manager.activated_fifos_list,
            mcs_manager.raw_output_files,
            mcs_manager.loc_acquired,
            mcs_manager.loc_previewed,
            mcs_manager.last_preprocessed_len,
            mcs_manager.acquisition_done_event,
            mcs_manager.acquisition_almost_done_event,
            mcs_manager.shared_dict,
            digital_words_per_sample=pi23_words_per_sample(mcs_manager.spad_channels),
            debug=mcs_manager.debug,
        )

