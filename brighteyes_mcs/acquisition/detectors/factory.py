from .models import DETECTOR_DISABLED, DETECTOR_PI23_TS_UIMG, detector_uses_pi23_timestamp, detector_uses_pi23_pipeline, normalize_detector_model
from .disabled import DisabledDetectorPipeline
from .pi23.pipeline import Pi23DetectorPipeline
from .pi23.timestamp_pipeline import Pi23TimestampPipeline, Pi23MicroimagePipeline
from .spad.pipeline import SpadDetectorPipeline


def create_detector_pipeline(detector_model):
    detector_model = normalize_detector_model(detector_model)
    if detector_model == DETECTOR_DISABLED:
        return DisabledDetectorPipeline()
    if detector_model == DETECTOR_PI23_TS_UIMG:
        return Pi23MicroimagePipeline()
    if detector_uses_pi23_timestamp(detector_model):
        return Pi23TimestampPipeline()
    if detector_uses_pi23_pipeline(detector_model):
        return Pi23DetectorPipeline(detector_model)
    return SpadDetectorPipeline(detector_model)
