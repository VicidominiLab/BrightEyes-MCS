"""Detector-specific acquisition pipelines."""

<<<<<<< HEAD
__all__ = ["create_detector_pipeline"]


def create_detector_pipeline(detector_model):
    from .common import create_detector_pipeline as _create_detector_pipeline

    return _create_detector_pipeline(detector_model)

=======
from .common import create_detector_pipeline

__all__ = ["create_detector_pipeline"]

>>>>>>> 619fdf7fdf53bf0ecff498d62b7597014e19b4f1
