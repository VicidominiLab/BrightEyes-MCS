"""SPAD FIFO preprocessing worker."""

from .data_pre_process import DataPreProcess


class SpadDataPreProcess(DataPreProcess):
    """SPAD-named wrapper around the legacy FIFO preprocessing worker."""

