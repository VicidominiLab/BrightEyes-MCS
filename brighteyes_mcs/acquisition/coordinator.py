"""Stateful application service around the legacy acquisition backend."""

from __future__ import annotations

from .state import AcquisitionState


class AcquisitionCoordinator:
    def __init__(self, backend):
        self.backend = backend
        self.state = AcquisitionState.IDLE
        self.last_error: Exception | None = None

    def run(self) -> None:
        self.last_error = None
        self.state = AcquisitionState.CONNECTING
        try:
            self.backend._run_pipeline()
        except Exception as error:
            self.last_error = error
            self.state = AcquisitionState.ERROR
            raise
        self.state = (
            AcquisitionState.PREVIEWING
            if self.backend.do_not_save_event.is_set()
            else AcquisitionState.ACQUIRING
        )

    def stop(self) -> None:
        self.state = AcquisitionState.STOPPING
        try:
            self.backend._stop_pipeline()
        except Exception as error:
            self.last_error = error
            self.state = AcquisitionState.ERROR
            raise
        self.state = AcquisitionState.IDLE
