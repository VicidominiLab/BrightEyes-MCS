"""Timestamp scan control without the PI23 intensity receiver or decoder.

Pi23Timetagging owns the external Rust process and receives its image stream
(port 19000 by default). Only Rust connects to the device's timestamp endpoint;
MCS must never start Pi23ReceiverProcess or send CS in this mode.
"""

from ..disabled import DisabledDetectorPipeline
from ..models import DETECTOR_PI23_TS, DETECTOR_PI23_TS_UIMG
from .microimage_worker import MicroimageWorker


class Pi23TimestampPipeline(DisabledDetectorPipeline):
    detector_model = DETECTOR_PI23_TS


class Pi23MicroimagePipeline(DisabledDetectorPipeline):
    """Buffered READ batches processed outside the GUI, without a CS receiver."""

    detector_model = DETECTOR_PI23_TS_UIMG

    def make_acquisition_loop(self, acquisition, do_not_save):
        saving = None
        if not do_not_save:
            saving = dict(filename=acquisition.filenameh5, frames=acquisition.dim_z,
                          repetitions=acquisition.dim_rep,
                          dwell_seconds=acquisition.time_resolution * acquisition.timebins_per_pixel
                          * acquisition.circ_points * acquisition.circ_repetition * 1e-6,
                          snake_z=acquisition.shared_dict.get("snake_walk_z", False))
        self.worker = MicroimageWorker(
            acquisition.dim_x, acquisition.dim_y,
            getattr(acquisition, "pi23_stream_port", 19000),
            getattr(acquisition, "pi23_batch_size", 4096),
            acquisition.shared_objects, acquisition.shared_dict,
            snake=acquisition.shared_dict.get("snake_walk_xy", False),
            saving=saving,
        )
        return self.worker
