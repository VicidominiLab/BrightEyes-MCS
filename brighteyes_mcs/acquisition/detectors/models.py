"""Detector model names and capability predicates."""

DETECTOR_SPAD_ARRAY = "SPAD Array"
DETECTOR_PISPAD23 = "PISPAD23"
DETECTOR_SPAD_TTM = "SPAD_TTM"
DETECTOR_PISPAD23_TT = "PISPAD23TT"
DETECTOR_SPAD_UI = "FPGA - SPAD"
DETECTOR_PISPAD23_UI = "TCP/IP - PI SPAD23R (Intensity)"
DETECTOR_PISPAD23_TS_UIMG = "TCP/IP - PI SPAD23R (TS mode - uimg)"
DETECTOR_DISABLED = "Disable"

DETECTOR_SPAD_MODELS = (DETECTOR_SPAD_ARRAY, DETECTOR_SPAD_TTM)
DETECTOR_PISPAD23_MODELS = (DETECTOR_PISPAD23, DETECTOR_PISPAD23_TT)
DETECTOR_PISPAD23_TS_MODELS = (DETECTOR_PISPAD23_TS_UIMG,)
DETECTOR_MODELS = DETECTOR_SPAD_MODELS + DETECTOR_PISPAD23_MODELS + DETECTOR_PISPAD23_TS_MODELS + (DETECTOR_DISABLED,)


def normalize_detector_model(detector_model):
    if detector_model in DETECTOR_MODELS:
        return detector_model
    if detector_model == DETECTOR_SPAD_UI:
        return DETECTOR_SPAD_ARRAY
    if detector_model == DETECTOR_PISPAD23_UI:
        return DETECTOR_PISPAD23
    # Retired modes must not silently select SPAD hardware.
    if detector_model in ("TCP/IP - PI SPAD23R (TS mode)", "TCP/IP - PI SPAD23R (TS mode - img)"):
        return DETECTOR_DISABLED
    return DETECTOR_SPAD_ARRAY


def detector_uses_spad_pipeline(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_SPAD_MODELS


def detector_uses_pispad23_pipeline(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_PISPAD23_MODELS


def detector_uses_pispad23_timestamp(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_PISPAD23_TS_MODELS


def detector_uses_nifpga_fifo(detector_model):
    return detector_uses_spad_pipeline(detector_model)


def detector_uses_nifpga_control(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_MODELS
