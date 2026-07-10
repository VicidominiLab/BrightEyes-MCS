"""Bluesky/Ophyd support for BrightEyes-MCS low-level FPGA registers."""

from importlib import import_module

from .registers import (
    FIFO_SPECS,
    REGISTER_ATTR_BY_NAME,
    REGISTER_SPECS,
    REGISTER_SPECS_BY_ATTR,
    REGISTER_SPECS_BY_NAME,
    FifoSpec,
    RegisterSpec,
)

__all__ = [
    "BrightEyesMCSLLDevice",
    "BrightEyesRegisterSignal",
    "FIFO_SPECS",
    "FifoSpec",
    "MappingRegisterIO",
    "NifpgaRegisterIO",
    "REGISTER_ATTR_BY_NAME",
    "REGISTER_SPECS",
    "REGISTER_SPECS_BY_ATTR",
    "REGISTER_SPECS_BY_NAME",
    "RegisterIO",
    "RegisterSpec",
]

_DEVICE_EXPORTS = {
    "BrightEyesMCSLLDevice",
    "BrightEyesRegisterSignal",
    "MappingRegisterIO",
    "NifpgaRegisterIO",
    "RegisterIO",
}


def __getattr__(name):
    if name in _DEVICE_EXPORTS:
        device = import_module(".device", __name__)
        return getattr(device, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
