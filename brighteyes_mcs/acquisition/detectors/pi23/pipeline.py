"""PI23 acquisition pipeline."""

import multiprocessing as mp
import os

from ...workers.detectors.pi23.acquisition_loop import Pi23AcquisitionLoopProcess
from ...workers.detectors.pi23.preprocessor import Pi23DataPreProcess
from ...workers.detectors.pi23.raw_writer import Pi23RawStreamWriterProcess
from ...workers.detectors.pi23.receiver import Pi23ReceiverProcess


def pi23_words_per_sample(spad_channels):
    return 2


def _pi23_active_fifos(active_fifos):
    return [fifo for fifo in active_fifos if fifo == "stream_out_main"] or ["stream_out_main"]


def _pi23_total_scan_frames(acquisition):
    return max(1, int(acquisition.dim_z))


def _pi23_dwell_us(acquisition):
    if os.environ.get("PI23_FORCE_DWELLTIME") is not None:
        acquisition.registers_configuration.get(
            "tag_clock_duration_cycles", acquisition.default_configuration.get("tag_clock_duration_cycles", 2000)
        )
    return 0


class Pi23DetectorPipeline:
    detector_model = "PI 23"

    def __init__(self, detector_model=None):
        if detector_model is not None:
            self.detector_model = detector_model

    def make_receiver_queue(self, acquisition):
        return mp.Queue()

    def make_receiver_process(self, acquisition, receiver_queue, start_event):
        active_fifos = _pi23_active_fifos(acquisition.activated_fifos_list)
        return Pi23ReceiverProcess(
            receiver_queue, active_fifos, start_event,
            acquisition.fpga_handle.configuration["fifo_chuck_size_digital"],
            acquisition.fpga_handle.configuration["fifo_chuck_size_analog"],
            acquisition.fpga_handle.configuration["expected_words_data_digital"],
            acquisition.fpga_handle.configuration["expected_words_data_analog"],
            digital_words_per_sample=pi23_words_per_sample(acquisition.spad_channels),
            digital_output_channels=25, scan_x=acquisition.dim_x, scan_y=acquisition.dim_y,
            scan_frames=_pi23_total_scan_frames(acquisition),
            timebins_per_pixel=(acquisition.timebins_per_pixel * acquisition.circ_repetition * acquisition.circ_points),
            dwell_us=_pi23_dwell_us(acquisition),
            external_frame=int(os.environ.get("PI23_IGNOREEXTERNAL_FRAME", "1")),
            host=acquisition.pi23_host, port=acquisition.pi23_port,
            shared_dict=acquisition.shared_dict, debug=acquisition.debug,
        )

    def make_data_preprocess(self, acquisition, receiver_queue):
        return Pi23DataPreProcess(
            receiver_queue, acquisition.loc_acquired, acquisition.last_preprocessed_len,
            acquisition.data_queue, acquisition.dtype_data_queue,
            digital_words_per_sample=pi23_words_per_sample(acquisition.spad_channels),
            debug=acquisition.debug,
        )

    def make_acquisition_loop(self, acquisition, do_not_save):
        acquisition.shared_objects["activated_fifos_list"] = _pi23_active_fifos(acquisition.activated_fifos_list)
        acquisition.shared_dict["spad_channels"] = 25
        return Pi23AcquisitionLoopProcess(
            25, acquisition.shared_objects, do_not_save, acquisition.data_queue,
            acquisition.acquisition_done_event, acquisition.acquisition_almost_done_event,
            acquisition.shared_dict, debug=acquisition.debug,
        )

    def make_raw_stream_writer(self, acquisition, receiver_queue):
        return Pi23RawStreamWriterProcess(
            receiver_queue, _pi23_active_fifos(acquisition.activated_fifos_list),
            acquisition.raw_output_files, acquisition.loc_acquired, acquisition.loc_previewed,
            acquisition.last_preprocessed_len, acquisition.acquisition_done_event,
            acquisition.acquisition_almost_done_event, acquisition.shared_dict,
            digital_words_per_sample=pi23_words_per_sample(acquisition.spad_channels),
            debug=acquisition.debug,
        )
