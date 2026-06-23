"""Detector model constants and shared detector selection helpers."""

from __future__ import annotations


DETECTOR_SPAD_ARRAY = "SPAD Array"
DETECTOR_PI_23 = "PI 23"
DETECTOR_MODELS = (DETECTOR_SPAD_ARRAY, DETECTOR_PI_23)


def normalize_detector_model(detector_model):
    """Return a supported detector model string, defaulting old configs to SPAD."""
    if detector_model in DETECTOR_MODELS:
        return detector_model
    return DETECTOR_SPAD_ARRAY


def detector_uses_nifpga_fifo(detector_model):
    """True when detector data is received from NI FPGA FIFOs."""
    return normalize_detector_model(detector_model) == DETECTOR_SPAD_ARRAY


def detector_uses_nifpga_control(detector_model):
    """True when scan/control registers are driven through an NI FPGA session."""
    return normalize_detector_model(detector_model) in DETECTOR_MODELS
