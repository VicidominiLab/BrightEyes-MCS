"""Library acquisition and MCS dwell processing inside one owned worker process."""

import json
import multiprocessing as mp
import queue
import signal
import time

from .microimage import MicroimagePreview
from .stream_image import MicroimageSnapshot
from ....logging_setup import logged_worker, logger
from ....storage.pispad23_microimage import MicroimageH5Writer


class LibraryMicroimageWorker(mp.Process):
    """Rust threads receive/record; this process publishes existing MCS arrays.

    Configuration arrives after MCS prepares its workers, before SB/FPGA start.
    No Qt callbacks or local TCP preview server participate in data delivery.
    The worker creates no child processes, so the existing supervisor owns its
    complete lifetime, including native threads and open recording files.
    """

    def __init__(self, width, height, batch_size, shared_objects=None, shared_dict=None,
                 *, snake=False, saving=None):
        super().__init__(daemon=True)
        self.width, self.height = width, height
        self.batch_size = batch_size
        self.shared_objects = shared_objects
        self.shared_dict = shared_dict if shared_dict is not None else {}
        self.snake, self.saving = snake, saving
        self.connected, self.done, self.stop_event = mp.Event(), mp.Event(), mp.Event()
        self.commands = mp.Queue(maxsize=1)
        self._status = mp.Array("c", 16384)
        self._publish_status(dict(state="waiting", finished=False, armed=False, error=""))
        if shared_objects is not None:
            self.shared_dict["pispad23_uimg_status"] = {}
            self.shared_dict["pispad23_uimg_error"] = ""

    def configure(self, options):
        self.commands.put_nowait(dict(options))

    def statistics(self):
        lock = self._status.get_lock()
        if not lock.acquire(timeout=0.05):
            return dict(state="unresponsive", finished=False, armed=False, error="")
        try:
            return json.loads(self._status.value)
        finally:
            lock.release()

    @property
    def error(self):
        return self.statistics().get("error", "")

    def _publish_status(self, status):
        status = dict(status)
        status["error"] = status.get("error", "")[:2048]
        with self._status.get_lock():
            self._status.value = json.dumps(status).encode("utf-8")

    def stop(self):
        self.stop_event.set()

    def _publish_preview(self, preview, status):
        shared_mask = self.shared_objects.get("shared_fingerprint_mask")
        mask = None
        if shared_mask is not None:
            with shared_mask.get_lock():
                mask = shared_mask.get_numpy_handle().copy()
        preview.publish(self.shared_dict.get("channel", "Sum"), mask=mask,
                        accumulate=self.shared_dict.get("accumulate_preview_photons", False))
        status.update(frame=preview.frame, frame_dwells=preview.frame_dwells,
                      last_frame_dwells=preview.last_frame_dwells,
                      recent_dwells=len(preview.recent), total_dwells=preview.total_dwells)
        self.shared_dict["pispad23_uimg_status"] = dict(status)

    @logged_worker
    def run(self):
        # The GUI owns Ctrl+C and requests stop through its supervisor. Native
        # writers must not be interrupted by a console signal in this process.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        session = writer = preview = None
        error = ""
        status = dict(state="starting", finished=False, armed=False, error="")
        natural = False
        try:
            while not self.stop_event.is_set():
                try:
                    options = self.commands.get(timeout=0.05)
                    break
                except queue.Empty:
                    continue
            else:
                return
            from brighteyes_pispad import AcquisitionConfig, AcquisitionSession

            if self.saving is not None:
                writer = MicroimageH5Writer(width=self.width, height=self.height,
                                           snake=self.snake, **self.saving)
            if self.shared_objects is not None:
                preview = MicroimagePreview(self.width, self.height, snake=self.snake,
                                            shared_objects=self.shared_objects)
            session = AcquisitionSession(AcquisitionConfig(**options)).start()
            last_publish = 0
            sequence = 0
            while not self.stop_event.is_set():
                # Sample completion BEFORE reading: finished=True then guarantees
                # no producer can append another native tail after an empty read.
                native = session.statistics()
                batch = session.read_microimages(self.batch_size, timeout=0.01)
                if preview is not None:
                    for record in batch:
                        snapshot = MicroimageSnapshot(record["counts"], int(record["frame"]),
                            int(record["x"]), int(record["y"]), int(record["events"]),
                            int(record["flags"]))
                        if writer is not None:
                            writer.consume(snapshot)
                        preview.consume(snapshot)
                sequence += len(batch)
                if native.get("runs_started", 0):
                    self.connected.set()
                if native.get("device_overflows", 0):
                    raise ValueError("PI SPAD23R device FIFO overflow; timestamp data may be incomplete")
                pending = max(0, native.get("microimages", 0) - sequence) if preview is not None else 0
                status = dict(native, sequence=sequence, available=pending, local_pending=0,
                              pending_dwells=pending, capacity=options["microimage_capacity"])
                # Keep GUI readiness fresh even while the plot publish is throttled.
                self._publish_status(dict(status, finished=False))
                if time.monotonic() - last_publish >= 0.05:
                    if preview is not None:
                        self._publish_preview(preview, status)
                    last_publish = time.monotonic()
                if native["finished"] and not len(batch):
                    session.wait()
                    natural = native["state"] == "complete"
                    break
        except Exception as exception:
            error = str(exception)
            logger.exception("PI SPAD23R library acquisition failed")
        finally:
            if session is not None:
                session.request_stop()
                try:
                    final = session.wait(timeout=10)
                    status.update(final)
                except Exception as exception:
                    error = error or str(exception)
            if writer is not None:
                try:
                    complete = writer.close(finished=natural and not self.stop_event.is_set(),
                                            error=error)
                    if natural and not complete and not error:
                        error = "PI SPAD23R HDF5 acquisition incomplete; missing pixels are marked invalid"
                except Exception as exception:
                    error = error or f"PI SPAD23R HDF5 close failed: {exception}"
            if preview is not None:
                try:
                    self._publish_preview(preview, status)
                except Exception as exception:
                    error = error or f"PI SPAD23R final preview publication failed: {exception}"
            status.update(finished=True, armed=False, error=error,
                          state="failed" if error else "complete" if natural else "interrupted")
            self._publish_status(status)
            if self.shared_objects is not None:
                self.shared_dict["pispad23_uimg_error"] = error
            self.done.set()
