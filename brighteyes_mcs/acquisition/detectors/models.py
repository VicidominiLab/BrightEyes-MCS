"""Detector model names and capability predicates."""

DETECTOR_SPAD_ARRAY = "SPAD Array"
DETECTOR_PI_23 = "PI 23"
DETECTOR_SPAD_TTM = "SPAD_TTM"
DETECTOR_PI23_TT = "PI23TT"
DETECTOR_SPAD_UI = "FPGA - SPAD"
DETECTOR_PI23_UI = "TCP/IP - PI23 (Intesity)"
DETECTOR_PI23_TS = "TCP/IP - PI23 (TS mode - img)"
DETECTOR_PI23_TS_UIMG = "TCP/IP - PI23 (TS mode - uimg)"
DETECTOR_DISABLED = "Disable"

DETECTOR_SPAD_MODELS = (DETECTOR_SPAD_ARRAY, DETECTOR_SPAD_TTM)
DETECTOR_PI23_MODELS = (DETECTOR_PI_23, DETECTOR_PI23_TT)
DETECTOR_PI23_TS_MODELS = (DETECTOR_PI23_TS, DETECTOR_PI23_TS_UIMG)
DETECTOR_MODELS = DETECTOR_SPAD_MODELS + DETECTOR_PI23_MODELS + DETECTOR_PI23_TS_MODELS + (DETECTOR_DISABLED,)
DETECTOR_MODEL_ALIASES = {
    "SPAD": DETECTOR_SPAD_ARRAY,
    "PI23": DETECTOR_PI_23,
    "TCP/IP - PI23": DETECTOR_PI_23,
    "TCP/IP - PI23 (Intensity)": DETECTOR_PI_23,
    "TCP/IP - PI23 (TS mode)": DETECTOR_PI23_TS,
    DETECTOR_SPAD_UI: DETECTOR_SPAD_ARRAY,
    DETECTOR_PI23_UI: DETECTOR_PI_23,
}


def normalize_detector_model(detector_model):
    if detector_model in DETECTOR_MODELS:
        return detector_model
    return DETECTOR_MODEL_ALIASES.get(detector_model, DETECTOR_SPAD_ARRAY)


def detector_uses_spad_pipeline(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_SPAD_MODELS


def detector_uses_pi23_pipeline(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_PI23_MODELS


def detector_uses_pi23_timestamp(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_PI23_TS_MODELS


def detector_uses_nifpga_fifo(detector_model):
    return detector_uses_spad_pipeline(detector_model)


def detector_uses_nifpga_control(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_MODELS
