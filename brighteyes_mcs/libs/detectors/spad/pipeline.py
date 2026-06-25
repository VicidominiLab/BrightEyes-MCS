"""SPAD Array acquisition pipeline."""

<<<<<<< HEAD
from ...processes.spad.acquisition_loop_process import SpadAcquisitionLoopProcess
from ...processes.spad.data_pre_process import SpadDataPreProcess
from ...processes.spad.raw_stream_writer_process import SpadRawStreamWriterProcess
=======
from ...processes.spad_acquisition_loop_process import SpadAcquisitionLoopProcess
from ...processes.spad_data_pre_process import SpadDataPreProcess
from ...processes.spad_raw_stream_writer_process import SpadRawStreamWriterProcess
>>>>>>> 619fdf7fdf53bf0ecff498d62b7597014e19b4f1


class SpadDetectorPipeline:
    detector_model = "SPAD Array"

    def make_receiver_queue(self, mcs_manager):
        return mcs_manager.fpga_handle.configuration["queueFifoRead"]

    def make_receiver_process(self, mcs_manager, receiver_queue, start_event):
        return None

    def make_data_preprocess(self, mcs_manager, receiver_queue):
        return SpadDataPreProcess(
            receiver_queue,
            mcs_manager.loc_acquired,
            mcs_manager.last_preprocessed_len,
            mcs_manager.data_queue,
            mcs_manager.dtype_data_queue,
            len_buffer=mcs_manager.fifo_prebuffer_length,
            debug=mcs_manager.debug,
            use_rust_fifo=mcs_manager.use_rust_fifo,
        )

    def make_acquisition_loop(self, mcs_manager, do_not_save):
        return SpadAcquisitionLoopProcess(
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
        return SpadRawStreamWriterProcess(
            receiver_queue,
            mcs_manager.activated_fifos_list,
            mcs_manager.raw_output_files,
            mcs_manager.loc_acquired,
            mcs_manager.loc_previewed,
            mcs_manager.last_preprocessed_len,
            mcs_manager.acquisition_done_event,
            mcs_manager.acquisition_almost_done_event,
            mcs_manager.shared_dict,
            debug=mcs_manager.debug,
        )

