"""Hardware adapters."""

__all__ = ["FpgaHandle", "TtmRemoteManager"]


def __getattr__(name):
    if name == "FpgaHandle":
        from .fpga import FpgaHandle
        return FpgaHandle
    if name == "TtmRemoteManager":
        from .ttm import TtmRemoteManager
        return TtmRemoteManager
    raise AttributeError(name)
