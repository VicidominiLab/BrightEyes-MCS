"""Qt timer adapter for spawned process tasks; no Qt worker threads."""

from concurrent.futures import TimeoutError
from concurrent.futures.process import BrokenProcessPool
import queue
import logging

from PySide6.QtCore import QObject, Signal, QTimer


log = logging.getLogger(__name__)


class FlareJob(QObject):
    result = Signal(object, object)
    snapshot = Signal(object)
    finished = Signal()

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function
        self.future = None
        self._completed = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)

    def start(self):
        try:
            self.future = self.parent()._process_pool.submit(self.function)
        except Exception as error:
            if isinstance(error, BrokenProcessPool):
                self.parent()._pool_failed = True
            self._start_error = str(error)
        self._timer.start()

    def isRunning(self):
        return not self._completed

    def _drain_snapshot(self):
        mailbox = self.function.arguments.get("snapshots")
        if mailbox is not None:
            try:
                self.snapshot.emit(mailbox.get_nowait())
            except queue.Empty:
                pass

    def _poll(self):
        self._drain_snapshot()
        if self.future is not None and not self.future.done():
            return
        value, error = None, getattr(self, "_start_error", None)
        if self.future is not None:
            try:
                value = self.future.result()
            except Exception as exception:
                if isinstance(exception, BrokenProcessPool):
                    self.parent()._pool_failed = True
                error = f"Flare worker failed: {exception}"
        # Completion can race the first mailbox read. Publish the final image
        # before announcing the result or starting the next preview frame.
        self._drain_snapshot()
        if error:
            log.warning("Flare worker task failed: %s", error)
        self._timer.stop()
        self._completed = True
        self.result.emit(value, error)
        self.finished.emit()

    def wait(self, milliseconds):
        if self.future is not None:
            try:
                self.future.result(timeout=milliseconds / 1000)
            except TimeoutError:
                return self.future.done()
            except Exception:
                pass
        return True
