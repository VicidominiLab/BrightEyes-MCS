from .models import DETECTOR_DISABLED, DETECTOR_PISPAD23_TS_UIMG, detector_uses_pispad23_pipeline, normalize_detector_model
from .disabled import DisabledDetectorPipeline
from .pispad23.pipeline import PISPAD23DetectorPipeline
from .pispad23.timestamp_pipeline import PISPAD23MicroimagePipeline
from .spad.pipeline import SpadDetectorPipeline


def create_detector_pipeline(detector_model):
    detector_model = normalize_detector_model(detector_model)
    if detector_model == DETECTOR_DISABLED:
        return DisabledDetectorPipeline()
    if detector_model == DETECTOR_PISPAD23_TS_UIMG:
        return PISPAD23MicroimagePipeline()
    if detector_uses_pispad23_pipeline(detector_model):
        return PISPAD23DetectorPipeline(detector_model)
    return SpadDetectorPipeline(detector_model)
