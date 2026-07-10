"""PI23 acquisition pipeline scaffold."""

import multiprocessing as mp
import os

from ...processes.pi23.acquisition_loop_process import Pi23AcquisitionLoopProcess
from ...processes.pi23.data_pre_process import Pi23DataPreProcess
from ...processes.pi23.raw_stream_writer_process import Pi23RawStreamWriterProcess
from ...processes.pi23.receiver_process import Pi23ReceiverProcess


def pi23_words_per_sample(spad_channels):
    return 2


def _pi23_active_fifos(active_fifos):
    return [fifo for fifo in active_fifos if fifo == "FIFO"] or ["FIFO"]


def _pi23_total_scan_frames(mcs_manager):
    return max(1, int(mcs_manager.dim_z))


def _pi23_dwell_us(mcs_manager):
    override = os.environ.get("PI23_FORCE_DWELLTIME")
    if override is not None:
        clock_dur_ns = mcs_manager.registers_configuration.get(
            "ClockDur",
            mcs_manager.default_configuration.get("ClockDur", 2000),
        )
    return 0 #max(0.0, float(clock_dur_ns) / 1000.0)


class Pi23DetectorPipeline:
    detector_model = "PI 23"

    def __init__(self, detector_model=None):
        if detector_model is not None:
            self.detector_model = detector_model

    def make_receiver_queue(self, mcs_manager):
        return mp.Queue()

    def make_receiver_process(self, mcs_manager, receiver_queue, start_event):
        active_fifos = _pi23_active_fifos(mcs_manager.activated_fifos_list)
        return Pi23ReceiverProcess(
            receiver_queue,
            active_fifos,
            start_event,
            mcs_manager.fpga_handle.configuration["fifo_chuck_size_digital"],
            mcs_manager.fpga_handle.configuration["fifo_chuck_size_analog"],
            mcs_manager.fpga_handle.configuration["expected_words_data_digital"],
            mcs_manager.fpga_handle.configuration["expected_words_data_analog"],
            digital_words_per_sample=pi23_words_per_sample(mcs_manager.spad_channels),
            digital_output_channels=25,
            scan_x=mcs_manager.dim_x,
            scan_y=mcs_manager.dim_y,
            scan_frames=_pi23_total_scan_frames(mcs_manager),
            timebins_per_pixel=(
                mcs_manager.timebins_per_pixel
                * mcs_manager.circ_repetition
                * mcs_manager.circ_points
            ),
            dwell_us=_pi23_dwell_us(mcs_manager),
            external_frame=int(os.environ.get("PI23_IGNOREEXTERNAL_FRAME", "1")),
            host=mcs_manager.pi23_host,
            port=mcs_manager.pi23_port,
            shared_dict=mcs_manager.shared_dict,
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
        mcs_manager.shared_objects["activated_fifos_list"] = _pi23_active_fifos(
            mcs_manager.activated_fifos_list
        )
        mcs_manager.shared_dict["spad_channels"] = 25
        return Pi23AcquisitionLoopProcess(
            25,
            mcs_manager.shared_objects,
            do_not_save,
            mcs_manager.data_queue,
            mcs_manager.acquisition_done_event,
            mcs_manager.acquisition_almost_done_event,
            mcs_manager.shared_dict,
            debug=mcs_manager.debug,
        )

    def make_raw_stream_writer(self, mcs_manager, receiver_queue):
        active_fifos = _pi23_active_fifos(mcs_manager.activated_fifos_list)
        return Pi23RawStreamWriterProcess(
            receiver_queue,
            active_fifos,
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

