"""Qt wiring for the optional software-trigger acquisition path."""

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from ...acquisition.software_trigger import SoftwareTriggerSession
from ...acquisition.detectors.models import DETECTOR_DISABLED, detector_uses_pispad23_timestamp
from ...logging_setup import logger
from ...storage.h5 import H5Manager
from ...storage.legacy_names import LEGACY_H5_REGISTER_NAME_MAP
from ...storage.h5_schema import legacy_raw_stream_metadata


class SoftwareTriggerController:
    GEOMETRY_WIDGET_NAMES = (
        "spinBox_range_x", "spinBox_range_y", "spinBox_range_z", "checkBoxLockRatio",
        "spinBox_off_x_um", "spinBox_off_y_um", "spinBox_off_z_um",
        "spinBox_offExtra_x_V", "spinBox_offExtra_y_V", "spinBox_offExtra_z_V",
        "spinBox_off_x2_um", "spinBox_off_y2_um", "spinBox_off_z2_um",
        "spinBox_offExtra_x_V_2", "spinBox_offExtra_y_V_2", "spinBox_offExtra_z_V_2",
    )

    def __init__(self, window):
        self.window = window
        self.ui = window.ui
        self.session = None
        self.stopping = False
        self.locked_widgets = []
        self.geometry_widgets = []
        self.label = QLabel(self.ui.groupBox_28)
        self.label.setObjectName("label_sw_trigger_status")
        self.label.setWordWrap(True)
        self.ui.gridLayout_113.addWidget(self.label, 3, 0)
        self.ui.checkBox_sw_trigger_enable.toggled.connect(self.software_toggled)
        self.ui.checkBox_slavemode_enable.toggled.connect(self.hardware_toggled)
        self.ui.pushButton_sw_trigger_cmd.clicked.connect(self.trigger)
        self.timer = QTimer(window)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)
        self.update_controls()

    @property
    def active(self):
        return self.session is not None

    @property
    def can_finalize(self):
        return not self.active or self.session.state == "complete"

    def selected(self):
        return self.ui.checkBox_sw_trigger_enable.isChecked()

    @property
    def preview_geometry_editable(self):
        return (self.active and self.session.preview and not self.stopping
                and self.session.state == "armed")

    def update_preview_geometry(self, registers):
        """Allow preview range/position changes, keeping acquisition geometry frozen."""
        if not self.preview_geometry_editable:
            return {}
        allowed = {"axis_start_offset_volts", "axis_calibration_volts_per_step"}
        selectors = getattr(self.ui, "comboBox_AnalogOut", {})
        for channel, selector in (selectors.items() if isinstance(selectors, dict) else ()):
            if selector.currentText() in ("X2", "Y2", "Z2"):
                allowed.add(f"analog_output_{channel}_dc_volts")
        geometry = {key: value for key, value in registers.items() if key in allowed}
        try:
            return geometry if self.session.update_preview_geometry(geometry) else {}
        except Exception as error:
            self.fail(error)
            return {}

    def software_toggled(self, checked):
        if checked:
            self.ui.checkBox_slavemode_enable.setChecked(False)
        self.update_controls()

    def hardware_toggled(self, checked):
        if checked:
            self.ui.checkBox_sw_trigger_enable.setChecked(False)
        self.update_controls()

    def update_controls(self):
        for widget, enabled in self.geometry_widgets:
            if widget is self.ui.spinBox_range_y:
                enabled = not self.ui.checkBoxLockRatio.isChecked()
            widget.setEnabled(enabled and self.preview_geometry_editable)
        self.ui.groupBox_27.setEnabled(not self.selected() and not self.active)
        self.ui.groupBox_28.setEnabled(not self.ui.checkBox_slavemode_enable.isChecked())
        self.ui.checkBox_sw_trigger_enable.setEnabled(not self.active)
        self.ui.checkBox_sw_trigger_laser_off.setEnabled(self.selected() and not self.active)
        self.ui.pushButton_sw_trigger_cmd.setEnabled(
            self.active and not self.stopping and self.session.state == "armed")
        if not self.active:
            self.label.setText("Start Preview or Acquisition to arm." if self.selected() else "")
        else:
            s = self.session
            count = str(s.completed) if s.preview else f"{s.completed}/{s.total}"
            text = {"preparing": "Preparing acquisition",
                    "armed": "Armed — waiting for software trigger",
                    "capturing": "Capturing frame", "draining": "Receiving frame data",
                    "complete": "Acquisition complete", "error": "Acquisition error"}[s.state]
            self.label.setText(f"{text}\nFrames completed: {count}")

    def validate(self):
        if not self.selected():
            return True
        model = self.window._current_detector_model()
        reason = ""
        if model == DETECTOR_DISABLED or detector_uses_pispad23_timestamp(model):
            reason = "Software triggering requires a detector with frame data (SPAD or PISPAD23 intensity)."
        elif any(widget.isChecked() for widget in (
                self.ui.checkBox_ttmActivate, self.ui.checkBox_uttmActivate,
                self.ui.checkBox_pispad23ttmActivate)):
            reason = "Software triggering with external TTM recording is not supported yet."
        elif not (self.ui.checkBox_fifo_digital.isChecked() or self.ui.checkBox_fifo_analog.isChecked()):
            reason = "Enable at least one data stream before using software triggering."
        if reason:
            QMessageBox.warning(self.window, "Software trigger", reason)
        return not reason

    def prepare(self, preview):
        if not self.selected():
            return
        manager = self.window.mcs_manager
        self.session = SoftwareTriggerSession(
            manager, preview=preview, laser_off=self.ui.checkBox_sw_trigger_laser_off.isChecked())
        manager.software_trigger_session = self.session
        self.stopping = False
        # Hardware readback supplies defaults for controls not represented in
        # configurationFPGA_dict (including firmware laser gating).
        for name in ("laser_off_after_measurement_enable", "laser_force_pulsing_enable"):
            value = manager.fpga_handle.register_read((name,)).get(name)
            if value is not None:
                self.session.requested[name] = value
        self.session.prepare()
        self._lock_settings()
        self.update_controls()

    def arm(self):
        if self.active:
            self.session.arm()
            self.timer.start()
            self.update_controls()

    def _lock_settings(self):
        # Only preview range/position reopen between frames. Pixel counts stay fixed.
        self.geometry_widgets = [(getattr(self.ui, name), getattr(self.ui, name).isEnabled())
                                 for name in self.GEOMETRY_WIDGET_NAMES]
        editable = ("preview_", "fingerprint_", "trace_", "fcs_", "plot_")
        widgets = [item[2] for key, item in self.window.configuration_helper.items()
                   if not key.startswith(editable)]
        widgets += [getattr(self.ui, name) for name in (
            "pushButton_loadCfg", "comboBox_detector_model", "checkBox_fifo_digital",
            "checkBox_fifo_analog", "checkBox_DFD", "checkBox_pulsing_forced",
            "checkBox_rawStreamAcquisition", "checkBox_ttmActivate", "checkBox_uttmActivate",
            "checkBox_pispad23ttmActivate")]
        widgets += [widget for widget, _enabled in self.geometry_widgets]
        seen = set()
        for widget in widgets:
            if isinstance(widget, QWidget) and id(widget) not in seen:
                seen.add(id(widget))
                if widget.isEnabled():
                    self.locked_widgets.append((widget, True))
                    widget.setEnabled(False)

    def trigger(self):
        if not self.active or self.stopping:
            return
        # Disable synchronously, before a register write can process more events.
        self.ui.pushButton_sw_trigger_cmd.setEnabled(False)
        for widget, _enabled in self.geometry_widgets:
            widget.setEnabled(False)
        try:
            self.session.trigger()
        except Exception as error:
            self.fail(error)
        self.update_controls()

    def poll(self):
        if not self.active or self.stopping:
            return
        try:
            self.session.poll()
            manager = self.window.mcs_manager
            if manager.shared_dict.get("raw_writer_error"):
                raise RuntimeError(manager.shared_dict["raw_writer_error"])
            for name in ("receiver", "preprocess", "preview", "raw_writer"):
                process = manager.process_supervisor.get(name)
                if process is not None and process.exitcode is not None:
                    expected_exit = (name in ("preview", "raw_writer") and
                                     self.session.total == self.session.received_frames())
                    if process.exitcode != 0 or not expected_exit:
                        raise RuntimeError(f"The {name} worker stopped during software-trigger acquisition.")
            self.update_controls()
        except Exception as error:
            self.fail(error)

    def fail(self, error):
        logger.exception("Software-trigger acquisition failed")
        self.session.error = str(error)
        self.session.state = "error"
        self.window.stop()
        self.label.setText(f"Software trigger error: {error}")
        self.ui.statusBar.showMessage(str(error), 15000)

    def before_stop(self):
        if not self.active or self.stopping:
            return
        self.stopping = True
        self.timer.stop()
        self.ui.pushButton_sw_trigger_cmd.setEnabled(False)
        if self.session.laser_off and self.window.mcs_manager.is_connected:
            try:
                self.session.lasers_off()
            except Exception:
                logger.exception("Could not switch off lasers during software-trigger stop")

    def finish(self):
        """Called after acquisition workers have closed their writer."""
        if not self.active:
            return
        self.timer.stop()
        session = self.session
        manager = self.window.mcs_manager
        try:
            if not session.preview and not self.window._mcs_saving_suppressed:
                filename = manager.filenameh5
                if Path(filename).exists() or manager.raw_stream_mode:
                    h5 = H5Manager(filename, new_file=not Path(filename).exists())
                    try:
                        metadata = session.metadata()
                        timestamps = metadata.pop("trigger_timestamps_unix")
                        h5.metadata_add_dict("softwareTrigger", metadata)
                        group = h5.h5file["softwareTrigger"]
                        group.create_dataset("trigger_timestamps_unix", data=timestamps)
                        h5.metadata_add_dict("configurationGUI_beforeStart",
                            self.window._gui_config_for_h5(self.window.configurationGUI_dict_beforeStart))
                        h5.metadata_add_dict("configurationFPGA", session.requested,
                                             legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP)
                        h5.metadata_add_dict("configurationSpadFCSmanager", session.requested,
                                             legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP)
                        h5.metadata_add_dict("configurationGUI",
                            self.window._gui_config_for_h5(self.window.configurationGUI_dict_beforeStart))
                        if manager.raw_stream_mode:
                            h5.metadata_add_dict("rawStreamAcquisition", legacy_raw_stream_metadata(
                                manager, spad_channels=self.window.spad_channels,
                                clock_base_mhz=self.window.clock_base,
                                raw_files=self.window.raw_stream_output_files,
                                include_pispad23=session.needs_receiver_ready))
                    finally:
                        h5.close()
        except Exception as error:
            logger.exception("Could not save software-trigger metadata")
            self.ui.statusBar.showMessage(f"Could not save trigger metadata: {error}", 15000)
        finally:
            try:
                session.restore()
            except Exception as error:
                logger.exception("Could not restore controls after software-trigger acquisition")
                self.ui.statusBar.showMessage(f"Could not restore FPGA controls: {error}", 15000)
            finally:
                manager.software_trigger_session = None
                self.session = None
                self.stopping = False
                for widget, enabled in self.locked_widgets:
                    widget.setEnabled(enabled)
                if session.preview:
                    self.ui.spinBox_range_y.setEnabled(not self.ui.checkBoxLockRatio.isChecked())
                self.locked_widgets.clear()
                self.geometry_widgets.clear()
                self.update_controls()
