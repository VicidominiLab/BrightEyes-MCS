"""SPAD adapter for the shared acquisition loop."""

from ...acquisition_loop import BaseAcquisitionLoopProcess


class SpadAcquisitionLoopProcess(BaseAcquisitionLoopProcess):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("process_label", "SPAD acquisition loop")
        super().__init__(*args, **kwargs)


__all__ = ["SpadAcquisitionLoopProcess"]
