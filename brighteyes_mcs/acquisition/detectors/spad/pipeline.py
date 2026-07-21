"""SPAD Array acquisition pipeline."""

from ...workers.detectors.spad.acquisition_loop import SpadAcquisitionLoopProcess
from ...workers.detectors.spad.preprocessor import SpadDataPreProcess
from ...workers.detectors.spad.raw_writer import SpadRawStreamWriterProcess


class SpadDetectorPipeline:
    detector_model = "SPAD Array"

    def __init__(self, detector_model=None):
        if detector_model is not None:
            self.detector_model = detector_model

    def make_receiver_queue(self, acquisition):
        return acquisition.fpga_handle.configuration["queueFifoRead"]

    def make_receiver_process(self, acquisition, receiver_queue, start_event):
        return None

    def make_data_preprocess(self, acquisition, receiver_queue):
        return SpadDataPreProcess(
            receiver_queue, acquisition.loc_acquired, acquisition.last_preprocessed_len,
            acquisition.data_queue, acquisition.dtype_data_queue,
            len_buffer=acquisition.fifo_prebuffer_length, debug=acquisition.debug,
            use_rust_fifo=acquisition.use_rust_fifo,
        )

    def make_acquisition_loop(self, acquisition, do_not_save):
        return SpadAcquisitionLoopProcess(
            acquisition.spad_channels, acquisition.shared_objects, do_not_save,
            acquisition.data_queue, acquisition.acquisition_done_event,
            acquisition.acquisition_almost_done_event, acquisition.shared_dict,
            debug=acquisition.debug,
        )

    def make_raw_stream_writer(self, acquisition, receiver_queue):
        return SpadRawStreamWriterProcess(
            receiver_queue, acquisition.activated_fifos_list, acquisition.raw_output_files,
            acquisition.loc_acquired, acquisition.loc_previewed, acquisition.last_preprocessed_len,
            acquisition.acquisition_done_event, acquisition.acquisition_almost_done_event,
            acquisition.shared_dict, debug=acquisition.debug,
        )
