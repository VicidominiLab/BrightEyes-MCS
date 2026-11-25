"""Rust-backed intensity acquisition uses the same MCS dwell processing path."""
from .timestamp_pipeline import PISPAD23MicroimagePipeline


class PISPAD23DetectorPipeline(PISPAD23MicroimagePipeline):
    detector_model = "PISPAD23"
    mode = "intensity"

    def __init__(self, detector_model=None):
        if detector_model is not None:
            self.detector_model = detector_model
