"""Network thread and count-processing process, independent of GUI event delivery."""

from brighteyes_mcs.logging_setup import logged_worker
import multiprocessing as mp
import queue
import threading
import time

from .microimage import MicroimagePreview
from .microimage_stream import buffered_microimages
from .stream_image import MicroimageSnapshot
from ....storage.pi23_microimage import MicroimageH5Writer
from ....logging_setup import logger


class MicroimageWorker(mp.Process):
    def __init__(self, width, height, port, batch_size, shared_objects, shared_dict, *, snake=False,
                 saving=None):
        super().__init__(daemon=True)
        self.width, self.height = width, height
        self.port, self.batch_size = port, batch_size
        self.shared_objects, self.shared_dict = shared_objects, shared_dict
        self.snake = snake
        self.saving = saving
        self.connected, self.done, self.stop_event = mp.Event(), mp.Event(), mp.Event()
        self.shared_dict["pi23_uimg_status"] = {}
        self.shared_dict["pi23_uimg_error"] = ""

    @property
    def error(self):
        return self.shared_dict.get("pi23_uimg_error", "")

    def stop(self):
        self.stop_event.set()

    @logged_worker
    def run(self):
        # 64 batches x 4096 dwells x 128 bytes = 32 MiB with default settings.
        incoming = queue.Queue(maxsize=64)
        progress_lock = threading.Lock()
        produced = received = 0
        def enqueue(item):
            while not self.stop_event.is_set():
                try:
                    incoming.put(item, timeout=0.1)
                    return
                except queue.Full:
                    continue

        def receive():
            nonlocal produced, received
            try:
                for batch in buffered_microimages(self.port, self.batch_size, self.stop_event, self.connected):
                    # Track the newest server cursor independently of processing.
                    # Include the batch waiting to enter a full local queue.
                    with progress_lock:
                        produced = batch.next_sequence
                        received = batch.sequence + len(batch.records)
                    enqueue(batch)
            except Exception as error:
                logger.exception("PI23 microimage receive failed port=%s batch=%s", self.port, self.batch_size)
                enqueue(error)
            finally:
                enqueue(None)

        reader = threading.Thread(target=receive, daemon=True)
        writer = None
        try:
            if self.saving is not None:
                writer = MicroimageH5Writer(width=self.width, height=self.height,
                                           snake=self.snake, **self.saving)
            reader.start()
            preview = MicroimagePreview(self.width, self.height, snake=self.snake,
                                        shared_objects=self.shared_objects)
            last_publish = 0
            end = False
            status = {"sequence": 0}
            while not self.stop_event.is_set():
                batch = None
                if not end:
                    try:
                        batch = incoming.get(timeout=0.05)
                    except queue.Empty:
                        batch = False
                    if isinstance(batch, Exception):
                        raise batch
                    if batch is None:
                        end = True
                    elif batch is not False:
                        logger.debug("PI23 microimage batch sequence=%s records=%s capacity=%s oldest=%s",
                                     batch.sequence, len(batch.records), batch.capacity, batch.oldest)
                        for record in batch.records:
                            snapshot = MicroimageSnapshot(
                                record["counts"], int(record["frame"]), int(record["x"]),
                                int(record["y"]), int(record["events"]), int(record["flags"]),
                            )
                            if writer is not None:
                                writer.consume(snapshot)
                            preview.consume(snapshot)
                        status = {"sequence": batch.sequence + len(batch.records),
                                  "capacity": batch.capacity, "oldest": batch.oldest}
                if time.monotonic() - last_publish >= 0.05 or end:
                    shared_mask = self.shared_objects["shared_fingerprint_mask"]
                    with shared_mask.get_lock():
                        mask = shared_mask.get_numpy_handle().copy()
                    preview.publish(self.shared_dict.get("channel", "Sum"), mask=mask,
                                    accumulate=self.shared_dict.get("accumulate_preview_photons", False))
                    with progress_lock:
                        status.update(available=max(0, produced - received),
                                      local_pending=max(0, received - status["sequence"]),
                                      pending_dwells=max(0, produced - status["sequence"]))
                    status.update(frame=preview.frame, frame_dwells=preview.frame_dwells,
                                  last_frame_dwells=preview.last_frame_dwells,
                                  recent_dwells=len(preview.recent), total_dwells=preview.total_dwells)
                    self.shared_dict["pi23_uimg_status"] = dict(status)
                    last_publish = time.monotonic()
                if end:
                    if writer is not None:
                        closing, writer = writer, None
                        if not closing.close(finished=True):
                            raise ValueError("PI23 HDF5 acquisition incomplete; missing pixels are marked in pi23_microimages/valid")
                    self.done.set()
                    self.stop_event.wait(0.1)
        except Exception as error:
            logger.exception("PI23 microimage worker failed port=%s scan=%sx%s status=%s",
                             self.port, self.width, self.height,
                             self.shared_dict.get("pi23_uimg_status"))
            self.shared_dict["pi23_uimg_error"] = str(error)
        finally:
            self.stop_event.set()
            if reader.ident is not None:
                reader.join(timeout=2)
            if writer is not None:
                try:
                    writer.close(error=self.error)
                except Exception as error:
                    logger.exception("PI23 HDF5 close failed")
                    self.shared_dict["pi23_uimg_error"] = f"PI23 HDF5 close failed: {error}"
            self.done.set()
