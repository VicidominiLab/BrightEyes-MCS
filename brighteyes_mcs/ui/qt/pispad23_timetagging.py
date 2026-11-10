"""One asynchronous PI SPAD23R acquisition controller for both library modes."""
import math
from pathlib import Path
import queue
import socket
import threading
import time
from PySide6.QtCore import QObject, QTimer, Signal
from ...logging_setup import logger, trace_action

def measurement_ms(ui, *, preview=False):
    """One frame plus startup/wait margin for preview; full recording budget.

    Calibration precedes SB,<ms> in both tools, so its actual duration is
    awaited separately; only the post-ready delay belongs in measurement-ms.
    Preview includes one frame's waits, the post-SB delay, and its own margin,
    without multiplying by frame/repetition counts.
    """
    frames = ui.spinBox_nframe.value() * ui.spinBox_nrepetition.value()
    dwell = ui.spinBox_timeresolution.value() * ui.spinBox_time_bin_per_px.value() / 1e6
    if ui.checkBox_circular.isChecked():
        dwell *= ui.spinBox_circular_points.value() * ui.spinBox_circular_repetition.value()
    seconds = dwell * ui.spinBox_nx.value() * ui.spinBox_ny.value()
    if preview:
        seconds += ui.spinBox_waitAfterFrame.value() + ui.spinBox_waitForLaser.value()
        seconds += ui.doubleSpinBox_pispad23ttm_settle.value() + ui.doubleSpinBox_pispad23ttm_preview_margin.value()
        return max(1, math.ceil(seconds * 1000))
    seconds *= frames
    seconds += frames * ui.spinBox_waitAfterFrame.value()
    seconds += ui.spinBox_waitForLaser.value() * (
        1 if ui.checkBox_waitOnlyFirstTime.isChecked() else frames
    )
    seconds += ui.doubleSpinBox_pispad23ttm_settle.value() + ui.doubleSpinBox_pispad23ttm_margin.value()
    return max(1, math.ceil(seconds * 1000))


def output_path(folder, mcs_filename, raw=False, mode="timestamp"):
    suffix = ("-intensity.raw" if raw else "-intensity.h5") if mode == "intensity" else ("-ts.raw" if raw else "-tsraw.h5")
    path = Path(folder) / (Path(mcs_filename).stem + suffix)
    original = path
    index = 1
    while path.exists():
        path = original.with_name(f"{original.stem}-{index}{original.suffix}")
        index += 1
    return path


class PISPAD23Timetagging(QObject):
    ready = Signal()
    failed = Signal(str)
    finished = Signal()
    microimage_updated = Signal()
    calibration_log = Signal(str)
    calibration_finished = Signal(bool, str)

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.process = None
        self.library_worker = None
        self.library_run = 0
        self.pending = False
        self.armed = False
        self.stopping = False
        self.path = None
        self.messages = queue.Queue()
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll)
        self.settle_timer = QTimer(self)
        self.settle_timer.setSingleShot(True)
        self.settle_timer.timeout.connect(self._ready)
        self.calibration_log.connect(self.log)
        self.calibration_finished.connect(self._calibration_finished)
        self.failed.connect(self._log_failure)
        self.calibrating = False
        self.stream_microimage = False
        self.microimage_worker = None
        self.image_stop = threading.Event()
        self.image_connected = threading.Event()
        self.image_done = threading.Event()

    @property
    def active(self):
        return self.process is not None

    def log(self, message, *, persist=True):
        if persist:
            logger.info("PI SPAD23R TTM: %s", message.rstrip())
        self.ui.plainTextEdit_pispad23ttm_log.appendPlainText(message.rstrip())

    def _log_failure(self, message):
        logger.error("PISPAD23_FAILURE reason=%s output=%s pending=%s armed=%s stopping=%s",
                     message, self.path, self.pending, self.armed, self.stopping)

    def _enable_settings(self, enabled):
        for name in (
            "lineEdit_pispad23ttm_folder", "lineEdit_pispad23ttm_address", "toolButton_pispad23ttm_folder",
            "comboBox_pispad23ttm_format", "doubleSpinBox_pispad23ttm_settle",
            "doubleSpinBox_pispad23ttm_margin", "doubleSpinBox_pispad23ttm_timeout",
            "doubleSpinBox_pispad23ttm_preview_margin", "pushButton_pispad23ttm_force_calibration",
            "spinBox_pispad23ttm_uimg_buffer", "spinBox_pispad23ttm_uimg_batch",
            "spinBox_pispad23_channels", "doubleSpinBox_pispad23_intensity_dwell",
            "checkBox_pispad23_external_frame",
        ):
            getattr(self.ui, name).setEnabled(enabled)
        if enabled:
            from ...acquisition.detectors.models import detector_uses_pispad23_pipeline
            intensity = detector_uses_pispad23_pipeline(self.ui.comboBox_detector_model.currentText())
            for name in ("spinBox_pispad23_channels", "doubleSpinBox_pispad23_intensity_dwell",
                         "checkBox_pispad23_external_frame"):
                getattr(self.ui, name).setEnabled(intensity)
            for name in ("doubleSpinBox_pispad23ttm_margin", "doubleSpinBox_pispad23ttm_preview_margin",
                         "pushButton_pispad23ttm_force_calibration"):
                getattr(self.ui, name).setEnabled(not intensity)


    @trace_action
    def start(self, filename, *, stream_microimage=False, record=True, preview=False,
              microimage_worker=None, mode="timestamp", wait_for_trigger=False):
        if self.active or self.calibrating:
            raise RuntimeError("The previous PI SPAD23R acquisition is still finishing.")
        if stream_microimage and microimage_worker is None:
            raise ValueError("Microimage mode requires its acquisition worker")
        try:
            import brighteyes_pispad as pispad
        except ImportError as error:
            raise RuntimeError("Install brighteyes-pispad-libs in the Python environment running BrightEyes-MCS.") from error
        if "mode" not in pispad.AcquisitionConfig.__dataclass_fields__:
            raise RuntimeError("Update brighteyes-pispad-libs to version 0.2 or newer.")
        from ...acquisition.detectors.pispad23.library_worker import LibraryMicroimageWorker

        if stream_microimage and not isinstance(microimage_worker, LibraryMicroimageWorker):
            raise RuntimeError("Microimage acquisition requires the PI library worker.")
        raw = self.ui.comboBox_pispad23ttm_format.currentText() == "RAW"
        self.path = None
        if record:
            folder = self.ui.lineEdit_pispad23ttm_folder.text().strip() or str(Path(filename).parent)
            Path(folder).mkdir(parents=True, exist_ok=True)
            self.path = output_path(folder, filename, raw, mode).resolve()
        duration = measurement_ms(self.ui, preview=preview)
        config = pispad.AcquisitionConfig(
            addr=self.ui.lineEdit_pispad23ttm_address.text().strip(),
            output=str(self.path) if self.path else None, format="raw" if raw else "h5",
            measurement_ms=duration, repeat=preview, preview=stream_microimage,
            mode=mode, width=self.ui.spinBox_nx.value(), height=self.ui.spinBox_ny.value(),
            frames=self.ui.spinBox_nframe.value() * self.ui.spinBox_nrepetition.value(),
            detector_channels=self.ui.spinBox_pispad23_channels.value(),
            intensity_dwell_us=self.ui.doubleSpinBox_pispad23_intensity_dwell.value(),
            external_frame=self.ui.checkBox_pispad23_external_frame.isChecked(),
            wait_for_trigger=wait_for_trigger,
            microimage_capacity=self.ui.spinBox_pispad23ttm_uimg_buffer.value(),
            idle_timeout_sec=max(60, math.ceil(duration / 1000) + 5),
        )
        worker = microimage_worker
        if worker is None:
            worker = LibraryMicroimageWorker(self.ui.spinBox_nx.value(), self.ui.spinBox_ny.value(),
                                             self.ui.spinBox_pispad23ttm_uimg_batch.value(), mode=mode)
        worker.configure(vars(config))
        if not stream_microimage:
            worker.start()
        self.process = self.library_worker = worker
        self.library_run = 0
        self.pending = True
        self.armed = self.stopping = False
        self.stream_microimage = stream_microimage
        self.microimage_worker = worker if stream_microimage else None
        self.image_connected, self.image_done, self.image_stop = worker.connected, worker.done, worker.stop_event
        self.messages = queue.Queue()
        self._enable_settings(False)
        self.deadline = time.monotonic() + self.ui.doubleSpinBox_pispad23ttm_timeout.value()
        self.log(f"brighteyes-pispad-libs: endpoint={config.addr} format={config.format} "
                 f"measurement_ms={duration} microimages={stream_microimage} output={self.path}")
        self.ui.label_pispad23ttm_status.setText("Starting / calibrating PI SPAD23R library acquisition…")
        self.timer.start()

    def _poll_library(self):
        worker = self.library_worker
        if worker is None:
            return
        while not self.messages.empty():
            self.log(self.messages.get_nowait())
        status = worker.statistics()
        run = status.get("runs_started", 0)
        if run != self.library_run:
            self.settle_timer.stop()
            self.library_run = run
        self.armed = bool(status.get("armed"))
        if not self.armed:
            self.settle_timer.stop()
        elif self.pending and not self.settle_timer.isActive():
            self.settle_timer.start(round(self.ui.doubleSpinBox_pispad23ttm_settle.value() * 1000))
        if self.stream_microimage:
            self.microimage_updated.emit()
        error = status.get("error", "")
        if error and not self.stopping:
            self.log(error)
            self.stop()
            self.failed.emit(error)
        if not worker.is_alive():
            worker.join(timeout=0)
            if not self.stopping and (not worker.done.is_set() or worker.exitcode != 0
                                      or status.get("state") != "complete"):
                error = error or f"PI SPAD23R library worker exited unexpectedly ({worker.exitcode})"
            was_pending = self.pending
            self.process = self.library_worker = None
            self.pending = self.armed = False
            self.timer.stop()
            self.settle_timer.stop()
            self._enable_settings(True)
            result = f"Library acquisition {status.get('state', 'exited')}: {self.path or 'preview only'}"
            self.log(result)
            self.ui.label_pispad23ttm_status.setText(result)
            if not self.stopping and (error or was_pending):
                self.failed.emit(error or "PI SPAD23R measurement ended before the FPGA scan started.")
            self.finished.emit()
        elif self.pending and time.monotonic() > self.deadline:
            self.stop()
            self.failed.emit("PI SPAD23R calibration / startup timed out; see PI-Timetagging log.")

    def poll(self):
        self._poll_library()

    def _ready(self):
        if self.library_worker is not None:
            worker = self.library_worker
            status = worker.statistics()
            if (not worker.is_alive() or worker.done.is_set() or not status.get("armed")
                    or status.get("runs_started", 0) != self.library_run):
                self._poll_library()
                return
            if not self.pending or self.stopping:
                return
            if not worker.connected.is_set():
                self.settle_timer.start(50)
                return
            self.pending = False
            self.ui.label_pispad23ttm_status.setText(
                f"Recording: {self.path}" if self.path else "PI SPAD23R microimage preview")
            self.log("Recorder ready; starting the FPGA scan.")
            self.ready.emit()
            return
    def stop(self):
        self.pending = False
        self.settle_timer.stop()
        if self.library_worker is not None and not self.stopping:
            self.stopping = True
            self.image_stop.set()
            self.ui.label_pispad23ttm_status.setText("Stopping PI SPAD23R / closing file")
            threading.Thread(target=self._stop_library_worker,
                             args=(self.library_worker, self.messages), daemon=True).start()

    def close(self):
        self.stop()

    @staticmethod
    def _stop_library_worker(worker, messages):
        worker.stop()
        worker.join(timeout=5)
        if worker.is_alive():
            messages.put("Library worker did not stop within 5 seconds; forcing termination. Output may be incomplete.")
            worker.terminate()
            worker.join(timeout=2)

    @trace_action
    def force_calibration(self):
        """Request a standalone vendor TDC calibration without recording data."""
        if self.active or self.calibrating:
            self.log("Cannot force calibration while PI SPAD23R TTM is active.")
            return
        endpoint = self.ui.lineEdit_pispad23ttm_address.text().strip()
        try:
            host, port = endpoint.rsplit(":", 1)
            port = int(port)
        except ValueError:
            self.ui.label_pispad23ttm_status.setText("Invalid TTM endpoint; use host:port.")
            return
        self.calibrating = True
        self._enable_settings(False)
        self.ui.label_pispad23ttm_status.setText("Forcing PI SPAD23R TTM calibration…")
        self.log(f"Force Calibration: connecting to {endpoint}")
        threading.Thread(
            target=self._force_calibration_worker, args=(host, port), daemon=True
        ).start()

    def _force_calibration_worker(self, host, port):
        try:
            with socket.create_connection((host, port), timeout=5) as connection:
                connection.settimeout(60)
                try:
                    greeting = connection.recv(8192)
                    if greeting:
                        self.calibration_log.emit(
                            f"Server greeting: {greeting.decode('utf-8', errors='replace').strip()}"
                        )
                except socket.timeout:
                    pass
                connection.sendall(b"T,c,1\n")
                response = connection.recv(8192).decode("utf-8", errors="replace").strip()
                self.calibration_finished.emit(True, response or "Calibration command completed.")
        except Exception as error:
            self.calibration_finished.emit(False, str(error))

    def _calibration_finished(self, success, message):
        self.calibrating = False
        self._enable_settings(True)
        if success:
            self.log(f"Force Calibration response: {message}")
            self.ui.label_pispad23ttm_status.setText("PI SPAD23R TTM calibration completed.")
        else:
            self.log(f"Force Calibration failed: {message}")
            self.ui.label_pispad23ttm_status.setText("PI SPAD23R TTM calibration failed; see log.")
