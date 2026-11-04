"""Qt adapter for explicitly selected Flare control and acquisition."""

from datetime import datetime
import json
import logging
import multiprocessing
import queue
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QSignalBlocker, Signal, QTimer, Qt
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication, QFileDialog, QHeaderView, QTableWidgetItem, QMessageBox

from ...acquisition.detectors.flare.config import (
    FlareSettings, axis_registers_from_gui,
)
from ...acquisition.detectors.flare.controls import FlareLiveControls
from ...acquisition.detectors.flare.dfd import sequence_from_gui, REFERENCE_FACTOR
from ...acquisition.detectors.flare.dfd_format import pack_sequence
from ...acquisition.detectors.models import detector_uses_flare
from ...acquisition.flare_worker import FlareTask, initialize_worker
from .flare_job import FlareJob


class FlareShutdownError(RuntimeError):
    """Keep the window alive until a bounded Flare request has returned."""


class FlareLogBridge(QObject, logging.Handler):
    line = Signal(str)

    def __init__(self, parent):
        QObject.__init__(self, parent)
        logging.Handler.__init__(self)

    def emit(self, record):
        self.line.emit(record.getMessage())


class FlareController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.ui = window.ui
        self.selected = False
        self.connected = False
        self.job = None
        self.register_jobs = set()
        self.run_job = None
        self.conversion_job = None
        self.live_job = None
        self.live_controls = FlareLiveControls()
        self._process_pool = None
        self._pool_failed = False
        self._pending_reset = False
        self._ipc_manager = None
        self._cancel = None
        self._display = None
        self._busy_failures = []
        self._reset_prompt = None
        self._closed = False
        self._log_mailbox = None
        self._log_timer = QTimer(self)
        self._log_timer.setInterval(200)
        self._log_timer.timeout.connect(self._drain_worker_logs)
        self.ui.plainTextEdit_flare_log.setMaximumBlockCount(1000)
        self.runner = None
        self.preview = False
        self.stopping = False
        self.last_result = None
        self.last_snapshot = None
        self._discovery = None
        self._disabled = {}
        self._catalog = {}
        self.display_channels = None
        self._frozen = {}
        self._preserve_view = False
        self._display_geometry = None
        self._profile_widgets = {}
        self._clock_label = None
        self._reference_active = None
        self._repeat = QTimer(self)
        self._repeat.setSingleShot(True)
        self._repeat.timeout.connect(lambda: self.begin(True))
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self.poll_status)
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(80)
        self._live_timer.timeout.connect(self._start_live_write)
        for axis in "xyz":
            for name in (f"spinBox_range_{axis}", f"spinBox_off_{axis}_um", f"spinBox_offExtra_{axis}_V"):
                getattr(self.ui, name).valueChanged.connect(self.geometry_changed)
        for index in range(4):
            getattr(self.ui, f"checkBox_laser{index}").toggled.connect(
                lambda checked, index=index: self.queue_registers({f"laser_{index + 1}_enable": int(checked)})
            )
        for index in range(1, 13):
            getattr(self.ui, f"comboLaserSeq_{index}").currentIndexChanged.connect(self.sequence_changed)
        self.bridge = FlareLogBridge(self)
        self.bridge.line.connect(self.log)
        self.loggers = [
            logging.getLogger(name)
            for name in (
                "brighteyes_mcs.hardware.flare",
                "brighteyes_mcs.acquisition.flare",
                "brighteyes_mcs.acquisition.detectors.flare.config",
            )
        ]
        for action in (
            "connect",
            "disconnect",
            "status",
            "read",
            "write",
            "read_all",
            "stop",
            "reset",
        ):
            getattr(self.ui, "pushButton_flare_" + action).clicked.connect(
                lambda checked=False, action=action: self.diagnostic(action)
            )
        self.ui.pushButton_flare_clear_log.clicked.connect(self.ui.plainTextEdit_flare_log.clear)
        self.ui.pushButton_flare_copy_log.clicked.connect(
            lambda: QApplication.clipboard().setText(self.ui.plainTextEdit_flare_log.toPlainText())
        )
        self.ui.pushButton_flare_export_log.clicked.connect(self.export_log)
        self.ui.tableWidget_flare_registers.cellClicked.connect(self.select_register)
        self.ui.tableWidget_flare_registers.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.ui.tableWidget_flare_registers.horizontalHeader().setStretchLastSection(True)
        self._channel_items = []
        self.ui.checkBox_DFD.toggled.connect(self.update_display)
        self.ui.checkBox_DFD.toggled.connect(self._dfd_toggled)
        self.ui.comboBox_spad_channels.currentTextChanged.connect(self.update_display)
        self.ui.spinBox_flare_reference_decimation.valueChanged.connect(self.update_display)
        self._refresh_reference_decimation()

    def _ensure_processes(self):
        if self._process_pool is not None and not self._pool_failed:
            return
        context = multiprocessing.get_context("spawn")
        if self._process_pool is not None:
            self._process_pool.shutdown(wait=False, cancel_futures=True)
        if self._ipc_manager is None:
            self._ipc_manager = context.Manager()
        previous = self.live_controls
        # A dead process may have held the old I/O lock. Retain desired values
        # but create fresh locks so an explicit Stop/Reset can still proceed.
        self.live_controls = FlareLiveControls(self._ipc_manager)
        self.live_controls.request(dict(previous._requested), geometry=previous._geometry)
        if self._log_mailbox is None:
            self._log_mailbox = self._ipc_manager.Queue(maxsize=256)
        self._process_pool = ProcessPoolExecutor(
            max_workers=3, mp_context=context, initializer=initialize_worker,
            initargs=(self._log_mailbox,),
        )
        self._pool_failed = False
        self._log_timer.start()

    def _drain_worker_logs(self):
        for _ in range(32):
            try:
                message = self._log_mailbox.get_nowait()
            except queue.Empty:
                break
            if self.selected:
                self.log(message)

    def _task(self, action, settings=None, **arguments):
        self._ensure_processes()
        return FlareTask(action, settings, self.live_controls, arguments)

    def configuration_fields(self):
        fields = {}
        for name in FlareSettings.__dataclass_fields__:
            value = getattr(FlareSettings(), name)
            prefix = (
                "lineEdit"
                if isinstance(value, str)
                else "spinBox"
                if isinstance(value, int)
                else "doubleSpinBox"
            )
            if name == "mode":
                prefix = "comboBox"
            fields[f"flare_{name}"] = (
                f"Flare {name}",
                type(value),
                getattr(self.ui, f"{prefix}_flare_{name}"),
                False,
            )
        return fields

    def settings(self):
        values = {}
        for key, (_, kind, widget, _) in self.configuration_fields().items():
            values[key] = (
                widget.currentText()
                if key == "flare_mode"
                else widget.text()
                if kind is str
                else widget.value()
            )
        return FlareSettings.from_legacy(values).validate()

    def log(self, message):
        self.ui.plainTextEdit_flare_log.appendPlainText(
            f"{datetime.now().astimezone().isoformat(timespec='seconds')} {message}"
        )

    def export_log(self):
        name, _ = QFileDialog.getSaveFileName(
            self.window, "Export Flare log", "flare.log", "Logs (*.log)"
        )
        if name:
            try:
                with open(name, "w", encoding="utf-8") as output:
                    output.write(self.ui.plainTextEdit_flare_log.toPlainText())
            except OSError as error:
                self.log(str(error))

    def convert(self, metadata_filename, output_filename):
        if self.conversion_job and self.conversion_job.isRunning():
            self.log("Wait for the current Flare conversion")
            return

        try:
            task = self._task("convert", metadata=metadata_filename, output=output_filename)
        except Exception as error:
            self._converted(None, str(error))
            return
        self.conversion_job = FlareJob(task, self)
        self.conversion_job.result.connect(self._converted)
        self.conversion_job.start()
        self.ui.statusBar.showMessage("Converting Flare recording...")

    def _converted(self, filename, error):
        if error:
            self.log(error)
            self.ui.statusBar.showMessage("Flare conversion failed: " + error, 15000)
        else:
            self.window.last_saved_filename = filename
            self.ui.pushButton_externalProgram.setEnabled(True)
            self.ui.statusBar.showMessage("Flare recording converted: " + filename, 15000)

    def selection_changed(self, detector):
        selected = detector_uses_flare(detector)
        if selected == self.selected:
            return
        self.selected = selected
        if selected:
            self._display_geometry = None
            self._clock_label = self.ui.label_120.text()
            self.ui.label_120.setText("Clock Base 40M x")
            for name, value in (("spinBox_DFD_nbins", 91), ("spinBox_clk_base_multiplier", 1)):
                widget = getattr(self.ui, name)
                self._profile_widgets[name] = (widget.value(), widget.isEnabled(), widget.toolTip())
                with QSignalBlocker(widget):
                    widget.setValue(value)
                widget.setEnabled(False)
                widget.setToolTip("Flare's current DFD clock profile is fixed at 40 MHz, 91 phase bins and six sequence slots")
            self.window.DFD_nbins = 91
            self.live_controls = FlareLiveControls()
            for logger in self.loggers:
                logger.addHandler(self.bridge)
            # Keep prior enablement to restore legacy controls exactly on exit.
            for name in (
                "checkBox_fifo_analog",
                "checkBox_ttmActivate",
                "checkBox_uttmActivate",
                "checkBox_pispad23ttmActivate",
                "checkBox_fcs_preview",
            ):
                widget = getattr(self.ui, name)
                self._disabled[name] = widget.isEnabled()
                # Checked legacy options remain editable so the user can clear them.
                widget.setEnabled(widget.isChecked())
            self.ui.tabWidget_fpga_backends.setCurrentWidget(self.ui.tab_fpga_flare)
        else:
            self._live_timer.stop()
            self.live_controls.discard_pending()
            self._repeat.stop()
            self._status_timer.stop()
            self.connected = False
            for name, (value, enabled, tooltip) in self._profile_widgets.items():
                widget = getattr(self.ui, name)
                with QSignalBlocker(widget):
                    widget.setValue(value)
                widget.setEnabled(enabled)
                widget.setToolTip(tooltip)
            self._profile_widgets.clear()
            self.window.DFD_nbins = int(self.ui.spinBox_DFD_nbins.value())
            self.ui.label_120.setText(self._clock_label)
            for logger in self.loggers:
                logger.removeHandler(self.bridge)
            for name, enabled in self._disabled.items():
                getattr(self.ui, name).setEnabled(enabled)
            self._disabled.clear()
        self.ui.label_flare_status.setText(
            "Disconnected. Slave acquisition awaits external-timing firmware."
        )
        if self.selected:
            self.update_display()
            if self.ui.checkBox_DFD.isChecked():
                self._start_reference_write()
        else:
            self._sync_channel_items(None)
            self._refresh_reference_decimation()

    def _display_layout(self):
        if not self.selected or not self.ui.checkBox_DFD.isChecked():
            return None
        physical = int(self.ui.comboBox_spad_channels.currentText())
        layout = (self.last_snapshot or {}).get("dfd_layout")
        if self._acquisition_active() and layout and layout["detector_channels"] == physical:
            return layout
        firmware = (self._discovery or {}).get("firmware", {})
        formats = firmware.get("supported_dfd_formats", [])
        version = 2 if any(f in formats for f in ("DFD2", "DFD3")) else 1
        return dict(detector_channels=physical, stream_channels=physical + version,
                    reference_channel_index=physical + version - 1,
                    extra_channel_index=physical if version == 2 else None)

    def _refresh_reference_decimation(self):
        widget = self.ui.spinBox_flare_reference_decimation
        requested = widget.value()
        firmware = (self._discovery or {}).get("firmware")
        supported = bool(firmware.get("board_capabilities", 0) & 0x400) if firmware else None
        enabled = self.selected
        widget.setEnabled(enabled and supported is not False)
        active = self._reference_active if self._acquisition_active() else None
        if active:
            factor = active.get(REFERENCE_FACTOR, 1)
            legacy = active.get("reference_histogram_counting") == "legacy_shared_detector_holdoff"
            text = "Active: legacy reference counting (factor 1)" if legacy else f"Active: 1 in {factor} triggers"
            if not legacy and factor != requested:
                target = "next preview run" if self.preview else "next acquisition"
                text += f"; requested 1 in {requested} for {target}"
        elif supported is False:
            text = "Legacy reference counting (factor 1); decimation unavailable"
        else:
            text = f"Requested: 1 in {requested} triggers"
            if supported is None:
                text += "; support checked on connection"
        self.ui.label_flare_reference_decimation_status.setText(text + "; calibration full-rate")

    def _dfd_toggled(self, enabled):
        if enabled and self.selected:
            self._start_reference_write()

    def _start_reference_write(self):
        """Submit the desired factor immediately on entering Flare DFD mode."""
        if not self.selected:
            return
        try:
            task = self._task("reference_factor", self.settings(),
                              value=self.ui.spinBox_flare_reference_decimation.value())
            job = FlareJob(task, self)
        except Exception as error:
            self.log("Reference decimation write could not start: " + str(error))
            return
        self.register_jobs.add(job)
        self.ui.comboBox_detector_model.setEnabled(False)
        job.result.connect(self._reference_written)
        job.finished.connect(lambda job=job: self._diagnostic_finished(job))
        job.start()

    def _reference_written(self, result, error):
        if not error and result and result["result"] is None:
            if self.selected:
                self._discovery = result["discovery"]
                self.update_display()
                self.log("Reference decimation unavailable on this firmware; using legacy counting")
            return
        self._diagnostic_result(result, error)

    def _sync_channel_items(self, layout):
        combo = self.ui.comboBox_plot_channel
        wanted = [] if layout is None else [str(i) for i in range(layout["stream_channels"])]
        with QSignalBlocker(combo):
            for text in self._channel_items[:]:
                if text not in wanted:
                    index = combo.findText(text)
                    if index >= 0:
                        combo.removeItem(index)
                    self._channel_items.remove(text)
            for text in wanted:
                if combo.findText(text) < 0:
                    combo.addItem(text)
                    self._channel_items.append(text)
                combo.setItemData(combo.findText(text), "", Qt.ItemDataRole.ToolTipRole)
            if layout:
                for key, label in (("extra_channel_index", "Extra (unconnected)"),
                                   ("reference_channel_index", "Laser reference")):
                    index = layout.get(key)
                    if index is not None:
                        combo.setItemData(combo.findText(str(index)), label, Qt.ItemDataRole.ToolTipRole)

    def poll_status(self):
        if (
            self.selected
            and self.connected
            and not (self.preview and not self.stopping)
            and not (self.run_job and self.run_job.isRunning())
        ):
            self.diagnostic("status")

    def queue_registers(self, registers, *, geometry=None):
        if not self.selected:
            return
        if self._modern_scan() and self._acquisition_active():
            # V3 freezes scan geometry and counting controls while queues exist.
            # Preview reads current widgets when configuring its next finite run.
            return
        self.live_controls.request(registers, geometry=geometry)
        if (self.connected or (self.run_job and self.run_job.isRunning())) and not self._live_timer.isActive():
            self._live_timer.start()

    def sequence_changed(self, *_):
        if not self.selected:
            return
        try:
            values = {f"laser_sequence_{i}": getattr(self.ui, f"comboLaserSeq_{i}").currentText() for i in range(1, 13)}
            self.queue_registers({"laser_excitation_sequence": pack_sequence(sequence_from_gui(values))})
        except ValueError as error:
            self.log(str(error))

    def _modern_scan(self):
        from ...acquisition.detectors.flare.v19 import supported
        firmware = (self.last_snapshot or {}).get("firmware") or (self._discovery or {}).get("firmware", {})
        return supported(firmware)

    def geometry_changed(self, *_, navigation=False):
        if not self.selected:
            return
        try:
            # Only read spatial widgets here; full profiles include plugins and
            # are needlessly expensive on every wheel/drag event.
            values = {key: getattr(self.ui, widget).value() for key, widget in (
                ("nx", "spinBox_nx"), ("ny", "spinBox_ny"), ("nframe", "spinBox_nframe"),
            )}
            for axis in "xyz":
                for key, widget in (
                    (f"range_{axis}", f"spinBox_range_{axis}"),
                    (f"offset_{axis}_um", f"spinBox_off_{axis}_um"),
                    (f"offsetExtra_{axis}", f"spinBox_offExtra_{axis}_V"),
                    (f"calib_{axis}", f"spinBox_calib_{axis}"),
                    (f"min_{axis}_V", f"spinBox_min_{axis}_V"),
                    (f"max_{axis}_V", f"spinBox_max_{axis}_V"),
                ):
                    values[key] = getattr(self.ui, widget).value()
            registers = axis_registers_from_gui(values)
            self._preserve_view = navigation
            self._display_geometry = dict(values)
            if not ((self.ui.checkBox_DFD.isChecked() or self._modern_scan()) and self._acquisition_active() and not self.preview):
                self.queue_registers(registers, geometry=values)
            if isinstance(getattr(self.window, "currentImage", None), np.ndarray):
                # Remap cached pixels in this mouse event, before the 80 ms
                # write timer or any HTTP response. Do not reprocess the image.
                self.plot_image(transform_only=True, fit_view=not navigation)
        except Exception as error:
            self.log(str(error))

    def navigate_preview(self):
        """Keep the mouse's view and update controls once without NI callbacks."""
        if (self.ui.checkBox_DFD.isChecked() or self._modern_scan()) and self._acquisition_active() and not self.preview:
            return  # DFD firmware freezes its scan layout through draining; view-only navigation remains available.
        projection = self.ui.comboBox_view_projection.currentText()
        if projection not in ("xy", "yx"):
            return
        bounds = [self.window.im_widget_plot_item.getAxis(axis).range for axis in ("bottom", "left")]
        # Match FPGA-SPAD navigation: viewport padding must not stretch the
        # scan. A common span keeps square sampling square in a wide/tall view.
        span = min(abs(high - low) for low, high in bounds)
        edits = []
        for axis, (low, high) in zip(projection, bounds, strict=True):
            edits.extend((
                (getattr(self.ui, f"spinBox_range_{axis}"), span),
                (getattr(self.ui, f"spinBox_off_{axis}_um"), (high + low) / 2),
            ))
        blockers = [QSignalBlocker(widget) for widget, _ in edits]
        try:
            for widget, value in edits:
                widget.setValue(value)
        finally:
            del blockers
        update_labels = getattr(self.window, "_update_offset_voltage_labels", None)
        if update_labels:
            update_labels()
        self.window.updateLabelPixelSize()
        self.geometry_changed(navigation=True)

    def preserve_preview_view(self, *_):
        if self.selected:
            self._preserve_view = True

    def _start_live_write(self):
        if (
            not self.selected or not self.live_controls.has_pending()
            or (self.live_job and self.live_job.isRunning())
        ):
            return
        try:
            settings = self.settings()
            task = self._task("live", settings)
        except Exception as error:
            self.log(str(error))
            self.ui.statusBar.showMessage("Flare worker could not start: " + str(error), 0)
            return
        self.live_job = FlareJob(task, self)
        self.live_job.result.connect(self._live_result)
        self.live_job.finished.connect(self._live_finished)
        self.ui.comboBox_detector_model.setEnabled(False)
        self.live_job.start()

    def _live_result(self, result, error):
        if not self.selected:
            return
        if error:
            self.log(error)
            self.ui.statusBar.showMessage(error, 15000)
        elif result:
            self.log("Live registers: " + json.dumps(result))

    def _live_finished(self):
        job = self.live_job
        self.live_job = None
        if job is not None:
            job.deleteLater()
        if not self._acquisition_active() and not self.register_jobs and not (self.job and self.job.isRunning()):
            self.ui.comboBox_detector_model.setEnabled(True)
        if self.selected and self.live_controls.has_pending():
            self._live_timer.start()

    def _acquisition_active(self):
        return bool(
            (self.run_job and self.run_job.isRunning()) or self._repeat.isActive()
            or getattr(self.window, "started_preview", False) is True
            or getattr(self.window, "started_normal", False) is True
        )

    def _busy(self, active):
        for name in (
            "pushButton_previewStart",
            "pushButton_acquisitionStart",
            "comboBox_detector_model",
            "comboBox_flare_mode",
            "pushButton_fpga_connection_cmd",
            "pushButton_flare_connect",
            "pushButton_flare_disconnect",
            "pushButton_flare_reset",
        ):
            getattr(self.ui, name).setEnabled(not active)
        self.ui.pushButton_stop.setEnabled(active)
        frozen = (
            "spinBox_nx",
            "spinBox_ny",
            "spinBox_nframe",
            "spinBox_nrepetition",
            "spinBox_time_bin_per_px",
            "spinBox_timeresolution",
            "comboBox_spad_channels",
            "spinBox_range_x",
            "spinBox_range_y",
            "spinBox_range_z",
            "spinBox_off_x_um",
            "spinBox_off_y_um",
            "spinBox_off_z_um",
            "spinBox_calib_x",
            "spinBox_calib_y",
            "spinBox_calib_z",
            "checkBox_rawStreamAcquisition",
            "checkBox_flare_dummy",
            "comboBox_fingerprint",
            "checkBox_fcs_preview",
            "checkBox_DFD",
            "checkBox_fifo_analog",
            "checkBox_ttmActivate",
            "checkBox_uttmActivate",
            "checkBox_pispad23ttmActivate",
        )
        frozen += ("checkBox_circular", "spinBox_circular_points", "spinBox_circular_repetition",
                   "spinBox_circular_radius_nm", "checkBox_lissajous")
        frozen += tuple(
            widget.objectName()
            for _, _, widget, _ in self.configuration_fields().values()
            if widget.objectName() != "comboBox_flare_mode"
        )
        # Spatial edits only change DAC arrays; stream dimensions stay fixed.
        frozen = tuple(name for name in frozen if name not in (
            *(f"spinBox_range_{axis}" for axis in "xyz"),
            *(f"spinBox_off_{axis}_um" for axis in "xyz"),
        ))
        if self.ui.checkBox_DFD.isChecked() or self._modern_scan():
            # XY preview geometry is read afresh between finite frames. Z
            # remains unsupported by the DFD REST configuration.
            frozen += tuple(name for axis in ("z" if self.preview else "xyz") for name in (
                f"spinBox_range_{axis}", f"spinBox_off_{axis}_um", f"spinBox_offExtra_{axis}_V",
            ))
            frozen += tuple(f"checkBox_laser{i}" for i in range(4))
            frozen += tuple(f"comboLaserSeq_{i}" for i in range(1, 13))
            frozen += ("checkBox_DFD_LaserDebug",)
        if active:
            if not self._frozen:
                self._frozen = {name: getattr(self.ui, name).isEnabled() for name in frozen}
            for name in self._frozen:
                getattr(self.ui, name).setEnabled(False)
        else:
            for name, enabled in self._frozen.items():
                getattr(self.ui, name).setEnabled(enabled)
            self._frozen = {}
            if self.register_jobs or (self.live_job and self.live_job.isRunning()):
                self.ui.comboBox_detector_model.setEnabled(False)

    def update_display(self):
        self._refresh_reference_decimation()
        layout = self._display_layout()
        self._sync_channel_items(layout)
        if not self.selected:
            return
        channels = int(self.ui.comboBox_spad_channels.currentText())
        text = self.ui.comboBox_plot_channel.currentText()
        mask = np.asarray(getattr(self.window, "fingerprint_mask", np.ones(channels))).reshape(-1)
        self.display_channels = tuple(
            i
            for i in range(channels)
            if i < len(mask) and mask[i] and (not text.isdigit() or i == int(text))
        )
        role = ""
        if layout and text.isdigit():
            index = int(text)
            if channels <= index < layout["stream_channels"]:
                self.display_channels = (index,)
                role = ("Laser reference" if index == layout["reference_channel_index"]
                        else "Extra (unconnected)")
                if index == layout["reference_channel_index"]:
                    role += " — " + self.ui.label_flare_reference_decimation_status.text()
        self.ui.label_plot_channel.setText(f"Ch. selected: {text}" + (f" — {role}" if role else ""))
        if self._display is not None:
            self._display["channels"] = self.display_channels
        if self.last_snapshot and "hcl_image" in self.last_snapshot:
            self.plot_image()

    def diagnostic(self, action):
        if not self.selected:
            self.log("Select TCP/IP - FPGA Flare before using device controls")
            return
        if action == "disconnect":
            if self.run_job and self.run_job.isRunning():
                self.log("Stop the Flare run before disconnecting")
                return
            self.connected = False
            self._live_timer.stop()
            self.live_controls.discard_pending()
            self._status_timer.stop()
            self.ui.label_flare_status.setText("Disconnected")
            return
        if action == "stop" and (
            self.runner or self._repeat.isActive() or (self.run_job and self.run_job.isRunning())
        ):
            self.stop()
            return
        if action == "reset" and (
            (self.run_job and self.run_job.isRunning()) or self._repeat.isActive()
        ):
            self.log("Stop the local acquisition before resetting Flare")
            return
        if action not in ("read", "write", "read_all") and self.job and self.job.isRunning():
            if action == "reset":
                self._pending_reset = True
                self.ui.statusBar.showMessage("Reset requested; waiting for the current Flare request.")
                return
            self.log("Wait for the current Flare control request")
            return
        try:
            settings = self.settings()
            name = self.ui.lineEdit_flare_register.text().strip()
            value = json.loads(self.ui.lineEdit_flare_value.text()) if action == "write" else None
            cached_discovery = self._discovery
            task = self._task(action, settings, name=name, value=value, discovery=cached_discovery)
        except Exception as error:
            self.log(str(error))
            self.ui.statusBar.showMessage("Flare request could not start: " + str(error), 0)
            return

        job = FlareJob(task, self)
        if action in ("read", "write", "read_all"):
            self.register_jobs.add(job)
        else:
            self.job = job
        job.result.connect(self._diagnostic_result)
        self.ui.comboBox_detector_model.setEnabled(False)
        job.finished.connect(lambda job=job: self._diagnostic_finished(job))
        job.start()

    def _diagnostic_finished(self, job):
        self.register_jobs.discard(job)
        if self.job is job:
            self.job = None
        if (
            not self._acquisition_active() and not self.register_jobs
            and not (self.job and self.job.isRunning())
            and not (self.live_job and self.live_job.isRunning())
        ):
            self.ui.comboBox_detector_model.setEnabled(True)
        if job is not None:
            job.deleteLater()
        if self._pending_reset:
            self._pending_reset = False
            self.diagnostic("reset")

    def _diagnostic_result(self, result, error):
        if error:
            self.log(error)
            self.ui.label_flare_status.setText(error)
            self.ui.statusBar.showMessage("Flare request failed: " + error, 0)
            return
        if not self.selected:
            return
        self.connected = True
        discovery = result["discovery"]
        self._discovery = discovery
        self.update_display()
        self._status_timer.start()
        self._catalog = {row["name"]: row for row in discovery["registers"]}
        if self.live_controls.has_pending():
            self._live_timer.start()
        firmware = discovery["firmware"]
        self.ui.label_flare_status.setText(
            f"Connected: board {firmware.get('board_id')}, schema {firmware.get('schema_version')}, "
            f"board firmware {firmware.get('board_firmware_version')}, clock {firmware.get('clock_hz')} Hz. "
            f"DMA: {discovery['status'].get('dma')}"
        )
        if result["action"] == "status":
            return
        if result["action"] == "reset":
            self._busy_failures.clear()
            self.ui.statusBar.showMessage("Flare reset completed. You can start Preview again.", 15000)
        values = result["result"] if result["action"] == "read_all" else {}
        if result["action"] in ("read", "write"):
            values = {result["result"]["name"]: result["result"]["value"]}
            self.ui.lineEdit_flare_value.setText(json.dumps(result["result"]["value"]))
        table = self.ui.tableWidget_flare_registers
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(self._catalog))
            for index, (name, row) in enumerate(self._catalog.items()):
                cells = (
                    name, row.get("address_hex", str(row.get("address"))),
                    row.get("type"), row.get("access"), row.get("write_policy"),
                )
                for col, text in enumerate(cells):
                    item = table.item(index, col)
                    if item is None or item.text() != str(text):
                        table.setItem(index, col, QTableWidgetItem(str(text)))
                if name in values:
                    table.setItem(index, 5, QTableWidgetItem(json.dumps(values[name])))
        finally:
            table.setUpdatesEnabled(True)
        self.log(f"{result['action']}: {json.dumps(result['result'])}")

    def select_register(self, row, column):
        self.ui.lineEdit_flare_register.setText(
            self.ui.tableWidget_flare_registers.item(row, 0).text()
        )
        self.ui.pushButton_flare_write.setEnabled(True)

    def begin(self, preview=False):
        if not self.selected or (self.run_job and self.run_job.isRunning()):
            return
        if self.job and self.job.isRunning():
            self.log("Wait for the Flare control request before starting")
            return
        try:
            settings = self.settings()
            if getattr(self.window, "runBatchFCS", False) is True:
                raise ValueError("Flare batch acquisition is not yet supported")
            if settings.mode == "slave":
                raise ValueError(
                    "Flare slave acquisition is unavailable until external NI timing is supported by firmware"
                )
            if self.window.mcs_manager.is_connected:
                raise ValueError("Disconnect the NI FPGA before starting Flare master mode")
            unsupported = (
                "checkBox_fifo_analog",
                "checkBox_ttmActivate",
                "checkBox_uttmActivate",
                "checkBox_pispad23ttmActivate",
                "checkBox_pulsing_forced",
                "checkBox_fcs_preview",
            )
            active = [
                getattr(self.ui, key).text()
                for key in unsupported
                if getattr(self.ui, key).isChecked()
            ]
            if active:
                raise ValueError(
                    "Disable unsupported Flare options before starting: " + ", ".join(active)
                )
            values = dict(self.window.getGUI_data())
            values["dfd_enable"] = self.ui.checkBox_DFD.isChecked()
            values[REFERENCE_FACTOR] = self.ui.spinBox_flare_reference_decimation.value()
            for i in range(4):
                values[f"laser_{i + 1}_enable"] = getattr(self.ui, f"checkBox_laser{i}").isChecked()
            if values["dfd_enable"]:
                for i in range(1, 13):
                    values[f"laser_sequence_{i}"] = int(getattr(self.ui, f"comboLaserSeq_{i}").currentText())
                values["DFD_laser_debug"] = self.ui.checkBox_DFD_LaserDebug.isChecked()
            if values.get("fingerprint_visualization", "Cumulative") != "Cumulative":
                raise ValueError("Select Cumulative fingerprint visualization for Flare")
            unsupported_flags = [
                key
                for key in (
                    "fcs",
                    "lissajous_active",
                    "slave_mode_enable",
                    "sw_trigger_enable",
                )
                if values.get(key)
            ]
            if unsupported_flags:
                raise ValueError("Flare does not support: " + ", ".join(unsupported_flags))
            if values.get("circular_active"):
                self.window.define_circular(int(values["circular_points"]))
                for axis in "xyz":
                    values[f"circular_scan_{axis}_volts"] = getattr(self.window, f"{axis.upper()}_array").tolist()
            filename = None if preview else self.window.defineFilename()
            if filename:
                path = Path(filename)
                if any(
                    p.exists()
                    for p in (path, path.with_suffix(".flare.raw"), path.with_suffix(".flare.json"))
                ):
                    filename = str(
                        path.with_name(
                            path.stem + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".h5"
                        )
                    )
            raw_only = self.ui.checkBox_rawStreamAcquisition.isChecked()
            dummy = self.ui.checkBox_flare_dummy.isChecked()
            if values["projection"] not in ("xy", "yx"):
                raise ValueError("Flare currently supports XY/YX preview only")
            if (values["preview_channel"] != "Sum" and not values["preview_channel"].isdigit()
                and not (values["dfd_enable"] and (values["preview_channel"] == "RGBDFD"
                     or values["preview_channel"].startswith(("LIFETIME", "COLOR_LIFETIME", "QUALITY"))))):
                raise ValueError("Select Sum or a detector channel for Flare preview")
            self.update_display()
            registers = axis_registers_from_gui(values)
            # Do not invent requests for absent legacy laser controls. Explicit
            # toggles (including off) are retained in the shared desired state.
            registers.update({
                f"laser_{index + 1}_enable": 1 for index in range(4)
                if getattr(self.ui, f"checkBox_laser{index}").isChecked()
            })
            if values["dfd_enable"] or self._modern_scan():
                self.live_controls.discard_pending()
            else:
                self.live_controls.request(registers, geometry=values)
            self._ensure_processes()
            cancel = self._ipc_manager.Event()
            display = self._ipc_manager.dict(channels=self.display_channels)
            snapshots = self._ipc_manager.Queue(maxsize=1)
        except Exception as error:
            self.log(str(error))
            self.ui.statusBar.showMessage(str(error), 15000)
            return
        # Finite runs belong to one continuous preview session. Keep the last
        # image visible until each pixel is replaced by the next scan.
        initial_image = (
            self.last_snapshot["image"]
            if preview and self.preview and not self.stopping and self.last_snapshot
            else None
        )
        if initial_image is None:
            self._preserve_view = False
            self._display_geometry = None
            self._reference_active = None
        self.preview, self.stopping = preview, False
        self.window.started_preview, self.window.started_normal = preview, not preview
        self.window.do_not_save = preview
        self.window.dfd_enable = values["dfd_enable"]
        self.window.raw_stream_mode = raw_only
        if values["dfd_enable"]:
            self.window.DFD_nbins = 91
        self._busy(True)
        if initial_image is None:
            self.window._auto_lifetime_correction_completed = False
        sync_correction = getattr(self.window, "_syncAutoLifetimeCorrectionWithPlotSelection", None)
        if sync_correction:
            sync_correction()
        self.window._set_program_state(
            self.window.PROGRAM_STATE_PREVIEW if preview else self.window.PROGRAM_STATE_ACQUISITION,
            "flare_started",
        )
        if initial_image is None:
            self.ui.statusBar.showMessage(
                "Starting Flare preview..." if preview else "Starting Flare acquisition...", 5000,
            )
        self.window.last_requested_filename = filename or ""
        self.window.currentImage_size = np.asarray(
            [values[f"range_{axis}"] for axis in "xyz"], dtype=float
        )
        self.window.currentImage_pos = np.asarray(
            [values[f"offset_{axis}_um"] for axis in "xyz"], dtype=float
        )
        self.window.currentImage_pixels = np.asarray([values["nx"], values["ny"], values["nframe"]])
        if preview:
            self.window.preview_run_id += 1
            self.window.last_preview_started_at = self.window._make_status_timestamp()
        else:
            self.window.acquisition_run_id += 1
            self.window.last_acquisition_started_at = self.window._make_status_timestamp()

        self._cancel = cancel
        self._display = display
        task = self._task(
            "acquire", settings, values=values, preview=preview, dummy=dummy,
            filename=filename, raw_only=raw_only, initial_image=initial_image,
            cancel=self._cancel, display=self._display,
            snapshots=snapshots,
        )
        self.run_job = FlareJob(task, self)
        self.run_job.snapshot.connect(self.render)
        self.run_job.result.connect(self._acquisition_result)
        self.run_job.finished.connect(self._run_finished)
        self.run_job.start()
        self._refresh_reference_decimation()

    def render(self, snapshot):
        previous_geometry = (self.last_snapshot or {}).get("geometry")
        geometry = snapshot.get("geometry")
        fit_view = self._display_geometry is None and not self._preserve_view and geometry is not None and (
            previous_geometry is None or any(
                previous_geometry[key] != geometry[key]
                for axis in "xy" for key in (f"range_{axis}", f"offset_{axis}_um")
            )
        )
        self.last_snapshot = snapshot
        if self._modern_scan() and self._acquisition_active():
            # Acquisition can discover V3 before an explicit Connect action.
            # Extend the frozen controls once that discovery reaches Qt.
            for axis in ("z" if self.preview else "xyz"):
                for name in (f"spinBox_range_{axis}", f"spinBox_off_{axis}_um", f"spinBox_offExtra_{axis}_V"):
                    if name not in self._frozen:
                        self._frozen[name] = getattr(self.ui, name).isEnabled()
                    getattr(self.ui, name).setEnabled(False)
        if "dfd_layout" in snapshot:
            self._reference_active = snapshot["dfd_layout"]
            self.update_display()
        self.connected = True
        if not self._status_timer.isActive():
            self._status_timer.start()
        self.ui.label_flare_status.setText(
            f"Bins {snapshot['bins']}/{snapshot['total_bins']}; received {snapshot['receiver_bytes']}/{snapshot['expected_bytes']} bytes; "
            + (f"DMA packet: {snapshot['dma_packet_bins']}; " if "dma_packet_bins" in snapshot else "")
            + f"DMA {snapshot['status'].get('dma')}"
        )
        self.ui.progressBar_frame.setMaximum(100)
        self.ui.progressBar_frame.setValue(int(100 * snapshot["bins"] / snapshot["total_bins"]))
        image = snapshot["image"]
        self.window.currentImage = image
        self.plot_image(image, fit_view=fit_view)
        dim = int(np.sqrt(len(snapshot["fingerprint"])))
        duration = max(snapshot["bins"] * snapshot.get("bin_seconds", 1), 1e-12)
        fingerprint = snapshot["fingerprint"].reshape(dim, dim).astype(float) / duration
        self.window.draw_fingerprint(fingerprint, np.zeros_like(fingerprint))
        if "dfd_hist_sum" in snapshot:
            live_seconds = snapshot.get("dfd_live_seconds", snapshot["bin_seconds"] * snapshot["dfd_live_records"])
            hist_seconds = snapshot.get("dfd_hist_seconds", snapshot["bin_seconds"] * snapshot["dfd_hist_records"])
            self.window.renderDfdTrace(
                snapshot["dfd_hist_live"] / max(live_seconds / snapshot["dfd_bins"], 1e-15),
                snapshot["dfd_hist_sum"] / max(hist_seconds / snapshot["dfd_bins"], 1e-15),
                snapshot["dfd_laser_hz"], snapshot["dfd_bins"],
            )
            auto_correct = getattr(self.window, "_maybeAutoCorrectLifetimeAfterFirstFrameProgress", None)
            if auto_correct:
                auto_correct(snapshot["bins"], image.shape[0] * image.shape[1])
        trace = snapshot.get("trace")
        if trace is not None and self.ui.checkBox_trace_on.isChecked():
            step = snapshot.get("bin_seconds", 1)
            self.window.trace_widget.plot(
                np.arange(snapshot["bins"] - len(trace), snapshot["bins"]) * step, trace, clear=True
            )

    def plot_image(self, image=None, *, fit_view=False, transform_only=False):
        """Display requested coordinates immediately, independent of board I/O."""
        if image is None:
            image = self.window.currentImage
        geometry = self._display_geometry or (self.last_snapshot or {}).get("geometry")
        snapshot = self.last_snapshot or {}
        channel = self.ui.comboBox_plot_channel.currentText()
        color_lifetime = False
        if not transform_only and "hcl_image" in snapshot:
            if channel == "RGBDFD":
                image = snapshot["rgb_image"]
            elif channel.startswith(("LIFETIME", "COLOR_LIFETIME")) and channel != "LIFETIME":
                image = snapshot["hcl_image"]
                color_lifetime = True
            elif channel in ("LIFETIME", "QUALITY"):
                image = snapshot["hcl_image"][:, :, 0 if channel == "LIFETIME" else 1]
        ranges = np.asarray(
            [geometry[f"range_{axis}"] if geometry else getattr(self.ui, f"spinBox_range_{axis}").value()
             for axis in "xyz"], dtype=float,
        )
        center = np.asarray(
            [geometry[f"offset_{axis}_um"] if geometry else getattr(self.ui, f"spinBox_off_{axis}_um").value()
             for axis in "xyz"], dtype=float,
        )
        self.window.currentImage_pos = center
        self.window.currentImage_size = ranges
        if self.ui.checkBox_showPreview.isChecked():
            position = tuple(center[:2] - ranges[:2] / 2)
            scale = (
                max(ranges[0] / max(1, image.shape[1]), 1e-12),
                max(ranges[1] / max(1, image.shape[0]), 1e-12),
            )
            yx = self.ui.comboBox_view_projection.currentText() == "yx"
            position = position[::-1] if yx else position
            scale = scale[::-1] if yx else scale
            if transform_only:
                transform = QTransform()
                transform.translate(*position)
                transform.scale(*scale)
                self.window.im_widget.getImageItem().setTransform(transform)
            else:
                displayed = image if yx else (image.transpose(1, 0, 2) if image.ndim == 3 else image.T)
                kwargs = dict(
                    autoLevels=self.ui.checkBox_autoscale_img.isChecked(),
                    autoRange=False, pos=position, scale=scale,
                )
                if color_lifetime:
                    period_ns = 1e9 / snapshot["dfd_laser_hz"]
                    self.window.im_widget.setFlimImage(
                        displayed, valid=displayed[:, :, 2], h_display_max=period_ns,
                        h_shift=self.ui.doubleSpinBox_delta_tau_ns.value() / period_ns,
                        render_mode=self.window.getLifetimeColorRenderMode(channel),
                        hue_display_range=self.window.getLifetimeHueDisplayRange(),
                        force_quality_full=self.window.getLifetimeForceQualityFull(), **kwargs,
                    )
                else:
                    self.window.im_widget.setImage(
                        displayed, levelMode="rgba" if displayed.ndim == 3 else "mono", **kwargs,
                    )
            if fit_view:
                bounds = [
                    (center[i] - max(ranges[i], 1e-12) / 2,
                     center[i] + max(ranges[i], 1e-12) / 2)
                    for i in range(2)
                ]
                if yx:
                    bounds.reverse()
                self.window.im_widget.getView().setRange(
                    xRange=bounds[0], yRange=bounds[1], padding=0,
                )

    def _acquisition_result(self, result, error):
        self.runner = None
        self._cancel = None
        self._display = None
        self.last_result = result
        if result and result.get("discovery"):
            self._discovery = result["discovery"]
        message = error or (result.get("error") if result else "Flare acquisition failed")
        if message:
            self.log(message)
        if result:
            status = result.get("after_stop_status", result.get("final_status", {}))
            self.ui.label_flare_status.setText(
                f"Capture {result.get('result')}; received {result.get('receiver_bytes', 0)} bytes; "
                f"hardware DMA: {status.get('dma', {})}. "
                + (
                    "Inspect status; Stop or Reset is a separate action."
                    if result.get("recovery_required")
                    else ""
                )
            )
        if self.preview and result and result.get("complete") and not self.stopping:
            # A finite preview frame ending is not the end of the preview session.
            self._busy_failures.clear()
            return
        if self.preview:
            self.stopping = True
        if result and result.get("complete") and not self.preview:
            filename = result.get("saved_filename", self.window.last_requested_filename)
            self.window.last_saved_filename = filename
            self.window.last_completed_filename = filename
            self.window.last_acquisition_completed_at = self.window._make_status_timestamp()
            self.window.completed_acquisition_count += 1
            self.window.ui.pushButton_externalProgram.setEnabled(
                not self.ui.checkBox_rawStreamAcquisition.isChecked()
            )
            self.window.plugin_signals.signal.emit("acquisitionDone " + filename)
        self.window.started_preview = self.window.started_normal = False
        self._busy(False)
        self._refresh_reference_decimation()
        complete = bool(result and result.get("complete"))
        self.window._set_program_state(
            self.window.PROGRAM_STATE_ACQUISITION_DONE
            if complete and not self.preview
            else self.window.PROGRAM_STATE_IDLE,
            "flare_completed" if complete else "flare_stopped",
        )
        if result and result.get("result") == "cancelled":
            self._busy_failures.clear()
            self.ui.statusBar.showMessage("Flare stopped", 15000)
        elif message:
            recovery = bool(result and result.get("recovery_required"))
            self.ui.statusBar.showMessage(
                ("Flare preview failed: " if self.preview else "Flare acquisition failed: ") + message
                + (". Flare may still be busy; use Stop or Reset in the Flare tab." if recovery else ""),
                0,
            )
            if "busy" in message.lower() or "errno=16" in message:
                now = time.monotonic()
                self._busy_failures = [stamp for stamp in self._busy_failures if now - stamp < 30]
                self._busy_failures.append(now)
                if len(self._busy_failures) >= 2 and self._reset_prompt is None:
                    self._offer_reset()
        else:
            self._busy_failures.clear()
            self.ui.statusBar.showMessage("Flare acquisition complete", 15000)

    def _offer_reset(self):
        prompt = QMessageBox(self.window)
        prompt.setWindowTitle("Flare is still busy")
        prompt.setIcon(QMessageBox.Icon.Warning)
        prompt.setText("Preview or acquisition could not start repeatedly because Flare is still busy.")
        prompt.setInformativeText(
            "Reset Flare now? This stops the board's current acquisition and returns DAC outputs to zero. "
            "After reset finishes, start Preview or Acquisition again."
        )
        prompt.setStandardButtons(QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel)
        prompt.setDefaultButton(QMessageBox.StandardButton.Cancel)
        self._reset_prompt = prompt

        def answered(button):
            self._reset_prompt = None
            self._busy_failures.clear()
            if button == QMessageBox.StandardButton.Reset:
                self.diagnostic("reset")
            prompt.deleteLater()

        prompt.finished.connect(answered)
        prompt.open()

    def _run_finished(self):
        job = self.run_job
        self.run_job = None
        if job is not None:
            job.deleteLater()
        if (
            self.preview
            and not self.stopping
            and self.last_result
            and self.last_result.get("complete")
        ):
            self._repeat.start(100)

    def stop(self):
        self.stopping = True
        self._repeat.stop()
        if self._cancel is not None:
            self._cancel.set()
        elif (
            self.preview
            and not (self.run_job and self.run_job.isRunning())
            and getattr(self.window, "started_preview", False)
        ):
            self._acquisition_result({"complete": False, "result": "cancelled"}, None)

    def close(self):
        if self._closed:
            return
        self._pending_reset = False
        if self._reset_prompt is not None:
            self._reset_prompt.reject()
        self._live_timer.stop()
        self.live_controls.discard_pending()
        self.stop()
        self._status_timer.stop()
        for job in (self.run_job, self.job, self.live_job, self.conversion_job, *self.register_jobs):
            if job and job.isRunning():
                # Requests have a finite timeout; keep the QObject alive until workers exit.
                if not job.wait(15000):
                    raise FlareShutdownError(
                        "Flare worker is still closing; retry closing the application"
                    )
            if job:
                job._timer.stop()
        if self._process_pool is not None:
            self._process_pool.shutdown(wait=True, cancel_futures=True)
            self._process_pool = None
        if self._ipc_manager is not None:
            self._log_timer.stop()
            self._ipc_manager.shutdown()
            self._ipc_manager = None
        for logger in self.loggers:
            logger.removeHandler(self.bridge)
        self._closed = True
