"""Hardware adapters."""

from .fpga import FpgaHandle
from .ttm import TtmRemoteManager

__all__ = ["FpgaHandle", "TtmRemoteManager"]
