"""Asynchronous external PI23 time-tag recording and acquisition timing."""

import math
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from ...hardware import pi23ttm_runner
from ...acquisition.detectors.pi23.stream_image import read_snapshot
from ...logging_setup import data_debug_enabled, logger, trace_action


class _PersistedRecorderLine(str):
    """A pipe line already saved by the reader, before GUI event delivery."""


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
        seconds += ui.doubleSpinBox_pi23ttm_settle.value() + ui.doubleSpinBox_pi23ttm_preview_margin.value()
        return max(1, math.ceil(seconds * 1000))
    seconds *= frames
    seconds += frames * ui.spinBox_waitAfterFrame.value()
    seconds += ui.spinBox_waitForLaser.value() * (
        1 if ui.checkBox_waitOnlyFirstTime.isChecked() else frames
    )
    seconds += ui.doubleSpinBox_pi23ttm_settle.value() + ui.doubleSpinBox_pi23ttm_margin.value()
    return max(1, math.ceil(seconds * 1000))


def output_path(folder, mcs_filename, raw=False):
    path = Path(folder) / (Path(mcs_filename).stem + ("-ts.raw" if raw else "-tsraw.h5"))
    original = path
    index = 1
    while path.exists():
        path = original.with_name(f"{original.stem}-{index}{original.suffix}")
        index += 1
    return path


class Pi23Timetagging(QObject):
    ready = Signal()
    failed = Signal(str)
    finished = Signal()
    image_ready = Signal(object)
    microimage_updated = Signal()
    calibration_log = Signal(str)
    calibration_finished = Signal(bool, str)

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.process = None
        self.pending = False
        self.require_armed = False
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
        self.stream_image = False
        self.stream_microimage = False
        self.microimage_worker = None
        self.image_messages = queue.Queue(maxsize=1)
        self.image_stop = threading.Event()
        self.image_connected = threading.Event()
        self.image_done = threading.Event()
        self.image_error = None
        self.image_received = False
        self.image_wait_reported = False

    @property
    def active(self):
        return self.process is not None

    def log(self, message, *, persist=True):
        if persist:
            logger.info("PI23 TTM: %s", message.rstrip())
        self.ui.plainTextEdit_pi23ttm_log.appendPlainText(message.rstrip())

    def _log_failure(self, message):
        logger.error("PI23_FAILURE reason=%s output=%s pending=%s armed=%s stopping=%s",
                     message, self.path, self.pending, self.armed, self.stopping)

    def _close_pipe(self, pipe, name):
        if pipe is None:
            return
        try:
            pipe.close()
        except (OSError, ValueError) as error:
            # TextIOWrapper.close flushes a buffered stop command even after
            # the bridge exits. Windows can report EINVAL instead of EPIPE.
            logger.warning("PI23 recorder %s close failed: %s", name, error)

    def _enable_settings(self, enabled):
        for name in (
            "lineEdit_pi23ttm_h5_executable", "lineEdit_pi23ttm_raw_executable",
            "lineEdit_pi23ttm_folder", "lineEdit_pi23ttm_address",
            "comboBox_pi23ttm_format", "doubleSpinBox_pi23ttm_settle",
            "doubleSpinBox_pi23ttm_margin", "doubleSpinBox_pi23ttm_timeout",
            "doubleSpinBox_pi23ttm_preview_margin",
            "toolButton_pi23ttm_h5", "toolButton_pi23ttm_raw", "toolButton_pi23ttm_folder",
            "pushButton_pi23ttm_force_calibration",
            "spinBox_pi23ttm_stream_port",
            "spinBox_pi23ttm_uimg_buffer", "spinBox_pi23ttm_uimg_batch",
        ):
            getattr(self.ui, name).setEnabled(enabled)

    @trace_action
    def start(self, filename, *, stream_image=False, stream_microimage=False, record=True, preview=False,
              microimage_worker=None):
        if self.active or self.calibrating:
            raise RuntimeError("The previous PI23 recording is still finishing.")
        if stream_image and stream_microimage:
            raise ValueError("Choose either image or microimage streaming")
        if stream_microimage and microimage_worker is None:
            raise ValueError("Microimage mode requires its acquisition worker")
        stream_image = stream_image or stream_microimage
        raw = stream_image or self.ui.comboBox_pi23ttm_format.currentText() == "RAW"
        executable = (self.ui.lineEdit_pi23ttm_raw_executable if raw else
                      self.ui.lineEdit_pi23ttm_h5_executable).text().strip()
        if not Path(executable).is_file():
            raise RuntimeError(f"PI23 recorder not found: {executable}")
        self.path = None
        if record:
            folder = self.ui.lineEdit_pi23ttm_folder.text().strip() or str(Path(filename).parent)
            Path(folder).mkdir(parents=True, exist_ok=True)
            self.path = output_path(folder, filename, raw).resolve()
        args = [executable, "--addr", self.ui.lineEdit_pi23ttm_address.text().strip(),
                "--measurement-ms", str(measurement_ms(self.ui, preview=preview))]
        if record:
            args += ["-o", str(self.path)]
        else:
            args += ["--no-output"]
        if stream_image:
            width, height = self.ui.spinBox_nx.value(), self.ui.spinBox_ny.value()
            if not 0 < width * height <= 16_777_216:
                raise ValueError("PI23 stream image supports at most 16777216 scan pixels.")
            port = self.ui.spinBox_pi23ttm_stream_port.value()
            if stream_microimage:
                args += ["--stream-microimage", "--microimage-buffer", str(self.ui.spinBox_pi23ttm_uimg_buffer.value())]
            else:
                args += ["--stream-image", str(width), str(height), "--stream-image-pixel", "-1"]
            args += ["--stream-image-port", str(port)]
            if preview:
                args += ["--repeat"]
        if getattr(sys, "frozen", False):
            raise RuntimeError("PI23 recorder bridge currently requires running MCS with Python.")
        options = {"start_new_session": True} if os.name != "nt" else {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options = dict(creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
        if raw and data_debug_enabled():
            args.append("--verbose")
        self.log(subprocess.list2cmdline(args))
        job = None
        bridge_args = []
        if os.name == "nt":
            from ...hardware.pi23ttm_job import RecorderJob

            job = RecorderJob()
            bridge_args = ["--job-name", job.name]
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-u", str(Path(pi23ttm_runner.__file__).resolve()), *bridge_args, *args],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", **options,
            )
            self.process.recorder_job = job
            logger.info("PI23 recorder launched pid=%s output=%s stream_image=%s microimage=%s preview=%s",
                        self.process.pid, self.path, stream_image, stream_microimage, preview)
        except Exception:
            if job is not None:
                job.close()
            raise
        self.messages = queue.Queue()
        self.reader = threading.Thread(target=self._read, args=(self.process, self.messages), daemon=True)
        self.reader.start()
        self.pending = True
        self.require_armed = raw
        self.armed = False
        self.stopping = False
        self.stream_image = stream_image
        self.stream_microimage = stream_microimage
        self.microimage_worker = microimage_worker
        self.image_error = None
        self.image_received = False
        self.image_wait_reported = False
        self.image_messages = queue.Queue(maxsize=64 if stream_microimage else 1)
        self.image_stop = threading.Event()
        self.image_connected = threading.Event()
        self.image_done = threading.Event()
        if stream_microimage:
            self.image_connected = microimage_worker.connected
            self.image_done = microimage_worker.done
            self.image_stop = microimage_worker.stop_event
        elif stream_image:
            threading.Thread(
                target=self._read_images,
                args=(port, width, height, self.image_messages, self.image_stop),
                daemon=True,
            ).start()
        self._enable_settings(False)
        self.deadline = time.monotonic() + self.ui.doubleSpinBox_pi23ttm_timeout.value()
        self.ui.label_pi23ttm_status.setText("Starting / calibrating PI23 TTM…")
        self.timer.start()

    @staticmethod
    def _read(process, messages):
        try:
            for line in process.stdout:
                logger.info("PI23 recorder output pid=%s: %s", process.pid, line.rstrip())
                messages.put(_PersistedRecorderLine(line))
        except (OSError, ValueError) as error:
            logger.exception("PI23 recorder output read failed pid=%s", process.pid)
            messages.put(f"Recorder output read failed: {error}\n")
        finally:
            messages.put(None)

    def poll(self):
        if self.stream_image and not self.stopping:
            if self.stream_microimage:
                worker = self.microimage_worker
                error = worker.error
                if not error and not worker.is_alive() and not worker.done.is_set():
                    error = "PI23 microimage acquisition worker exited unexpectedly"
                if error:
                    self.log(error)
                    self.stop()
                    self.failed.emit(error)
            else:
                self._poll_images()
        self._poll_process()

    def _poll_images(self):
        for _ in range(1):
            try:
                snapshot = self.image_messages.get_nowait()
            except queue.Empty:
                break
            else:
                if isinstance(snapshot, Exception):
                    if not self.pending and str(snapshot) != self.image_error:
                        self.image_error = str(snapshot)
                        self.log(f"PI23 image stream: {snapshot}")
                        self.ui.label_pi23ttm_status.setText(f"Image stream unavailable: {snapshot}")
                elif snapshot is not None:
                    self.image_error = None
                    if not self.image_received:
                        self.image_received = True
                        shape = f"{snapshot.counts.shape[1]} x {snapshot.counts.shape[0]}"
                        self.log(f"Image stream received: {shape}, frame {snapshot.frame}, {snapshot.events} photons")
                    self.ui.label_pi23ttm_status.setText(
                        f"Recording: {self.path}" if self.path else "PI23 timestamp image preview"
                    )
                    self.image_ready.emit(snapshot)
                elif not self.pending and not self.image_wait_reported:
                    self.image_wait_reported = True
                    interval = "scan frame marker"
                    self.log(f"Image server connected; waiting for the first {interval}.")
                    self.ui.label_pi23ttm_status.setText(f"Image server connected; waiting for {interval}.")

    def _poll_process(self):
        while not self.messages.empty():
            line = self.messages.get_nowait()
            if line is None:
                process = self.process
                if process is None:
                    continue
                if (self.stream_microimage and not self.stopping and not self.pending
                        and (not self.image_done.is_set() or not self.image_messages.empty())):
                    # Rust serves the final batches before exit; consume the tail
                    # before announcing completion or releasing preview buffers.
                    self.messages.put(None)
                    return
                code = process.wait()
                log_exit = logger.error if code != 0 else logger.info
                log_exit("PI23 recorder exit pid=%s code=%s hex=0x%08X requested_stop=%s pending=%s armed=%s output=%s",
                         process.pid, code, code & 0xFFFFFFFF, self.stopping, self.pending,
                         self.armed, self.path)
                if self.stream_microimage and not self.stopping and self.microimage_worker.error:
                    self.stop()
                    self.failed.emit(self.microimage_worker.error)
                job = getattr(process, "recorder_job", None)
                if job is not None:
                    job.close()
                self.process = None
                self.image_stop.set()
                self.timer.stop()
                self.settle_timer.stop()
                was_pending = self.pending
                self.pending = False
                self._close_pipe(process.stdout, "stdout")
                self._close_pipe(process.stdin, "stdin")
                self._enable_settings(True)
                result = f"Recorder exited ({code}): {self.path}" if self.path else f"Image stream exited ({code})"
                self.log(result)
                self.ui.label_pi23ttm_status.setText(result)
                if not self.stopping and (code != 0 or was_pending):
                    self.failed.emit(f"PI23 recorder exited ({code}); see PI-Timetagging log.")
                if self.stream_microimage:
                    self.microimage_updated.emit()
                self.finished.emit()
                return
            self.log(line, persist=not isinstance(line, _PersistedRecorderLine))
            stream_closed = self.stream_image and "Socket closed by server." in line
            if ("Acquisition error:" in line or stream_closed) and not self.stopping:
                self.stop()
                self.failed.emit(line.strip())
            if line.strip() == "PI23_DISARMED":
                self.armed = False
                if self.pending:
                    self.settle_timer.stop()
            if line.startswith("PI23_ARMED SB,"):
                self.armed = True
            ready_message = (line.startswith("PI23_ARMED SB,") if self.require_armed
                             else "Press Ctrl+C to stop." in line)
            if self.pending and ready_message and not self.settle_timer.isActive():
                self.settle_timer.start(round(self.ui.doubleSpinBox_pi23ttm_settle.value() * 1000))
        if self.pending and time.monotonic() > self.deadline:
            detail = (" RAW recorder must report PI23_ARMED after sending SB; rebuild tdc_raw_acquire if needed."
                      if self.require_armed and not self.armed else "")
            self.stop()
            self.failed.emit("PI23 calibration / startup timed out; see PI-Timetagging log." + detail)

    @staticmethod
    def _read_images(port, width, height, messages, stop):
        while not stop.is_set():
            try:
                result = read_snapshot(port, width, height)
            except (OSError, ValueError) as error:
                result = error
            try:
                messages.put_nowait(result)
            except queue.Full:
                pass
            if stop.wait(0.2):
                break

    def _ready(self):
        # Process a queued DONE/disarm before acting on an earlier ready timer.
        if not self.messages.empty():
            self._poll_process()
            if self.settle_timer.isActive():
                return
        if self.active and self.process.poll() is None and self.pending:
            if self.require_armed and not self.armed:
                return
            if self.stream_microimage and not self.image_connected.is_set():
                self.settle_timer.start(50)
                return
            self.pending = False
            self.ui.label_pi23ttm_status.setText(
                f"Recording: {self.path}" if self.path else "PI23 timestamp image preview"
            )
            self.log("Recorder ready; starting the FPGA scan.")
            self.ready.emit()

    def stop(self):
        self.pending = False
        self.image_stop.set()
        self.settle_timer.stop()
        if self.active and not self.stopping:
            self.stopping = True
            threading.Thread(
                target=pi23ttm_runner.stop_watchdog,
                args=(self.process, self.messages), daemon=True,
            ).start()
            self.ui.label_pi23ttm_status.setText("Stopping PI23 TTM / closing file…")
            try:
                self.process.stdin.write("stop\n")
                self.process.stdin.flush()
            except (OSError, ValueError) as error:
                logger.warning("PI23 recorder stop pipe failed: %s", error)
                self._close_pipe(self.process.stdin, "stdin")  # EOF also stops the bridge.

    def close(self):
        self.stop()
        if self.active:
            # Closing stdin also stops the bridge if the GUI exits unexpectedly.
            self._close_pipe(self.process.stdin, "stdin")

    @trace_action
    def force_calibration(self):
        """Request a standalone vendor TDC calibration without recording data."""
        if self.active or self.calibrating:
            self.log("Cannot force calibration while PI23 TTM is active.")
            return
        endpoint = self.ui.lineEdit_pi23ttm_address.text().strip()
        try:
            host, port = endpoint.rsplit(":", 1)
            port = int(port)
        except ValueError:
            self.ui.label_pi23ttm_status.setText("Invalid TTM endpoint; use host:port.")
            return
        self.calibrating = True
        self._enable_settings(False)
        self.ui.label_pi23ttm_status.setText("Forcing PI23 TTM calibration…")
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
            self.ui.label_pi23ttm_status.setText("PI23 TTM calibration completed.")
        else:
            self.log(f"Force Calibration failed: {message}")
            self.ui.label_pi23ttm_status.setText("PI23 TTM calibration failed; see log.")
