"""Timestamp scan control without the PISPAD23 intensity receiver or decoder.

PISPAD23Timetagging configures the library worker or the legacy executable.
Only the selected timestamp backend connects to the device endpoint; MCS must
never start PISPAD23ReceiverProcess or send CS in this mode.
"""

from ..disabled import DisabledDetectorPipeline
from ..models import DETECTOR_PISPAD23_TS_UIMG
from .microimage_worker import MicroimageWorker
from .library_worker import LibraryMicroimageWorker


class PISPAD23MicroimagePipeline(DisabledDetectorPipeline):
    """Completed dwell batches processed outside the GUI, without a CS receiver."""

    detector_model = DETECTOR_PISPAD23_TS_UIMG

    def make_acquisition_loop(self, acquisition, do_not_save):
        saving = None
        if not do_not_save:
            saving = dict(filename=acquisition.filenameh5, frames=acquisition.dim_z,
                          repetitions=acquisition.dim_rep,
                          dwell_seconds=acquisition.time_resolution * acquisition.timebins_per_pixel
                          * acquisition.circ_points * acquisition.circ_repetition * 1e-6,
                          snake_z=acquisition.shared_dict.get("snake_walk_z", False))
        if getattr(acquisition, "pispad23_backend", "Python library") == "Python library":
            self.worker = LibraryMicroimageWorker(
                acquisition.dim_x, acquisition.dim_y,
                getattr(acquisition, "pispad23_batch_size", 4096),
                acquisition.shared_objects, acquisition.shared_dict,
                snake=acquisition.shared_dict.get("snake_walk_xy", False), saving=saving,
            )
            return self.worker
        self.worker = MicroimageWorker(
            acquisition.dim_x, acquisition.dim_y,
            getattr(acquisition, "pispad23_stream_port", 19000),
            getattr(acquisition, "pispad23_batch_size", 4096),
            acquisition.shared_objects, acquisition.shared_dict,
            snake=acquisition.shared_dict.get("snake_walk_xy", False),
            saving=saving,
        )
        return self.worker
