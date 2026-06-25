"""PI23 acquisition loop scaffold."""

from .spad_acquisition_loop_process import SpadAcquisitionLoopProcess


class Pi23AcquisitionLoopProcess(SpadAcquisitionLoopProcess):
    """
    PI23-named acquisition worker.

    It currently reuses the shared preview/H5 implementation after
    ``Pi23DataPreProcess`` decodes detector-native bunches into the normalized
    preview stream.
    """

