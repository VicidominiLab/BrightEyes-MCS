"""Qt adapter for explicitly selected Flare control and acquisition."""

from datetime import datetime
import json
import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QSignalBlocker, QThread, Signal, QTimer
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication, QFileDialog, QHeaderView, QTableWidgetItem

from ...acquisition.detectors.flare.config import (
    FlareSettings, axis_registers_from_gui, configuration_from_gui,
)
from ...acquisition.detectors.flare.controls import FlareLiveControls
from ...acquisition.detectors.flare.dfd import sequence_from_gui
from ...acquisition.detectors.flare.dfd_format import pack_sequence
from ...acquisition.detectors.models import detector_uses_flare


class FlareShutdownError(RuntimeError):
    """Keep the window alive until a bounded Flare request has returned."""


class FlareJob(QThread):
    result = Signal(object, object)
    snapshot = Signal(object)

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.result.emit(self.function(), None)
        except Exception as error:
            self.result.emit(None, str(error))


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

        def execute():
            from ...storage.raw import convert_raw_acquisition

            return convert_raw_acquisition(metadata_filename, output_filename)

        self.conversion_job = FlareJob(execute, self)
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
            self.queue_registers(registers, geometry=values)
            if isinstance(getattr(self.window, "currentImage", None), np.ndarray):
                # Remap cached pixels in this mouse event, before the 80 ms
                # write timer or any HTTP response. Do not reprocess the image.
                self.plot_image(transform_only=True, fit_view=not navigation)
        except Exception as error:
            self.log(str(error))

    def navigate_preview(self):
        """Keep the mouse's view and update controls once without NI callbacks."""
        if self.ui.checkBox_DFD.isChecked() and self._acquisition_active():
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
        except Exception as error:
            self.log(str(error))
            return
        controls = self.live_controls

        def execute():
            from ...hardware.flare import FlareClient

            client = FlareClient(settings)
            try:
                return controls.apply(client)
            finally:
                client.close()

        self.live_job = FlareJob(execute, self)
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
        if self.ui.checkBox_DFD.isChecked():
            frozen += tuple(name for axis in "xyz" for name in (
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
        if not self.selected:
            return
        channels = int(self.ui.comboBox_spad_channels.currentText())
        text = self.ui.comboBox_plot_channel.currentText()
        mask = np.asarray(self.window.fingerprint_mask).reshape(-1)
        self.display_channels = tuple(
            i
            for i in range(channels)
            if i < len(mask) and mask[i] and (not text.isdigit() or i == int(text))
        )
        if self.runner:
            self.runner.display_channels = self.display_channels
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
            self.log("Wait for the current Flare control request")
            return
        try:
            settings = self.settings()
            name = self.ui.lineEdit_flare_register.text().strip()
            value = json.loads(self.ui.lineEdit_flare_value.text()) if action == "write" else None
            cached_discovery = self._discovery
        except Exception as error:
            self.log(str(error))
            return

        def execute():
            from ...hardware.flare import FlareClient

            client = FlareClient(settings)
            try:
                if cached_discovery and action in ("read", "write", "read_all", "status"):
                    discovery = dict(cached_discovery)
                    client.catalog = {row["name"]: row for row in discovery["registers"]}
                    if action == "status":
                        discovery["status"] = client.status()
                else:
                    discovery = client.discover()
                result = discovery
                if action == "read":
                    result = client.read_register(name)
                elif action == "write":
                    result = self.live_controls.write(client, name, value)
                elif action == "read_all":
                    result = client.read_all()
                elif action in ("reset", "stop"):
                    with self.live_controls.io_lock:
                        result = {"before_command": client.status(), "command": client.command(action)}
                return {"action": action, "discovery": discovery, "result": result}
            finally:
                client.close()

        job = FlareJob(execute, self)
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

    def _diagnostic_result(self, result, error):
        if error:
            self.log(error)
            self.ui.label_flare_status.setText(error)
            return
        if not self.selected:
            return
        self.connected = True
        discovery = result["discovery"]
        self._discovery = discovery
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
            if values["dfd_enable"]:
                for i in range(1, 13):
                    values[f"laser_sequence_{i}"] = int(getattr(self.ui, f"comboLaserSeq_{i}").currentText())
                for i in range(4):
                    values[f"laser_{i + 1}_enable"] = getattr(self.ui, f"checkBox_laser{i}").isChecked()
                values["DFD_laser_debug"] = self.ui.checkBox_DFD_LaserDebug.isChecked()
            if values.get("fingerprint_visualization", "Cumulative") != "Cumulative":
                raise ValueError("Select Cumulative fingerprint visualization for Flare")
            unsupported_flags = [
                key
                for key in (
                    "fcs",
                    "circular_active",
                    "lissajous_active",
                    "slave_mode_enable",
                    "sw_trigger_enable",
                )
                if values.get(key)
            ]
            if unsupported_flags:
                raise ValueError("Flare does not support: " + ", ".join(unsupported_flags))
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
            if values["dfd_enable"]:
                self.live_controls.discard_pending()
            else:
                self.live_controls.request(registers, geometry=values)
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

        def acquire():
            from ...hardware.flare import FlareClient
            from ...acquisition.flare import FlareAcquisition

            client = FlareClient(settings)
            try:
                client.discover()
                if values["dfd_enable"]:
                    client.check_acquisition_support(dfd=True)
                else:
                    client.check_acquisition_support()
                configuration = configuration_from_gui(
                    values, client.firmware["clock_hz"], settings, preview=preview, dummy=dummy
                )
            finally:
                client.close()
            runner = FlareAcquisition(
                settings,
                configuration,
                filename=filename,
                raw_only=raw_only,
                on_snapshot=lambda snapshot: self.run_job.snapshot.emit(dict(
                    snapshot, geometry=values if values["dfd_enable"] else (self.live_controls.geometry() or values),
                )),
                initial_image=initial_image,
                live_controls=self.live_controls,
            )
            runner.gui_metadata = dict(values)
            runner.display_channels = self.display_channels
            self.runner = runner
            if self.stopping:
                runner.stop()
            return runner.run()

        self.run_job = FlareJob(acquire, self)
        self.run_job.snapshot.connect(self.render)
        self.run_job.result.connect(self._acquisition_result)
        self.run_job.finished.connect(self._run_thread_finished)
        self.run_job.start()

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
        self.connected = True
        if not self._status_timer.isActive():
            self._status_timer.start()
        self.ui.label_flare_status.setText(
            f"Bins {snapshot['bins']}/{snapshot['total_bins']}; received {snapshot['receiver_bytes']}/{snapshot['expected_bytes']} bytes; "
            f"DMA {snapshot['status'].get('dma')}"
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
            exposure = snapshot["bin_seconds"] / snapshot["dfd_bins"]
            self.window.renderDfdTrace(
                snapshot["dfd_hist_live"] / max(exposure * snapshot["dfd_live_records"], 1e-15),
                snapshot["dfd_hist_sum"] / max(exposure * snapshot["dfd_hist_records"], 1e-15),
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
        self.last_result = result
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
        complete = bool(result and result.get("complete"))
        self.window._set_program_state(
            self.window.PROGRAM_STATE_ACQUISITION_DONE
            if complete and not self.preview
            else self.window.PROGRAM_STATE_IDLE,
            "flare_completed" if complete else "flare_stopped",
        )
        self.ui.statusBar.showMessage(message or "Flare acquisition complete", 15000)

    def _run_thread_finished(self):
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
        if self.runner:
            self.runner.stop()
        elif (
            self.preview
            and not (self.run_job and self.run_job.isRunning())
            and getattr(self.window, "started_preview", False)
        ):
            self._acquisition_result({"complete": False, "result": "cancelled"}, None)

    def close(self):
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
        for logger in self.loggers:
            logger.removeHandler(self.bridge)
