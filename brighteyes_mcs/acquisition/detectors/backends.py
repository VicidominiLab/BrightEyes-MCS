"""Backward-compatible detector backend imports."""

from .models import (
    DETECTOR_MODELS,
    DETECTOR_PISPAD23_MODELS,
    DETECTOR_PISPAD23_TT,
    DETECTOR_PISPAD23,
    DETECTOR_SPAD_ARRAY,
    DETECTOR_SPAD_MODELS,
    DETECTOR_SPAD_TTM,
    detector_uses_nifpga_control,
    detector_uses_nifpga_fifo,
    detector_uses_pispad23_pipeline,
    detector_uses_spad_pipeline,
    normalize_detector_model,
)
__all__ = [
    "DETECTOR_MODELS",
    "DETECTOR_PISPAD23_MODELS",
    "DETECTOR_PISPAD23_TT",
    "DETECTOR_PISPAD23",
    "DETECTOR_SPAD_ARRAY",
    "DETECTOR_SPAD_MODELS",
    "DETECTOR_SPAD_TTM",
    "detector_uses_nifpga_control",
    "detector_uses_nifpga_fifo",
    "detector_uses_pispad23_pipeline",
    "detector_uses_spad_pipeline",
    "normalize_detector_model",
]
