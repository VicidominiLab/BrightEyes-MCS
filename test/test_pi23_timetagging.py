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
from brighteyes_mcs.acquisition.detectors.models import DETECTOR_PI23_TS, DETECTOR_PI23_TS_UIMG, normalize_detector_model


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
    assert measurement_ms(ui, preview=True) == 8000
    ui.checkBox_waitOnlyFirstTime.setChecked(True)
    assert measurement_ms(ui) == 34500
    assert measurement_ms(ui, preview=True) == 8000


def test_preview_budget_is_one_frame_even_with_30000_repetitions(ui):
    ui.spinBox_timeresolution.setValue(5)
    ui.spinBox_time_bin_per_px.setValue(2)
    ui.spinBox_nx.setValue(200)
    ui.spinBox_ny.setValue(200)
    ui.spinBox_nframe.setValue(7)
    ui.spinBox_nrepetition.setValue(30000)
    ui.checkBox_circular.setChecked(False)
    ui.spinBox_waitAfterFrame.setValue(3)
    ui.spinBox_waitForLaser.setValue(2)
    ui.doubleSpinBox_pi23ttm_settle.setValue(0.5)
    ui.doubleSpinBox_pi23ttm_margin.setValue(10)
    assert measurement_ms(ui, preview=True) == 6400
    ui.doubleSpinBox_pi23ttm_preview_margin.setValue(1.25)
    assert measurement_ms(ui, preview=True) == 7150
    ui.spinBox_nx.setValue(1)
    ui.spinBox_ny.setValue(1)
    assert measurement_ms(ui, preview=True) == 6751
    ui.spinBox_waitAfterFrame.setValue(0)
    ui.spinBox_waitForLaser.setValue(0)
    ui.doubleSpinBox_pi23ttm_settle.setValue(0)
    ui.doubleSpinBox_pi23ttm_preview_margin.setValue(0.001)
    assert measurement_ms(ui, preview=True) == 2


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
    assert ui.doubleSpinBox_pi23ttm_preview_margin.value() == 0.5
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
    pi23_index = ui.comboBox_detector_model.findText("TCP/IP - PI23 (Intesity)")
    assert not ui.comboBox_detector_model.model().item(pi23_index).isEnabled()
    ui.checkBox_pi23ttmActivate.setChecked(False)
    ui.comboBox_detector_model.setCurrentText("TCP/IP - PI23 (Intesity)")
    MainWindow._sync_pi23_ttm_detector(window)
    assert not ui.checkBox_pi23ttmActivate.isEnabled()


@pytest.mark.parametrize("model", ["TCP/IP - PI23 (TS mode)", DETECTOR_PI23_TS, DETECTOR_PI23_TS_UIMG])
def test_timestamp_detector_allows_recording_and_persists_stream_port(ui, model):

    window = SimpleNamespace(ui=ui, pi23_timetagging=SimpleNamespace(active=False),
                             detectorModelChanged=MagicMock())
    window._current_detector_model = lambda: MainWindow._current_detector_model(window)
    window._pi23_timetagging_bindings = lambda: MainWindow._pi23_timetagging_bindings(window)
    MainWindow._set_detector_model_combo(window, model)
    ui.checkBox_pi23ttmActivate.setChecked(True)
    MainWindow._sync_pi23_ttm_detector(window)
    assert window._current_detector_model() == normalize_detector_model(model)
    assert ui.checkBox_pi23ttmActivate.isEnabled()
    assert ui.comboBox_detector_model.model().item(ui.comboBox_detector_model.currentIndex()).isEnabled()
    assert ui.comboBox_pi23ttm_format.currentText() == "RAW"
    assert not ui.comboBox_pi23ttm_format.isEnabled()
    assert ui.tab_pi_timetagging.isAncestorOf(ui.spinBox_pi23ttm_stream_port)
    assert ui.spinBox_pi23ttm_stream_port.value() == 19000
    MainWindow._apply_pi23_timetagging_configuration(window, {"pi23ttm_stream_port": 19234})
    assert MainWindow._get_pi23_timetagging_configuration(window)["pi23ttm_stream_port"] == 19234
    MainWindow._apply_pi23_timetagging_configuration(window, {"pi23ttm_preview_margin": 0.75})
    assert MainWindow._get_pi23_timetagging_configuration(window)["pi23ttm_preview_margin"] == 0.75


def test_microimage_preview_displays_worker_buffers_and_fingerprint(ui):
    import numpy as np
    from brighteyes_mcs.acquisition.shared_memory import SharedMemoryRegistry
    from brighteyes_mcs.acquisition.preview import PreviewRepository
    from brighteyes_mcs.acquisition.detectors.pi23.microimage import MicroimagePreview
    from brighteyes_mcs.acquisition.detectors.pi23.stream_image import MicroimageSnapshot

    arrays = SharedMemoryRegistry().allocate_preview(dim_x=3, dim_y=2, dim_z=1,
        detector_dim=5, autocorrelation_maxx=2, trace_bins=2, dfd_bins=2)
    repository = PreviewRepository()
    repository.bind(arrays)
    preview = MicroimagePreview(3, 2, shared_objects=arrays)
    counts = np.zeros(25, dtype=np.uint32)
    counts[0], counts[24] = 5, 2
    preview.consume(MicroimageSnapshot(counts, 3, 2, 1, 7, 3))
    preview.publish()
    manager = SimpleNamespace(preview_repository=repository,
        shared_dict={"pi23_uimg_status": dict(frame=3, frame_dwells=1, recent_dwells=1,
                                           last_frame_dwells=0, total_dwells=1)},
        getFingerprintSaturation=lambda: repository.get_fingerprint(4))
    window = SimpleNamespace(ui=ui, _current_detector_model=lambda: DETECTOR_PI23_TS_UIMG,
        mcs_manager=manager, im_widget=MagicMock(), autoscale_image=True,
        fingerprint_mask=np.ones((5, 5), dtype=np.uint8), fingerprint_visualization=0,
        draw_fingerprint=MagicMock(), microimage_analysis=MagicMock(),
        currentImage_size=[30, 10, 1], currentImage_pos=[20, 10, 0], currentImage_pixels=[3, 2, 1])
    window.getCurrentPreviewImage = lambda: MainWindow.getCurrentPreviewImage(window, repository.get_preview_image())
    window.isLifetimeColorChannel = lambda ch: False
    ui.checkBox_showPreview.setChecked(True)
    ui.comboBox_plot_channel.setCurrentText("Sum")
    ui.comboBox_view_projection.setCurrentText("xy")
    MainWindow._plot_pi23_microimage(window)
    args, kwargs = window.im_widget.setImage.call_args
    assert args[0].shape == (3, 2) and args[0][2, 1] == 7
    assert kwargs["scale"] == (10, 5)
    assert window.draw_fingerprint.call_args.args[0][4, 4] > 0
    preview.publish("24")
    ui.comboBox_plot_channel.setCurrentText("24")
    MainWindow._plot_pi23_microimage(window)
    assert window.im_widget.setImage.call_args.args[0][2, 1] == 2
    assert "1 dwells processed" in ui.label_tot_num_dat_point_val.text()


@pytest.mark.parametrize("circular", [False, True])
def test_microimage_preview_delay_blinks_above_threshold_and_clears(ui, monkeypatch, circular):
    from brighteyes_mcs.ui.qt import main_window

    ui.spinBox_timeresolution.setValue(100)
    ui.spinBox_time_bin_per_px.setValue(10)
    ui.checkBox_circular.setChecked(circular)
    ui.spinBox_circular_points.setValue(2)
    ui.spinBox_circular_repetition.setValue(5)
    # Check before the first frame too, when data may already be queued.
    status = {"pending_dwells": 2000 if not circular else 200}
    window = SimpleNamespace(ui=ui, _current_detector_model=lambda: DETECTOR_PI23_TS_UIMG,
        mcs_manager=SimpleNamespace(shared_dict={"pi23_uimg_status": status}))
    monkeypatch.setattr(main_window, "time", SimpleNamespace(monotonic=lambda: 10.0))
    MainWindow._plot_pi23_microimage(window)
    assert ui.label_preview_delay.text() == "2.000"
    assert "rgb(255,128,128)" in ui.label_preview_delay.styleSheet()
    monkeypatch.setattr(main_window, "time", SimpleNamespace(monotonic=lambda: 10.5))
    MainWindow._plot_pi23_microimage(window)
    assert ui.label_preview_delay.text() == "2.000"
    assert "rgb(255,128,128)" not in ui.label_preview_delay.styleSheet()
    monkeypatch.setattr(main_window, "time", SimpleNamespace(monotonic=lambda: 11.0))
    status["pending_dwells"] //= 2
    MainWindow._plot_pi23_microimage(window)
    assert ui.label_preview_delay.text() == "1.000"
    assert "red" not in ui.label_preview_delay.styleSheet()
    window.mcs_manager.shared_dict["pi23_uimg_status"] = {}
    MainWindow._plot_pi23_microimage(window)
    assert ui.label_preview_delay.text() == "0.000"
    assert "red" not in ui.label_preview_delay.styleSheet()


def test_timestamp_preview_waits_for_recorder_ready():
    window = SimpleNamespace(_waiting_for_pi23=True, started_normal=False,
                             started_preview=True, sendCmdRun=MagicMock())
    MainWindow._start_after_pi23_ready(window)
    assert not window._waiting_for_pi23
    window.sendCmdRun.assert_called_once()


def test_microimage_scan_waits_for_subscription_acknowledgement(ui):
    recorder = Pi23Timetagging(ui)
    recorder.process = MagicMock()
    recorder.process.poll.return_value = None
    recorder.pending = True
    recorder.stream_microimage = True
    recorder.require_armed = True
    recorder.armed = True
    ready = []
    recorder.ready.connect(lambda: ready.append(True))
    recorder._ready()
    assert recorder.pending and not ready
    recorder.image_connected.set()
    recorder._ready()
    assert not recorder.pending and ready == [True]
    recorder.settle_timer.stop()
    recorder.process = None


def test_raw_scan_waits_for_sb_armed_and_cancels_stale_ready_timer(ui):
    recorder = Pi23Timetagging(ui)
    recorder.process = MagicMock()
    recorder.process.poll.return_value = None
    recorder.pending = True
    recorder.require_armed = True
    recorder.deadline = time.monotonic() + 10
    window = SimpleNamespace(_waiting_for_pi23=True, started_preview=True,
                             started_normal=False, sendCmdRun=MagicMock())
    recorder.ready.connect(lambda: MainWindow._start_after_pi23_ready(window))
    recorder.messages.put("Press Ctrl+C to stop.\n")
    recorder.poll()
    recorder._ready()
    assert not recorder.settle_timer.isActive()
    window.sendCmdRun.assert_not_called()
    recorder.messages.put("PI23_ARMED SB,1000\n")
    recorder.poll()
    assert recorder.armed and recorder.settle_timer.isActive()
    window.sendCmdRun.assert_not_called()  # Wait for the configured delay.
    recorder.messages.put("PI23_DISARMED\n")
    recorder._ready()
    assert not recorder.armed and not recorder.settle_timer.isActive()
    window.sendCmdRun.assert_not_called()
    recorder.messages.put("PI23_ARMED SB,1000\n")
    recorder.poll()
    recorder._ready()
    window.sendCmdRun.assert_called_once()
    recorder.messages.put("PI23_DISARMED\n")
    recorder.messages.put("PI23_ARMED SB,1000\n")
    recorder.poll()
    recorder._ready()
    window.sendCmdRun.assert_called_once()  # Repeat SB does not restart the FPGA.
    recorder.settle_timer.stop()
    recorder.process = None


@pytest.mark.parametrize("normal,stopping", [(True, False), (False, False), (True, True)])
def test_timestamp_process_exit_finishes_scan_without_fifo_completion(ui, normal, stopping):
    from brighteyes_mcs.acquisition.detectors.models import DETECTOR_PI23_TS

    window = SimpleNamespace(
        ui=ui, _current_detector_model=lambda: DETECTOR_PI23_TS,
        pi23_timetagging=SimpleNamespace(stopping=stopping), started_normal=normal,
        started_preview=not normal, finalizeAcquisition=MagicMock(), stop=MagicMock(),
    )
    MainWindow._pi23_recording_finished(window)
    assert window.finalizeAcquisition.call_count == int(normal and not stopping)
    assert window.stop.call_count == int(not normal and not stopping)


def test_timestamp_snapshot_renders_with_scan_geometry(ui):
    import numpy as np
    from brighteyes_mcs.acquisition.detectors.models import DETECTOR_PI23_TS
    from brighteyes_mcs.acquisition.detectors.pi23.stream_image import ImageSnapshot

    window = SimpleNamespace(ui=ui, _current_detector_model=lambda: DETECTOR_PI23_TS,
                             started_normal=False, started_preview=True, im_widget=MagicMock(),
                             currentImage_size=[30, 10, 1], currentImage_pos=[20, 10, 0],
                             autoscale_image=True)
    ui.checkBox_showPreview.setChecked(True)
    counts = np.arange(6, dtype=np.uint32).reshape(2, 3)
    MainWindow._show_pi23_timestamp_image(window, ImageSnapshot(counts, 7, 15, 2))
    args, kwargs = window.im_widget.setImage.call_args
    np.testing.assert_array_equal(args[0], counts.T)
    assert kwargs["scale"] == (10, 5)
    assert kwargs["pos"] == (5, 5)
    assert ui.label_current_frame_val.text() == "8"


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


@pytest.mark.parametrize("record,suppress,expected_suppressed", [
    (False, False, False), (False, True, False), (True, False, False), (True, True, True),
])
def test_uimg_acquire_enables_h5_independently_of_timestamp_recording(ui, record, suppress, expected_suppressed):
    ui.checkBox_pi23ttmActivate.setChecked(record)
    ui.checkBox_noMcsSaveWithTtm.setChecked(suppress)
    ui.checkBox_ttmActivate.setChecked(False)
    ui.checkBox_uttmActivate.setChecked(False)
    ui.checkBox_rawStreamAcquisition.setChecked(True)  # A saved intensity preference must not bypass uimg.
    window = MagicMock(ui=ui)
    window.pi23_timetagging.active = False
    window._current_detector_model.return_value = DETECTOR_PI23_TS_UIMG
    MainWindow.beginAcquisition(window)
    assert window._mcs_saving_suppressed is expected_suppressed
    window.initializeAcquisition.assert_called_once_with(do_not_save=False, do_run=True, raw_stream_mode=False)


def test_conflicting_config_is_rejected_before_connecting(ui):
    ui.comboBox_detector_model.setCurrentText("TCP/IP - PI23 (Intesity)")
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


@pytest.mark.parametrize("code", [0, 1])
def test_broken_stop_pipe_cannot_crash_cleanup_or_leave_recorder_active(ui, code):
    recorder = Pi23Timetagging(ui)
    process = MagicMock()
    process.wait.return_value = code
    process.stdin.flush.side_effect = OSError(22, "Invalid argument")
    process.stdin.close.side_effect = OSError(22, "Invalid argument")
    recorder.process = process
    recorder.pending = True
    recorder.timer.start()
    recorder.settle_timer.start(500)
    recorder._enable_settings(False)
    finished = []
    recorder.finished.connect(lambda: finished.append(True))
    recorder.stop()
    recorder.close()
    recorder.messages.put(None)
    recorder.poll()
    assert not recorder.active and not recorder.pending
    assert not recorder.timer.isActive() and not recorder.settle_timer.isActive()
    assert recorder.image_stop.is_set()
    assert ui.spinBox_pi23ttm_stream_port.isEnabled()
    assert finished == [True]
    # A queued tick after completion is harmless, including duplicate EOF.
    recorder.messages.put(None)
    recorder.poll()
    assert finished == [True]


def test_recorder_error_and_exit_are_persisted_in_log(ui, tmp_path):
    import logging
    from brighteyes_mcs.logging_setup import logger

    path = tmp_path / "recorder.log"
    handler = logging.FileHandler(path, encoding="utf-8")
    old_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        recorder = Pi23Timetagging(ui)
        recorder.process = MagicMock()
        recorder.process.wait.return_value = 1
        recorder.pending = True
        recorder.messages.put("Error: image server port is already in use\n")
        recorder.messages.put(None)
        recorder.poll()
        handler.flush()
        saved = path.read_text(encoding="utf-8")
        assert "image server port is already in use" in saved
        assert "Image stream exited (1)" in saved
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(old_level)


@pytest.mark.parametrize("level", range(4))
def test_raw_recorder_verbose_flag_only_at_level_three(ui, tmp_path, monkeypatch, level):
    import brighteyes_mcs.ui.qt.pi23_timetagging as module
    from brighteyes_mcs.logging_setup import VERBOSITY_ENV_VAR

    executable = tmp_path / "recorder.exe"
    executable.touch()
    ui.lineEdit_pi23ttm_raw_executable.setText(str(executable))
    ui.comboBox_pi23ttm_format.setCurrentText("RAW")
    monkeypatch.setenv(VERBOSITY_ENV_VAR, str(level))
    launch = MagicMock(side_effect=OSError("synthetic launch failure"))
    monkeypatch.setattr(module.subprocess, "Popen", launch)
    recorder = Pi23Timetagging(ui)
    with pytest.raises(OSError, match="synthetic launch failure"):
        recorder.start(str(tmp_path / "scan.h5"), record=False)
    command = launch.call_args.args[0]
    assert ("--verbose" in command) == (level == 3)


def test_recorder_can_restart_after_failed_image_server_start(app, ui, tmp_path):
    executable = Path(ui.lineEdit_pi23ttm_raw_executable.text())
    if not executable.is_file():
        pytest.skip("Local vendor recorder build is not available")
    recorder = Pi23Timetagging(ui)
    failures = []
    recorder.failed.connect(failures.append)
    # Occupying the image port causes startup to fail before connecting to
    # any detector. Retry on the same controller to exercise the second start.
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        ui.spinBox_pi23ttm_stream_port.setValue(occupied.getsockname()[1])
        for attempt in range(2):
            recorder.start(str(tmp_path / "image.h5"), stream_image=True, record=False)
            wait_for(app, lambda: not recorder.active)
            assert len(failures) == attempt + 1
            assert not recorder.pending
            assert ui.spinBox_pi23ttm_stream_port.isEnabled()


def test_timestamp_socket_loss_is_failure_even_if_rust_exits_zero(ui):
    recorder = Pi23Timetagging(ui)
    recorder.process = MagicMock()
    recorder.process.wait.return_value = 0
    recorder.stream_image = True
    recorder.messages.put("Socket closed by server.\n")
    recorder.messages.put(None)
    failures = []
    recorder.failed.connect(failures.append)
    recorder.poll()
    assert failures == ["Socket closed by server."]
    assert recorder.stopping and not recorder.active


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


def test_stop_button_overrides_automatic_completion_tail():
    window = SimpleNamespace(_pending_program_state_after_stop="done", stop=MagicMock())
    MainWindow.stopButtonClicked(window)
    assert window._pending_program_state_after_stop is None
    window.stop.assert_called_once()


@pytest.mark.parametrize("phase", ["calibration", "acquisition"])
def test_stop_real_raw_recorder_during_blocked_device_read_and_restart(app, ui, tmp_path, phase):
    executable = Path(ui.lineEdit_pi23ttm_raw_executable.text())
    if not executable.is_file():
        pytest.skip("Local vendor recorder build is not available")
    with socket.socket() as port:
        port.bind(("127.0.0.1", 0))
        ui.spinBox_pi23ttm_stream_port.setValue(port.getsockname()[1])
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(2)
        server.settimeout(10)
        ui.lineEdit_pi23ttm_address.setText(f"127.0.0.1:{server.getsockname()[1]}")
        reached = [threading.Event(), threading.Event()]
        disconnected = [threading.Event(), threading.Event()]
        errors = []

        def device():
            try:
                for attempt in range(2):
                    connection, _ = server.accept()
                    with connection:
                        connection.settimeout(10)
                        connection.sendall(b"Fake PI23\n")
                        with connection.makefile("rb") as stream:
                            assert stream.readline() == b"T,v,1\n"
                            connection.sendall(b"invalid\n" if phase == "calibration" else b"valid\n")
                            command = stream.readline()
                            if phase == "calibration":
                                assert command == b"T,c,1\n"
                            else:
                                assert command.startswith(b"SB,")
                            reached[attempt].set()
                            # No response: calibration or acquisition is blocked.
                            assert stream.read(1) == b""
                            disconnected[attempt].set()
            except Exception as error:
                errors.append(error)

        worker = threading.Thread(target=device, daemon=True)
        worker.start()
        recorder = Pi23Timetagging(ui)
        failures, ready = [], []
        recorder.failed.connect(failures.append)
        recorder.ready.connect(lambda: ready.append(True))
        try:
            for attempt in range(2):
                recorder.start(str(tmp_path / "stop.h5"), stream_image=True, record=False, preview=True)
                wait_for(app, lambda attempt=attempt: reached[attempt].is_set() or errors)
                assert not errors
                recorder.stop()
                # Do not pump Qt: cancellation must not depend on GUI timers.
                recorder.process.wait(timeout=8)
                recorder.reader.join(timeout=2)
                recorder.poll()
                assert not recorder.active and not recorder.pending
                assert disconnected[attempt].wait(2)
                assert not failures
                assert ui.spinBox_pi23ttm_stream_port.isEnabled()
            if phase == "calibration":
                assert not ready
            worker.join(timeout=2)
            assert not errors
        finally:
            recorder.close()


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
        if raw:
            assert recorder.armed
            log = ui.plainTextEdit_pi23ttm_log.toPlainText()
            assert log.index("PI23_ARMED SB,") < log.index("Recorder ready; starting the FPGA scan.")
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


@pytest.mark.parametrize("record,microimage,save_h5", [
    (False, False, False), (True, False, False), (False, True, False),
    (True, True, True), (False, True, True),
])
def test_vendor_timestamp_image_and_optional_raw_recording(app, ui, tmp_path, record, microimage, save_h5):
    import subprocess
    import numpy as np
    preview = not record and not save_h5

    executable = Path(ui.lineEdit_pi23ttm_raw_executable.text())
    if not executable.is_file():
        pytest.skip("Local vendor recorder build is not available")
    help_result = subprocess.run([str(executable), "--help"], capture_output=True, text=True)
    option = "--stream-microimage" if microimage else "--stream-image"
    if option not in help_result.stderr + help_result.stdout:
        pytest.skip("Build tdc_raw_acquire with --stream-image support")
    with socket.socket() as stream_port:
        stream_port.bind(("127.0.0.1", 0))
        ui.spinBox_pi23ttm_stream_port.setValue(stream_port.getsockname()[1])
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(10)
    finish = threading.Event()
    errors = []
    commands = []
    # Combined frame/line/dwell, then three columns and two rows.
    repeat_frame = threading.Event()
    scan_ready = threading.Event()
    ids = [33, 0, 24, 27, 1, 27, 2, 2, 2, 29, 3, 27, 4, 4, 27, 5]
    if microimage:
        ids.append(27)  # Close the final dwell in the continuous subscription.
    payload = b"".join(bytes([marker, 0, 1, 0, 0, 2]) for marker in ids)

    def device():
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(10)
                connection.sendall(b"Fake PI23\n")
                with connection.makefile("rb") as stream:
                    assert stream.readline() == b"T,v,1\n"
                    connection.sendall(b"invalid\n")
                    assert stream.readline() == b"T,c,1\n"
                    connection.sendall(b"calibration valid\n")
                    commands.append(stream.readline())
                    assert commands[0].startswith(b"SB,")
                    assert scan_ready.wait(8)
                    connection.sendall(payload)
                    if preview:
                        assert repeat_frame.wait(8)
                        connection.sendall(b"DONE\n")
                        commands.append(stream.readline())
                        connection.sendall(payload)
                    assert finish.wait(8)
                    if not preview:
                        connection.sendall(b"DONE\n")
                    else:
                        assert stream.read(1) == b""
        except Exception as error:
            errors.append(error)
        finally:
            server.close()

    thread = threading.Thread(target=device, daemon=True)
    thread.start()
    ui.lineEdit_pi23ttm_address.setText(f"127.0.0.1:{server.getsockname()[1]}")
    ui.lineEdit_pi23ttm_folder.setText(str(tmp_path))
    ui.spinBox_nx.setValue(3)
    ui.spinBox_ny.setValue(2)
    ui.doubleSpinBox_pi23ttm_settle.setValue(0.1)
    recorder = Pi23Timetagging(ui)
    images, failures, ready = [], [], []
    worker = None
    manager = None
    shared = None
    if microimage:
        import multiprocessing as mp
        from brighteyes_mcs.acquisition.shared_memory import SharedMemoryRegistry
        from brighteyes_mcs.acquisition.preview import PreviewRepository
        from brighteyes_mcs.acquisition.detectors.pi23.microimage_worker import MicroimageWorker
        manager = mp.Manager()
        shared = manager.dict(channel="Sum")
        arrays = SharedMemoryRegistry().allocate_preview(dim_x=3, dim_y=2, dim_z=1,
            detector_dim=5, autocorrelation_maxx=2, trace_bins=2, dfd_bins=2)
        repository = PreviewRepository()
        repository.bind(arrays)
        saving = (dict(filename=str(tmp_path / "image.h5"), frames=1, repetitions=1,
                       dwell_seconds=0.001) if save_h5 else None)
        worker = MicroimageWorker(3, 2, ui.spinBox_pi23ttm_stream_port.value(), 2, arrays, shared, saving=saving)
        worker.start()
    else:
        recorder.image_ready.connect(images.append)
    recorder.failed.connect(failures.append)
    recorder.ready.connect(lambda: (ready.append(True), scan_ready.set()))
    try:
        recorder.start(str(tmp_path / "image.h5"), stream_image=not microimage,
                       stream_microimage=microimage, record=record, preview=preview, microimage_worker=worker)
        def received(frame):
            if microimage:
                return shared.get("pi23_uimg_status", {}).get("total_dwells", 0) >= 6 * (frame + 1)
            return images and images[-1].frame == frame and images[-1].events == 10
        wait_for(app, lambda: (ready and received(0)) or failures or errors)
        assert not failures and not errors
        if microimage:
            np.testing.assert_array_equal(repository.get_preview_image(), [[2, 1, 3], [1, 2, 1]])
            expected = np.zeros(25, dtype=np.uint64)
            expected[[0, 1, 2, 3, 4, 5, 24]] = [1, 1, 3, 1, 2, 1, 1]
            np.testing.assert_array_equal(repository.get_fingerprint(0).ravel(), expected)
            shared["channel"] = "2"
            wait_for(app, lambda: repository.get_preview_image().sum() == 3)
        else:
            np.testing.assert_array_equal(images[-1].counts, [[2, 1, 3], [1, 2, 1]])
        log = ui.plainTextEdit_pi23ttm_log.toPlainText()
        duration = measurement_ms(ui, preview=preview)
        assert commands == [f"SB,{duration}\n".encode()]
        assert f"--measurement-ms {duration}" in log
        if microimage:
            assert "--stream-microimage" in log and "--stream-image 3 2" not in log
            assert "--stream-image-pixel" not in log
            assert "--microimage-buffer 1048576" in log
        else:
            assert "--stream-image 3 2" in log and "--stream-microimage" not in log
        assert f"--stream-image-port {ui.spinBox_pi23ttm_stream_port.value()}" in log
        if preview:
            assert "--no-output" in log and "--repeat" in log
            assert recorder.path is None
            assert list(tmp_path.iterdir()) == []
            repeat_frame.set()
            wait_for(app, lambda: received(1) or failures or errors)
            assert not failures and not errors
            assert commands == [f"SB,{duration}\n".encode()] * 2
            recorder.stop()
        else:
            assert "--repeat" not in log
        finish.set()
        wait_for(app, lambda: not recorder.active)
        if record:
            assert recorder.path.read_bytes() == payload
        if save_h5:
            with h5py.File(tmp_path / "image.h5", "r") as saved:
                assert saved["data"].shape == (1, 1, 2, 3, 1, 25)
                assert saved["data"].dtype == np.dtype("uint32")
                np.testing.assert_array_equal(saved["data"][0, 0, :, :, 0].sum(axis=2), [[2, 1, 3], [1, 2, 1]])
                np.testing.assert_array_equal(saved["data"][...].sum(axis=(0, 1, 2, 3, 4)), expected)
                assert saved["pi23_microimages/valid"][...].all()
                assert saved["pi23_microimages"].attrs["complete"]
            if not record:
                assert recorder.path is None
                assert "--no-output" in log
                assert list(tmp_path.iterdir()) == [tmp_path / "image.h5"]
        assert not failures
        assert recorder.image_stop.is_set()
        thread.join(timeout=2)
        assert not errors
    finally:
        repeat_frame.set()
        finish.set()
        recorder.close()
        if worker is not None:
            worker.stop()
            worker.join(timeout=3)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=2)
        if manager is not None:
            manager.shutdown()
