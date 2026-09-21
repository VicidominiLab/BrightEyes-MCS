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


def measurement_ms(ui):
    """Conservative scan budget, including circular dwells and frame waits.

    Calibration precedes SB,<ms> in both tools, so its actual duration is
    awaited separately; only the post-ready delay belongs in measurement-ms.
    """
    frames = ui.spinBox_nframe.value() * ui.spinBox_nrepetition.value()
    dwell = ui.spinBox_timeresolution.value() * ui.spinBox_time_bin_per_px.value() / 1e6
    if ui.checkBox_circular.isChecked():
        dwell *= ui.spinBox_circular_points.value() * ui.spinBox_circular_repetition.value()
    seconds = dwell * ui.spinBox_nx.value() * ui.spinBox_ny.value() * frames
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
    calibration_log = Signal(str)
    calibration_finished = Signal(bool, str)

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.process = None
        self.pending = False
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
        self.calibrating = False

    @property
    def active(self):
        return self.process is not None

    def log(self, message):
        self.ui.plainTextEdit_pi23ttm_log.appendPlainText(message.rstrip())

    def _enable_settings(self, enabled):
        for name in (
            "lineEdit_pi23ttm_h5_executable", "lineEdit_pi23ttm_raw_executable",
            "lineEdit_pi23ttm_folder", "lineEdit_pi23ttm_address",
            "comboBox_pi23ttm_format", "doubleSpinBox_pi23ttm_settle",
            "doubleSpinBox_pi23ttm_margin", "doubleSpinBox_pi23ttm_timeout",
            "toolButton_pi23ttm_h5", "toolButton_pi23ttm_raw", "toolButton_pi23ttm_folder",
            "pushButton_pi23ttm_force_calibration",
        ):
            getattr(self.ui, name).setEnabled(enabled)

    def start(self, filename):
        if self.active or self.calibrating:
            raise RuntimeError("The previous PI23 recording is still finishing.")
        raw = self.ui.comboBox_pi23ttm_format.currentText() == "RAW"
        executable = (self.ui.lineEdit_pi23ttm_raw_executable if raw else
                      self.ui.lineEdit_pi23ttm_h5_executable).text().strip()
        if not Path(executable).is_file():
            raise RuntimeError(f"PI23 recorder not found: {executable}")
        folder = self.ui.lineEdit_pi23ttm_folder.text().strip() or str(Path(filename).parent)
        Path(folder).mkdir(parents=True, exist_ok=True)
        self.path = output_path(folder, filename, raw).resolve()
        args = [executable, "--addr", self.ui.lineEdit_pi23ttm_address.text().strip(),
                "--measurement-ms", str(measurement_ms(self.ui)), "-o", str(self.path)]
        if getattr(sys, "frozen", False):
            raise RuntimeError("PI23 recorder bridge currently requires running MCS with Python.")
        options = {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options = dict(creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
        self.log(subprocess.list2cmdline(args))
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(Path(pi23ttm_runner.__file__).resolve()), *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", **options,
        )
        self.messages = queue.Queue()
        self.reader = threading.Thread(target=self._read, args=(self.process, self.messages), daemon=True)
        self.reader.start()
        self.pending = True
        self.stopping = False
        self._enable_settings(False)
        self.deadline = time.monotonic() + self.ui.doubleSpinBox_pi23ttm_timeout.value()
        self.ui.label_pi23ttm_status.setText("Starting / calibrating PI23 TTM…")
        self.timer.start()

    @staticmethod
    def _read(process, messages):
        for line in process.stdout:
            messages.put(line)
        messages.put(None)

    def poll(self):
        while not self.messages.empty():
            line = self.messages.get_nowait()
            if line is None:
                code = self.process.wait()
                self.process.stdout.close()
                self.process.stdin.close()
                self.process = None
                self.timer.stop()
                self.settle_timer.stop()
                was_pending = self.pending
                self.pending = False
                self._enable_settings(True)
                self.ui.label_pi23ttm_status.setText(f"Recorder exited ({code}): {self.path}")
                if not self.stopping and (code != 0 or was_pending):
                    self.failed.emit(f"PI23 recorder exited ({code}); see PI-Timetagging log.")
                self.finished.emit()
                return
            self.log(line)
            if self.pending and "Press Ctrl+C to stop." in line and not self.settle_timer.isActive():
                self.settle_timer.start(round(self.ui.doubleSpinBox_pi23ttm_settle.value() * 1000))
        if self.pending and time.monotonic() > self.deadline:
            self.stop()
            self.failed.emit("PI23 calibration / startup timed out; see PI-Timetagging log.")

    def _ready(self):
        if self.active and self.process.poll() is None and self.pending:
            self.pending = False
            self.ui.label_pi23ttm_status.setText(f"Recording: {self.path}")
            self.ready.emit()

    def stop(self):
        self.pending = False
        self.settle_timer.stop()
        if self.active and not self.stopping:
            self.stopping = True
            self.ui.label_pi23ttm_status.setText("Stopping PI23 TTM / closing file…")
            try:
                self.process.stdin.write("stop\n")
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def close(self):
        self.stop()
        if self.active:
            # Closing stdin also stops the bridge if the GUI exits unexpectedly.
            self.process.stdin.close()

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
