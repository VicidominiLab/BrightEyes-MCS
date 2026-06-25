"""Backward-compatible detector backend imports."""

from .detectors.models import (
    DETECTOR_MODELS,
    DETECTOR_PI_23,
    DETECTOR_SPAD_ARRAY,
    detector_uses_nifpga_control,
    detector_uses_nifpga_fifo,
    normalize_detector_model,
)
from .detectors.pi23.backend import (
    Pi23RandomBunchSource,
    Pi23RawBunch,
    Pi23TcpBunchSource,
    pi23_decode_raw_bunch_to_spad_preview_words,
    pi23_pack_counts_to_spad25_words,
)

__all__ = [
    "DETECTOR_MODELS",
    "DETECTOR_PI_23",
    "DETECTOR_SPAD_ARRAY",
    "Pi23RandomBunchSource",
    "Pi23RawBunch",
    "Pi23TcpBunchSource",
    "detector_uses_nifpga_control",
    "detector_uses_nifpga_fifo",
    "normalize_detector_model",
    "pi23_decode_raw_bunch_to_spad_preview_words",
    "pi23_pack_counts_to_spad25_words",
]
