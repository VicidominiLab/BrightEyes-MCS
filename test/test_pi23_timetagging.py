"""Recorder lifecycle tests use a fake TCP detector, never microscope hardware."""

from pathlib import Path
import json
import socket
import threading
import time
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import MagicMock

import h5py
import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

from brighteyes_mcs.ui.qt.main_window_design import Ui_MainWindowDesign
from brighteyes_mcs.ui.qt.pi23_timetagging import Pi23Timetagging, measurement_ms, output_path
from brighteyes_mcs.ui.qt.main_window import MainWindow
from brighteyes_mcs.acquisition.manager import McsManager


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ui(app):
    window = QMainWindow()
    design = Path(__file__).parents[1] / "brighteyes_mcs/ui/qt/main_window_design.ui"
    for connection in ET.parse(design).findall("./connections/connection"):
        if connection.findtext("receiver") == "MainWindowDesign":
            slot = connection.findtext("slot").split("(")[0]
            if not hasattr(window, slot):
                setattr(window, slot, lambda *args: None)
    ui = Ui_MainWindowDesign()
    ui.setupUi(window)
    defaults = (
        Path(__file__).parents[1]
        / "brighteyes_mcs/cfg/plugins_cfg/pi23_timetagging.cfg"
    )
    settings = json.loads(defaults.read_text(encoding="utf-8"))
    adapter = SimpleNamespace(ui=ui)
    adapter._pi23_timetagging_bindings = lambda: (
        MainWindow._pi23_timetagging_bindings(adapter)
    )
    MainWindow._apply_pi23_timetagging_configuration(adapter, settings)
    yield ui
    window.close()


def wait_for(app, condition, timeout=10):
    deadline = time.monotonic() + timeout
    while not condition():
        app.processEvents()
        assert time.monotonic() < deadline, "Timed out waiting for recorder"
        time.sleep(0.01)


def test_timing_includes_circular_frames_waits_and_margin(ui):
    ui.spinBox_timeresolution.setValue(10)
    ui.spinBox_time_bin_per_px.setValue(100)
    ui.spinBox_nx.setValue(10)
    ui.spinBox_ny.setValue(20)
    ui.spinBox_nframe.setValue(3)
    ui.spinBox_nrepetition.setValue(2)
    ui.checkBox_circular.setChecked(True)
    ui.spinBox_circular_points.setValue(4)
    ui.spinBox_circular_repetition.setValue(5)
    ui.spinBox_waitAfterFrame.setValue(1)
    ui.spinBox_waitForLaser.setValue(2)
    ui.checkBox_waitOnlyFirstTime.setChecked(False)
    ui.doubleSpinBox_pi23ttm_settle.setValue(0.5)
    ui.doubleSpinBox_pi23ttm_margin.setValue(2)
    assert measurement_ms(ui) == 44500
    ui.checkBox_waitOnlyFirstTime.setChecked(True)
    assert measurement_ms(ui) == 34500


def test_output_names_never_reuse_existing_file(tmp_path):
    first = output_path(tmp_path, "data-test.h5")
    assert first.name == "data-test-tsraw.h5"
    first.touch()
    assert output_path(tmp_path, "data-test.h5").name == "data-test-tsraw-1.h5"
    assert output_path(tmp_path, "data-test.h5", raw=True).name == "data-test-ts.raw"


def test_timetagging_is_inside_config(ui):
    assert ui.tabWidget.indexOf(ui.tab_14) == -1
    assert ui.tabWidget_2.indexOf(ui.tab_14) >= 0
    assert ui.tabWidget_3.indexOf(ui.tab_pi_timetagging) >= 0
    assert ui.groupBox_10.isAncestorOf(ui.checkBox_pi23ttmActivate)
    assert ui.dockWidget_adv2.isAncestorOf(ui.checkBox_noMcsSaveWithTtm)
    assert ui.pushButton_pi23ttm_force_calibration.text() == "Force Calibration"


def test_timetagging_defaults_are_loaded_from_plugins_cfg(ui):
    config_path = (
        Path(__file__).parents[1]
        / "brighteyes_mcs/cfg/plugins_cfg/pi23_timetagging.cfg"
    )
    configuration = json.loads(config_path.read_text(encoding="utf-8"))
    window = SimpleNamespace(ui=ui)
    window._pi23_timetagging_bindings = lambda: (
        MainWindow._pi23_timetagging_bindings(window)
    )

    MainWindow._apply_pi23_timetagging_configuration(window, configuration)

    assert ui.lineEdit_pi23ttm_h5_executable.text().endswith("tdc_h5_acquire.exe")
    assert ui.lineEdit_pi23ttm_raw_executable.text().endswith("tdc_raw_acquire.exe")
    assert ui.lineEdit_pi23ttm_address.text() == "127.0.0.1:9997"
    assert ui.doubleSpinBox_pi23ttm_margin.value() == 2.0
    assert ui.doubleSpinBox_pi23ttm_settle.value() == 0.5
    assert ui.doubleSpinBox_pi23ttm_timeout.value() == 120.0
    assert (
        MainWindow._get_pi23_timetagging_configuration(window)
        == configuration
    )


def test_force_calibration_sends_vendor_command_and_logs_response(app, ui):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    received = []

    def device():
        connection, _ = server.accept()
        with connection:
            connection.sendall(b"Fake PI23\n")
            received.append(connection.recv(128))
            connection.sendall(b"calibration complete\n")
        server.close()

    thread = threading.Thread(target=device, daemon=True)
    thread.start()
    ui.lineEdit_pi23ttm_address.setText(f"127.0.0.1:{server.getsockname()[1]}")
    recorder = Pi23Timetagging(ui)
    recorder.force_calibration()
    wait_for(app, lambda: not recorder.calibrating)
    thread.join(timeout=1)
    assert received == [b"T,c,1\n"]
    assert "calibration complete" in ui.plainTextEdit_pi23ttm_log.toPlainText()
    assert ui.pushButton_pi23ttm_force_calibration.isEnabled()


def test_force_calibration_is_not_available_while_recording(ui):
    recorder = Pi23Timetagging(ui)
    recorder.process = MagicMock()
    recorder.force_calibration()
    recorder.process.assert_not_called()
    assert "Cannot force calibration" in ui.plainTextEdit_pi23ttm_log.toPlainText()


def test_pi23_imaging_and_timetagging_are_mutually_exclusive(ui):
    window = SimpleNamespace(ui=ui, pi23_timetagging=SimpleNamespace(active=False))
    ui.comboBox_detector_model.setCurrentText("FPGA - SPAD")
    ui.checkBox_pi23ttmActivate.setChecked(True)
    MainWindow._sync_pi23_ttm_detector(window)
    pi23_index = ui.comboBox_detector_model.findText("TCP/IP - PI23")
    assert not ui.comboBox_detector_model.model().item(pi23_index).isEnabled()
    ui.checkBox_pi23ttmActivate.setChecked(False)
    ui.comboBox_detector_model.setCurrentText("TCP/IP - PI23")
    MainWindow._sync_pi23_ttm_detector(window)
    assert not ui.checkBox_pi23ttmActivate.isEnabled()


def test_disabled_detector_configuration_roundtrip_and_pi23_controls(ui):
    window = SimpleNamespace(
        ui=ui, pi23_timetagging=SimpleNamespace(active=False),
        detectorModelChanged=MagicMock(),
    )
    window._current_detector_model = lambda: MainWindow._current_detector_model(window)
    MainWindow._set_detector_model_combo(window, "Disable")
    assert ui.comboBox_detector_model.currentText() == "Disable"
    assert window._current_detector_model() == "Disable"
    window.detectorModelChanged.assert_called_once_with("Disable")
    ui.checkBox_pi23ttmActivate.setChecked(True)
    MainWindow._sync_pi23_ttm_detector(window)
    assert not ui.checkBox_pi23ttmActivate.isEnabled()


def test_disabled_preview_tick_does_not_access_detector_data(ui):
    window = SimpleNamespace(
        ui=ui, _current_detector_model=lambda: "Disable",
        timerPreviewImg_tick_mutex=MagicMock(), mcs_manager=MagicMock(),
    )
    MainWindow.timerPreviewImg_tick(window)
    assert ui.label_tot_num_dat_point_val.text() == "Detector disabled"
    assert not window.mcs_manager.mock_calls
    window.timerPreviewImg_tick_mutex.unlock.assert_called_once_with()


def test_conflicting_config_is_rejected_before_connecting(ui):
    ui.comboBox_detector_model.setCurrentText("TCP/IP - PI23")
    ui.checkBox_pi23ttmActivate.setChecked(True)
    window = SimpleNamespace(
        ui=ui, pi23_timetagging=SimpleNamespace(active=False),
        _current_detector_model=lambda: "PI23", _prepare_fpga_for_acquisition=MagicMock(),
    )
    from unittest.mock import patch
    with patch("brighteyes_mcs.ui.qt.main_window.QMessageBox.warning") as warning:
        MainWindow.beginAcquisition(window)
    warning.assert_called_once()
    window._prepare_fpga_for_acquisition.assert_not_called()


def test_disconnected_register_settings_are_retained_and_write_errors_propagate():
    manager = McsManager.__new__(McsManager)
    manager.detector_model = "SPAD Array"
    manager.is_connected = False
    manager.registers_configuration = {}
    manager.setRegistersDict({"laser_force_pulsing_enable": True})
    assert manager.registers_configuration["laser_force_pulsing_enable"] is True
    manager.is_connected = True
    manager.fpga_handle = MagicMock()
    manager.fpga_handle.register_write_checked.side_effect = RuntimeError("write failed")
    with pytest.raises(RuntimeError, match="write failed"):
        manager.setRegistersDict({"laser_force_pulsing_enable": False})
    assert manager.registers_configuration["laser_force_pulsing_enable"] is True


def test_requested_controls_are_written_after_vi_start():
    from unittest.mock import call, patch

    manager = McsManager.__new__(McsManager)
    for name in ("bitfile", "niAddr", "bitfile2", "niAddr2"):
        setattr(manager, name, "")
    manager.detector_model = "SPAD Array"
    manager.mp_manager = MagicMock()
    manager.requested_fifo_depth = 1000
    manager.initial_registers_dict = {}
    manager.debug = False
    manager.use_rust_fifo = False
    manager.timeout_fifos = 1000
    manager.update_chuck = MagicMock()
    manager.registers_configuration = {}
    manager.is_connected = False
    handle = MagicMock()
    with patch("brighteyes_mcs.acquisition.manager.FpgaHandle", return_value=handle):
        manager.connect({"laser_force_pulsing_enable": True})
    assert handle.mock_calls.index(call.runfpga()) < handle.mock_calls.index(
        call.register_write_checked("laser_force_pulsing_enable", True)
    )


def test_cancelled_calibration_cannot_start_mcs():
    window = SimpleNamespace(_waiting_for_pi23=False, started_normal=True, sendCmdRun=MagicMock())
    MainWindow._start_after_pi23_ready(window)
    window.sendCmdRun.assert_not_called()


def test_calibration_timeout_cancels_delayed_start_and_requests_clean_stop(ui):
    recorder = Pi23Timetagging(ui)
    recorder.process = MagicMock()
    recorder.pending = True
    recorder.deadline = time.monotonic() - 1
    recorder.settle_timer.start(1000)
    failures = []
    recorder.failed.connect(failures.append)
    recorder.poll()
    assert not recorder.pending
    assert not recorder.settle_timer.isActive()
    recorder.process.stdin.write.assert_called_once_with("stop\n")
    assert "timed out" in failures[0]


def test_recorder_failure_before_ready_does_not_start_scan(ui):
    recorder = Pi23Timetagging(ui)
    recorder.process = MagicMock()
    recorder.process.wait.return_value = 1
    recorder.pending = True
    recorder.messages.put("Connection refused\n")
    recorder.messages.put(None)
    failures = []
    ready = []
    recorder.failed.connect(failures.append)
    recorder.ready.connect(lambda: ready.append(True))
    recorder.poll()
    assert not recorder.active
    assert not recorder.pending
    assert failures and not ready
    assert "Connection refused" in ui.plainTextEdit_pi23ttm_log.toPlainText()


def test_suppressed_mcs_saving_finishes_without_creating_metadata_file():
    from unittest.mock import patch

    window = SimpleNamespace(
        started_normal=True, _mcs_saving_suppressed=True,
        ui=SimpleNamespace(checkBox_uttmActivate=MagicMock(isChecked=MagicMock(return_value=False))),
        completed_acquisition_count=0, _make_status_timestamp=lambda: "now",
        PROGRAM_STATE_ACQUISITION_DONE="done", stop=MagicMock(), plugin_signals=MagicMock(),
    )
    with patch("brighteyes_mcs.ui.qt.main_window.H5Manager") as storage:
        MainWindow.finalizeAcquisition(window)
    storage.assert_not_called()
    window.stop.assert_called_once()
    assert window._pending_program_state_after_stop == "done"
    assert window.completed_acquisition_count == 1


@pytest.mark.parametrize("natural", [False, True])
def test_mcs_stop_interrupts_recorder_only_for_manual_stop(ui, natural):
    window = SimpleNamespace(
        ui=ui, _waiting_for_pi23=True, pi23_timetagging=MagicMock(active=True),
        _pending_program_state_after_stop="done" if natural else None,
        started_normal=True, started_preview=False, analog_before_stop=MagicMock(),
        ttm_remote_is_up=lambda: False, stopAcquisition=MagicMock(),
        update=MagicMock(), repaint=MagicMock(), _sync_pi23_ttm_detector=MagicMock(),
        _set_program_state=MagicMock(), PROGRAM_STATE_IDLE="idle",
    )
    MainWindow.stop(window)
    if natural:
        window.pi23_timetagging.stop.assert_not_called()
    else:
        window.pi23_timetagging.stop.assert_called_once()
    assert not window._waiting_for_pi23
    assert not ui.pushButton_acquisitionStart.isEnabled()
    assert ui.pushButton_stop.isEnabled()


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("manual_stop", [False, True])
def test_vendor_recorder_calibration_record_and_clean_stop(app, ui, tmp_path, raw, manual_stop):
    executable = Path("C:/Users/madonato/Documents/GitHub/tdc_raw_acquire/target/release") / (
        "tdc_raw_acquire.exe" if raw else "tdc_h5_acquire.exe"
    )
    if not executable.is_file():
        pytest.skip("Local vendor recorder build is not available")
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(10)
    calibrated = threading.Event()
    streaming = threading.Event()
    finish = threading.Event()
    commands = []
    errors = []

    def device():
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(10)
                connection.sendall(b"Fake PI23\n")
                stream = connection.makefile("rb")
                assert stream.readline() == b"T,v,1\n"
                connection.sendall(b"invalid\n")
                assert stream.readline() == b"T,c,1\n"
                time.sleep(0.15)
                calibrated.set()
                connection.sendall(b"calibration valid\n")
                command = stream.readline()
                commands.append(command)
                assert command.startswith(b"SB,")
                connection.sendall(bytes([0, 0, 1, 0, 0, 2]))
                streaming.set()
                if manual_stop:
                    assert stream.read(1) == b""
                else:
                    assert finish.wait(8)
                    connection.sendall(b"DONE\n")
                stream.close()
        except Exception as error:
            errors.append(error)
        finally:
            server.close()

    thread = threading.Thread(target=device, daemon=True)
    thread.start()
    ui.lineEdit_pi23ttm_address.setText(f"127.0.0.1:{server.getsockname()[1]}")
    ui.comboBox_pi23ttm_format.setCurrentText("RAW" if raw else "HDF5")
    ui.lineEdit_pi23ttm_folder.setText(str(tmp_path))
    ui.doubleSpinBox_pi23ttm_settle.setValue(0.2)
    recorder = Pi23Timetagging(ui)
    ready = []
    failures = []
    recorder.ready.connect(lambda: ready.append(calibrated.is_set() and streaming.is_set()))
    recorder.failed.connect(failures.append)
    try:
        recorder.start(str(tmp_path / "data-test.h5"))
        wait_for(app, lambda: ready or failures or errors)
        assert not failures and not errors
        assert ready == [True]
        assert commands == [f"SB,{measurement_ms(ui)}\n".encode()]
        if manual_stop:
            recorder.stop()
        else:
            finish.set()
        try:
            wait_for(app, lambda: not recorder.active)
        except AssertionError:
            pytest.fail(ui.plainTextEdit_pi23ttm_log.toPlainText())
        assert not failures
        if raw:
            assert recorder.path.read_bytes() == bytes([0, 0, 1, 0, 0, 2])
        else:
            with h5py.File(recorder.path) as file:
                assert file.attrs["acquisition_status"] == ("interrupted" if manual_stop else "complete")
                assert file.attrs["event_count"] == 1
        thread.join(timeout=1)
        assert not errors
    finally:
        finish.set()
        recorder.close()
