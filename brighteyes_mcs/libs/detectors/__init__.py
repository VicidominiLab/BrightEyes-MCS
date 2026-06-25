"""Detector-specific acquisition pipelines."""

__all__ = ["create_detector_pipeline"]


def create_detector_pipeline(detector_model):
    from .common import create_detector_pipeline as _create_detector_pipeline

    return _create_detector_pipeline(detector_model)

