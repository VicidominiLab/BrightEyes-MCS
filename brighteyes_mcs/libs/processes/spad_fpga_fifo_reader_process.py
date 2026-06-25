"""SPAD NI-FPGA FIFO reader process."""

from .fpga_handle_process_fifo_new import FpgaHandleProcess


class SpadFpgaFifoReaderProcess(FpgaHandleProcess):
    """SPAD-named wrapper around the NI-FPGA FIFO process."""

