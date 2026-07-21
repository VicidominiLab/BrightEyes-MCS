from .models import detector_uses_pi23_pipeline, normalize_detector_model
from .pi23.pipeline import Pi23DetectorPipeline
from .spad.pipeline import SpadDetectorPipeline


def create_detector_pipeline(detector_model):
    detector_model = normalize_detector_model(detector_model)
    if detector_uses_pi23_pipeline(detector_model):
        return Pi23DetectorPipeline(detector_model)
    return SpadDetectorPipeline(detector_model)
