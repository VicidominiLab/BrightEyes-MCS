"""Rust microimage pipeline shared by timestamp and intensity acquisition."""

from ..disabled import DisabledDetectorPipeline
from ..models import DETECTOR_PISPAD23_TS_UIMG
from .library_worker import LibraryMicroimageWorker


class PISPAD23MicroimagePipeline(DisabledDetectorPipeline):
    """Completed dwell batches processed outside the GUI, without a CS receiver."""

    detector_model = DETECTOR_PISPAD23_TS_UIMG
    mode = "timestamp"

    def make_acquisition_loop(self, acquisition, do_not_save):
        saving = None
        if not do_not_save:
            trigger = getattr(acquisition, "software_trigger_session", None)
            saving = dict(filename=acquisition.filenameh5,
                          frames=trigger.frames if trigger else acquisition.dim_z,
                          repetitions=trigger.repetitions if trigger else acquisition.dim_rep,
                          dwell_seconds=acquisition.time_resolution * acquisition.timebins_per_pixel
                          * acquisition.circ_points * acquisition.circ_repetition * 1e-6,
                          snake_z=acquisition.shared_dict.get("snake_walk_z", False))
        self.worker = LibraryMicroimageWorker(
            acquisition.dim_x, acquisition.dim_y,
            getattr(acquisition, "pispad23_batch_size", 4096),
            acquisition.shared_objects, acquisition.shared_dict,
            snake=acquisition.shared_dict.get("snake_walk_xy", False),
            saving=saving, mode=self.mode,
            acquisition_done=getattr(acquisition, "acquisition_done_event", None),
        )
        return self.worker
