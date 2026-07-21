"""Detector model names and capability predicates."""

DETECTOR_SPAD_ARRAY = "SPAD Array"
DETECTOR_PI_23 = "PI 23"
DETECTOR_SPAD_TTM = "SPAD_TTM"
DETECTOR_PI23_TT = "PI23TT"

DETECTOR_SPAD_MODELS = (DETECTOR_SPAD_ARRAY, DETECTOR_SPAD_TTM)
DETECTOR_PI23_MODELS = (DETECTOR_PI_23, DETECTOR_PI23_TT)
DETECTOR_MODELS = DETECTOR_SPAD_MODELS + DETECTOR_PI23_MODELS
DETECTOR_MODEL_ALIASES = {"SPAD": DETECTOR_SPAD_ARRAY, "PI23": DETECTOR_PI_23}


def normalize_detector_model(detector_model):
    if detector_model in DETECTOR_MODELS:
        return detector_model
    return DETECTOR_MODEL_ALIASES.get(detector_model, DETECTOR_SPAD_ARRAY)


def detector_uses_spad_pipeline(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_SPAD_MODELS


def detector_uses_pi23_pipeline(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_PI23_MODELS


def detector_uses_nifpga_fifo(detector_model):
    return detector_uses_spad_pipeline(detector_model)


def detector_uses_nifpga_control(detector_model):
    return normalize_detector_model(detector_model) in DETECTOR_MODELS
