"""Detector pipeline factory."""

<<<<<<< HEAD
from .models import DETECTOR_PI_23, normalize_detector_model
=======
from ..detector_backends import DETECTOR_PI_23, normalize_detector_model
>>>>>>> 619fdf7fdf53bf0ecff498d62b7597014e19b4f1
from .pi23.pipeline import Pi23DetectorPipeline
from .spad.pipeline import SpadDetectorPipeline


def create_detector_pipeline(detector_model):
    detector_model = normalize_detector_model(detector_model)
    if detector_model == DETECTOR_PI_23:
        return Pi23DetectorPipeline()
    return SpadDetectorPipeline()

