"""Detector pipeline factory."""

from .models import DETECTOR_PI_23, normalize_detector_model
from .pi23.pipeline import Pi23DetectorPipeline
from .spad.pipeline import SpadDetectorPipeline


def create_detector_pipeline(detector_model):
    detector_model = normalize_detector_model(detector_model)
    if detector_model == DETECTOR_PI_23:
        return Pi23DetectorPipeline()
    return SpadDetectorPipeline()

