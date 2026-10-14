"""Run trigger widgets in a separate Qt interpreter, without hardware."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("preview", [False, True])
def test_trigger_widgets_and_early_stop_metadata(tmp_path, preview):
    source = textwrap.dedent('''
        import sys
        import math
        from types import MethodType
        from unittest.mock import MagicMock
        import h5py
        from PySide6.QtWidgets import QApplication, QMainWindow
        from brighteyes_mcs.ui.qt.main_window_design import Ui_MainWindowDesign
        from brighteyes_mcs.ui.qt.main_window import MainWindow
        from brighteyes_mcs.ui.controllers.software_trigger import SoftwareTriggerController
        from test.test_software_trigger import manager_stub

        class Window(QMainWindow):
            def offset_um_Changed(self, force=False):
                MainWindow.positionSettingsChanged_apply(self, force)

            def rangeValueChanged(self, number=None):
                MainWindow.positionSettingsChanged_apply(self, True)

            def __getattr__(self, name):
                # Designer connects unrelated controls to MainWindow slots.
                if callable(getattr(MainWindow, name, None)):
                    return lambda *args: None
                raise AttributeError(name)

        preview = sys.argv[2] == "True"
        app = QApplication([])
        window = Window()
        window.ui = Ui_MainWindowDesign()
        window.ui.setupUi(window)
        window.configuration_helper = {
            "nframe": ("Frames", int, window.ui.spinBox_nframe, True),
            "sw_trigger_enable": ("Trigger", bool, window.ui.checkBox_sw_trigger_enable, False),
        }
        window.configurationFPGA_dict = {}
        window.configurationGUI_dict_beforeStart = {"nframe": 3, "nrep": 2, "sw_trigger_enable": True}
        window._gui_config_for_h5 = MainWindow._gui_config_for_h5
        window._mcs_saving_suppressed = False
        window.mcs_manager = manager_stub()
        window.mcs_manager.filenameh5 = sys.argv[1]
        window.mcs_manager.process_supervisor = MagicMock()
        window.mcs_manager.process_supervisor.get.return_value = None
        window.mcs_manager.fpga_handle.register_read.return_value = {
            "laser_off_after_measurement_enable": False, "laser_force_pulsing_enable": False}
        window.setRegistersDict = MethodType(MainWindow.setRegistersDict, window)
        window._offset_volts = MethodType(MainWindow._offset_volts, window)
        window._update_offset_voltage_labels = MethodType(MainWindow._update_offset_voltage_labels, window)
        window.lock_parameters_changed_call = False
        window.rect_roi = MagicMock()
        window.software_trigger = controller = SoftwareTriggerController(window)
        ui = window.ui
        assert ui.groupBox_27.isEnabled() and ui.groupBox_28.isEnabled()
        assert not ui.pushButton_sw_trigger_cmd.isEnabled()
        ui.checkBox_sw_trigger_enable.setChecked(True)
        assert not ui.groupBox_27.isEnabled()
        ui.checkBox_sw_trigger_enable.setChecked(False)
        ui.checkBox_slavemode_enable.setChecked(True)
        assert not ui.groupBox_28.isEnabled()
        ui.checkBox_slavemode_enable.setChecked(False)
        assert ui.groupBox_27.isEnabled() and ui.groupBox_28.isEnabled()
        ui.checkBox_sw_trigger_enable.setChecked(True)
        ui.checkBox_sw_trigger_laser_off.setChecked(True)
        controller.prepare(preview=preview)
        window.mcs_manager.readRegistersDict()
        controller.arm()
        assert "Armed" in controller.label.text()
        for name in controller.GEOMETRY_WIDGET_NAMES:
            assert getattr(ui, name).isEnabled() == preview, name
        assert not ui.spinBox_nframe.isEnabled()
        assert not ui.checkBox_sw_trigger_enable.isEnabled()
        assert ui.pushButton_sw_trigger_cmd.isEnabled()
        assert window.mcs_manager.registers_configuration["max_frame"] == 1
        window.setRegistersDict({"max_frame": 42})
        assert window.mcs_manager.registers_configuration["max_frame"] == 1
        # Exercise the actual Designer valueChanged connection and the real
        # position register calculation while the acquisition remains armed.
        ui.spinBox_off_x_um.setValue(ui.spinBox_off_x_um.value() + 1)
        ui.spinBox_range_x.setValue(ui.spinBox_range_x.value() + 1)
        expected_x = ((ui.spinBox_off_x_um.value() - 0.5 * ui.spinBox_range_x.value())
                      / ui.spinBox_calib_x.value() + ui.spinBox_offExtra_x_V.value())
        if preview:
            assert math.isclose(window.mcs_manager.registers_configuration["axis_start_offset_volts"][0], expected_x,
                                rel_tol=1e-12, abs_tol=1e-12)
            expected_step = ui.spinBox_range_x.value() / ui.spinBox_calib_x.value() / ui.spinBox_nx.value()
            assert math.isclose(window.mcs_manager.registers_configuration["axis_calibration_volts_per_step"][0], expected_step)
            ui.checkBoxLockRatio.setChecked(True)
            controller.update_controls()
            assert not ui.spinBox_range_y.isEnabled()
            ui.checkBoxLockRatio.setChecked(False)
            controller.update_controls()
            assert ui.spinBox_range_y.isEnabled()
        assert controller.session.state == "armed"
        # Real position handlers submit offsets together with dimensions.
        # Only preview geometry may pass through during the trigger wait.
        window.setRegistersDict({"axis_start_offset_volts": [4, 5, 6],
                                 "max_frame": 42, "max_repetition": 43,
                                 "axis_calibration_volts_per_step": [8, 8, 8]})
        offsets = [4, 5, 6] if preview else [1, 2, 3]
        assert window.mcs_manager.registers_configuration["axis_start_offset_volts"] == offsets
        assert window.mcs_manager.registers_configuration["max_frame"] == 1
        assert window.mcs_manager.registers_configuration["max_repetition"] == 2
        assert window.mcs_manager.registers_configuration["axis_calibration_volts_per_step"] == ([8, 8, 8] if preview else [0.1, 0.2, 0.5])
        ui.comboBox_AnalogOut = {2: MagicMock(), 3: MagicMock()}
        ui.comboBox_AnalogOut[2].currentText.return_value = "X2"
        ui.comboBox_AnalogOut[3].currentText.return_value = "Constant"
        window.setRegistersDict({"analog_output_2_dc_volts": 1.25, "analog_output_3_dc_volts": 9})
        assert ("analog_output_2_dc_volts" in window.mcs_manager.registers_configuration) == preview
        assert "analog_output_3_dc_volts" not in window.mcs_manager.registers_configuration
        ui.pushButton_sw_trigger_cmd.click()
        assert not ui.pushButton_sw_trigger_cmd.isEnabled()
        assert not ui.spinBox_off_x_um.isEnabled()
        assert not ui.spinBox_off_x2_um.isEnabled()
        assert not ui.spinBox_range_x.isEnabled()
        window.setRegistersDict({"axis_start_offset_volts": [99, 99, 99]})
        assert window.mcs_manager.registers_configuration["axis_start_offset_volts"] == offsets
        for fifo in window.mcs_manager.activated_fifos_list:
            window.mcs_manager.shared_dict[f"software_trigger_frames_{fifo}"] = 1
        controller.poll()
        assert ("Frames completed: 1" if preview else "1/6") in controller.label.text()
        assert ui.pushButton_sw_trigger_cmd.isEnabled()
        for name in controller.GEOMETRY_WIDGET_NAMES:
            assert getattr(ui, name).isEnabled() == preview, name
        if not preview:
            with h5py.File(sys.argv[1], "w"):
                pass
        controller.before_stop()
        controller.finish()
        assert ui.spinBox_nframe.isEnabled()
        assert ui.checkBox_sw_trigger_enable.isEnabled()
        assert not ui.pushButton_sw_trigger_cmd.isEnabled()
        assert ui.spinBox_range_x.isEnabled()
        assert ui.spinBox_off_x_um.isEnabled()
        if not preview:
            with h5py.File(sys.argv[1]) as output:
                meta = output["softwareTrigger"].attrs
                assert meta["frames_completed"] == 1 and meta["frames_requested"] == 6
                assert not meta["complete"]
                assert len(output["softwareTrigger/trigger_timestamps_unix"]) == 1
                assert "frame_start_offsets_volts" not in output["softwareTrigger"]
        ui.checkBox_sw_trigger_enable.setChecked(False)
        window.setRegistersDict({"max_frame": 42})
        assert window.mcs_manager.registers_configuration["max_frame"] == 42
        assert ui.groupBox_27.isEnabled() and ui.groupBox_28.isEnabled()
        print("TRIGGER_GUI_OK", flush=True)
    ''')
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", BRIGHTEYES_LOG_DIR=str(tmp_path / "logs"))
    result = subprocess.run([sys.executable, "-c", source, str(tmp_path / "early-stop.h5"), str(preview)],
                            cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=45)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    assert "TRIGGER_GUI_OK" in result.stdout
