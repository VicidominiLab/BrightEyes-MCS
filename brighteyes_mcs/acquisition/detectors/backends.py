"""Backward-compatible detector backend imports."""

from .models import (
    DETECTOR_MODELS,
    DETECTOR_PI23_MODELS,
    DETECTOR_PI23_TT,
    DETECTOR_PI_23,
    DETECTOR_SPAD_ARRAY,
    DETECTOR_SPAD_MODELS,
    DETECTOR_SPAD_TTM,
    detector_uses_nifpga_control,
    detector_uses_nifpga_fifo,
    detector_uses_pi23_pipeline,
    detector_uses_spad_pipeline,
    normalize_detector_model,
)
from .pi23.backend import (
    Pi23RandomBunchSource,
    Pi23RawBunch,
    Pi23TcpBunchSource,
    pi23_decode_raw_bunch_to_spad_preview_words,
    pi23_pack_counts_to_spad25_words,
)

__all__ = [
    "DETECTOR_MODELS",
    "DETECTOR_PI23_MODELS",
    "DETECTOR_PI23_TT",
    "DETECTOR_PI_23",
    "DETECTOR_SPAD_ARRAY",
    "DETECTOR_SPAD_MODELS",
    "DETECTOR_SPAD_TTM",
    "Pi23RandomBunchSource",
    "Pi23RawBunch",
    "Pi23TcpBunchSource",
    "detector_uses_nifpga_control",
    "detector_uses_nifpga_fifo",
    "detector_uses_pi23_pipeline",
    "detector_uses_spad_pipeline",
    "normalize_detector_model",
    "pi23_decode_raw_bunch_to_spad_preview_words",
    "pi23_pack_counts_to_spad25_words",
]
