"""Real Qt Flare panel checks; device access is explicitly mocked."""

import os
import logging
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch
from xml.etree import ElementTree
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import queue

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import numpy as np
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QTimer

from brighteyes_mcs.ui.controllers.flare import FlareController
from brighteyes_mcs.ui.qt.main_window import MainWindow
from brighteyes_mcs.ui.qt.main_window_design import Ui_MainWindowDesign
from brighteyes_mcs.hardware.flare import FlareError


@pytest.fixture
def panel(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    source = Path(__file__).resolve().parents[1] / "brighteyes_mcs/ui/qt/main_window_design.ui"
    for connection in ElementTree.parse(source).findall(".//connections/connection"):
        if connection.findtext("receiver") == "MainWindowDesign":
            name = connection.findtext("slot").split("(")[0]
            if not hasattr(window, name):
                setattr(window, name, lambda *args: None)
    window.ui = Ui_MainWindowDesign()
    window.ui.setupUi(window)
    window.ui.statusBar = window.statusBar()
    window.mcs_manager = SimpleNamespace(is_connected=False)
    window._set_program_state = Mock()
    controller = FlareController(window)
    # Keep device mocks in this interpreter for focused UI tests. Real spawn
    # and IPC integration is exercised separately in test_flare_process.py.
    def local_workers():
        if controller._process_pool is None:
            controller._process_pool = ThreadPoolExecutor(max_workers=3)
            controller._ipc_manager = SimpleNamespace(
                Event=threading.Event, dict=lambda **kw: dict(kw), Queue=queue.Queue,
                shutdown=lambda: None,
            )
    monkeypatch.setattr(controller, "_ensure_processes", local_workers)
    yield window, controller
    controller.close()
    window.close()
    app.processEvents()


def test_tabs_defaults_and_inactive_controls_never_construct_flare(panel):
    window, controller = panel
    ui = window.ui
    assert [ui.tabWidget_fpga_backends.tabText(i) for i in range(2)] == ["NI", "Kria Flare"]
    assert ui.comboBox_detector_model.findText("TCP/IP - FPGA Flare") == 4
    assert controller.settings().host == "mmskria3"
    assert controller.settings().port == 8081
    assert controller.settings().mode == "master"
    assert controller.settings().receiver_port == 9000
    with patch(
        "brighteyes_mcs.hardware.flare.FlareClient",
        side_effect=AssertionError("Flare must stay inactive"),
    ):
        ui.tabWidget_fpga_backends.setCurrentWidget(ui.tab_fpga_flare)
        controller.diagnostic("connect")
        controller.begin(False)
        for label in (
            "FPGA - SPAD",
            "TCP/IP - PI SPAD23R (Intensity)",
            "TCP/IP - PI SPAD23R (TS mode - uimg)",
            "Disable",
        ):
            controller.selection_changed(label)
        assert controller.job is None
        assert controller.run_job is None


@pytest.mark.parametrize("physical", [25, 49])
@pytest.mark.parametrize("version", [1, 2])
def test_flare_reference_selection_bypasses_detector_mask(panel, physical, version):
    window, controller = panel
    controller.selection_changed("TCP/IP - FPGA Flare")
    window.fingerprint_mask = np.zeros(physical)
    window.ui.comboBox_spad_channels.setCurrentText(str(physical))
    controller._discovery = {"firmware": {"supported_dfd_formats": [f"DFD{version}"]}}
    window.ui.checkBox_DFD.setChecked(True)
    controller._display = {}
    reference = physical + version - 1
    combo = window.ui.comboBox_plot_channel
    assert combo.findText(str(reference)) >= 0
    combo.setCurrentText(str(reference))
    controller.update_display()
    assert controller.display_channels == (reference,)
    assert controller._display['channels'] == (reference,)
    assert "Laser reference" in window.ui.label_plot_channel.text()
    if version == 2:
        combo.setCurrentText(str(physical))
        controller.update_display()
        assert controller.display_channels == (physical,)
        assert "Extra (unconnected)" in window.ui.label_plot_channel.text()
    combo.setCurrentText("Sum")
    controller.update_display()
    assert controller.display_channels == ()
    window.fingerprint_mask = np.ones(physical)
    controller.update_display()
    assert controller.display_channels == tuple(range(physical))
    controller.selection_changed("FPGA - SPAD")
    assert combo.findText(str(reference)) < 0


def test_selection_restores_existing_widget_state_and_slave_is_blocked(panel):
    window, controller = panel
    widget = window.ui.checkBox_DFD
    original = widget.isEnabled()
    controller.selection_changed("TCP/IP - FPGA Flare")
    assert widget.isEnabled() == original
    window.ui.comboBox_flare_mode.setCurrentText("slave")
    controller.begin()
    assert controller.run_job is None
    assert "external NI timing" in window.ui.plainTextEdit_flare_log.toPlainText()
    controller.selection_changed("FPGA - SPAD")
    assert widget.isEnabled() == original
    assert not controller._repeat.isActive()


def test_configuration_warnings_appear_in_flare_log_only_while_selected(panel):
    window, controller = panel
    logger = logging.getLogger("brighteyes_mcs.acquisition.detectors.flare.config")
    controller.selection_changed("TCP/IP - FPGA Flare")
    logger.warning("X scan exceeds the configured voltage limits; continuing")
    assert "configured voltage limits; continuing" in window.ui.plainTextEdit_flare_log.toPlainText()
    controller.selection_changed("FPGA - SPAD")
    window.ui.plainTextEdit_flare_log.clear()
    logger.warning("Inactive Flare warning")
    assert not window.ui.plainTextEdit_flare_log.toPlainText()


def test_discovery_and_register_display(panel):
    window, controller = panel
    controller.selection_changed("TCP/IP - FPGA Flare")
    controller._diagnostic_result(
        {
            "action": "read_all",
            "discovery": {
                "firmware": {
                    "board_id": 0x464C5234,
                    "schema_version": 0x30000,
                    "clock_hz": 100000000,
                },
                "registers": [
                    {
                        "name": "scratch",
                        "address_hex": "0x10",
                        "type": "U32",
                        "access": "RW",
                        "write_policy": "live",
                    }
                ],
                "status": {"dma": {"state": 0}},
            },
            "result": {"scratch": 42},
        },
        None,
    )
    assert window.ui.tableWidget_flare_registers.item(0, 5).text() == "42"
    controller.select_register(0, 0)
    assert window.ui.lineEdit_flare_register.text() == "scratch"
    assert window.ui.pushButton_flare_write.isEnabled()


def test_preview_completion_keeps_controls_locked_until_stop_between_frames(panel):
    window, controller = panel
    window.PROGRAM_STATE_IDLE = "idle"
    window.PROGRAM_STATE_ACQUISITION_DONE = "acquisition_done"
    window.started_preview = True
    window.started_normal = False
    controller.preview = True
    before = window.ui.spinBox_nx.isEnabled()
    controller._busy(True)
    controller._busy(True)
    controller._acquisition_result({"complete": True, "result": "complete"}, None)
    assert window.started_preview
    assert not window.ui.comboBox_detector_model.isEnabled()
    controller._run_finished()
    assert controller._repeat.isActive()
    controller.stop()
    assert not window.started_preview
    assert not controller._repeat.isActive()
    assert window.ui.spinBox_nx.isEnabled() == before
    assert window.ui.comboBox_flare_mode.isEnabled()


@pytest.mark.parametrize("preview", [True, False])
def test_repeated_busy_failures_offer_reset_only_after_user_accepts(preview_panel, preview):
    from PySide6.QtWidgets import QMessageBox

    window, controller = preview_panel
    failure = {"complete": False, "error": "Flare is busy; inspect status", "result": "partial"}
    with patch.object(controller, "diagnostic") as diagnostic:
        controller.preview = preview
        controller._acquisition_result(failure, None)
        assert controller._reset_prompt is None
        assert "Flare is busy" in window.ui.statusBar.currentMessage()
        controller._acquisition_result(failure, None)
        assert controller._reset_prompt is not None
        diagnostic.assert_not_called()
        controller._reset_prompt.done(QMessageBox.StandardButton.Cancel)
        diagnostic.assert_not_called()
        assert controller._reset_prompt is None
        controller._acquisition_result(failure, None)
        controller._acquisition_result(failure, None)
        controller._reset_prompt.done(QMessageBox.StandardButton.Reset)
        diagnostic.assert_called_once_with("reset")


def test_old_busy_failures_do_not_trigger_reset_prompt(preview_panel):
    _, controller = preview_panel
    failure = {"complete": False, "error": "Flare is busy", "result": "partial"}
    controller.preview = True
    with patch("brighteyes_mcs.ui.controllers.flare.time.monotonic", side_effect=[0, 31]):
        controller._acquisition_result(failure, None)
        controller._acquisition_result(failure, None)
    assert controller._reset_prompt is None


def test_queue_overflow_remains_visible_and_does_not_reset_automatically(preview_panel):
    window, controller = preview_panel
    controller.preview = True
    with patch.object(controller, "diagnostic") as diagnostic:
        controller._acquisition_result({
            "complete": False, "result": "partial", "recovery_required": True,
            "error": "Flare processing queue filled; capture is incomplete",
        }, None)
        assert "queue filled" in window.ui.statusBar.currentMessage()
        assert "Stop or Reset" in window.ui.statusBar.currentMessage()
        assert not window.started_preview
        diagnostic.assert_not_called()


@pytest.mark.parametrize("name", ["max_pixel", "REG_MAX_PIXEL", "0x104"])
def test_stopped_register_writes_are_sent_during_local_startup(panel, name):
    window, controller = panel
    controller.selection_changed("TCP/IP - FPGA Flare")
    controller.run_job = Mock()
    controller.run_job.isRunning.return_value = True
    controller._catalog = {"max_pixel": {"address": 0x0104, "write_policy": "stopped"}}
    window.ui.lineEdit_flare_register.setText(name)
    window.ui.lineEdit_flare_value.setText("10")
    try:
        with (
            patch("brighteyes_mcs.ui.controllers.flare.FlareJob") as job,
            patch("brighteyes_mcs.hardware.flare.FlareClient") as client,
        ):
            controller.diagnostic("write")
            assert job.called
            job.call_args.args[0]()
            client.return_value.write_register.assert_called_once_with(name, 10)
    finally:
        controller.run_job = controller.job = None


@pytest.mark.parametrize("canonical,address,value", [
    ("laser_1_enable", 0x0450, 1),
    ("master_laser_clk_apply", 0x8078, 1),
    ("max_pixel", 0x0104, 7),
    ("command", 0x0010, 1),
])
@pytest.mark.parametrize("notation", ["name", "constant", "address"])
def test_live_register_writes_during_local_acquisition_accept_all_notations(
    panel, canonical, address, value, notation,
):
    window, controller = panel
    controller.selection_changed("TCP/IP - FPGA Flare")
    controller._catalog = {canonical: {"address": address, "write_policy": "live"}}
    name = {"name": canonical, "constant": "REG_" + canonical.upper(), "address": hex(address)}[notation]
    window.ui.lineEdit_flare_register.setText(name)
    window.ui.lineEdit_flare_value.setText(str(value))
    controller.run_job = Mock()
    controller.run_job.isRunning.return_value = True
    try:
        with (
            patch("brighteyes_mcs.ui.controllers.flare.FlareJob") as job,
            patch("brighteyes_mcs.hardware.flare.FlareClient") as client,
        ):
            controller.diagnostic("write")
            assert job.called, window.ui.plainTextEdit_flare_log.toPlainText()
            job.call_args.args[0]()
            client.return_value.write_register.assert_called_once_with(name, value)
            client.return_value.command.assert_not_called()
    finally:
        controller.run_job = controller.job = None


@pytest.fixture
def preview_panel(panel):
    window, controller = panel
    controller.selection_changed("TCP/IP - FPGA Flare")
    for name in (
        "DFD", "fifo_analog", "ttmActivate", "uttmActivate", "pispad23ttmActivate",
        "pulsing_forced", "fcs_preview",
    ):
        getattr(window.ui, "checkBox_" + name).setChecked(False)
    values = dict(
        projection="xy", preview_channel="Sum", nx=3, ny=2, nframe=1,
        range_x=0, range_y=0, range_z=0, offset_x_um=0, offset_y_um=0, offset_z_um=0,
        nrep=1, timebin_per_pixel=3, time_resolution=1000, spad_channels="25",
        calib_x=1, calib_y=1,
    )
    for axis in "xy":
        getattr(window.ui, f"spinBox_calib_{axis}").setValue(1)
        getattr(window.ui, f"spinBox_range_{axis}").setValue(1)
        getattr(window.ui, f"spinBox_off_{axis}_um").setValue(0)
    window.ui.spinBox_nx.setValue(3)
    window.ui.spinBox_ny.setValue(2)
    window.ui.spinBox_nframe.setValue(1)
    window.ui.spinBox_calib_z.setValue(1)
    window.getGUI_data = lambda: dict(values, **{
        key: getattr(window.ui, widget).value()
        for axis in "xy" for key, widget in (
            (f"range_{axis}", f"spinBox_range_{axis}"),
            (f"offset_{axis}_um", f"spinBox_off_{axis}_um"),
        )
    })
    window.fingerprint_mask = np.ones(49)
    window.PROGRAM_STATE_PREVIEW = "preview"
    window.PROGRAM_STATE_IDLE = "idle"
    window.started_preview = window.started_normal = False
    window.preview_run_id = 0
    window._make_status_timestamp = Mock(return_value="now")
    window.currentImage = np.full((2, 3), 123, dtype=np.uint64)
    window.im_widget = Mock()
    window.draw_fingerprint = Mock()
    window.ui.checkBox_showPreview.setChecked(True)
    return window, controller


@pytest.mark.parametrize("continuing,stopping", [(True, False), (False, False), (True, True)])
def test_only_continuing_preview_passes_previous_image_to_next_run(preview_panel, continuing, stopping):
    window, controller = preview_panel
    controller.preview, controller.stopping = continuing, stopping
    previous = np.full((2, 3), 123, dtype=np.uint64)
    controller.last_snapshot = {"image": previous}
    with (
        patch("brighteyes_mcs.ui.controllers.flare.FlareJob") as job,
        patch("brighteyes_mcs.hardware.flare.FlareClient"),
        patch("brighteyes_mcs.acquisition.flare_worker.configuration_from_gui"),
        patch("brighteyes_mcs.acquisition.flare.FlareAcquisition") as acquisition,
    ):
        job.return_value.isRunning.return_value = False
        controller.begin(True)
        assert job.called, window.ui.plainTextEdit_flare_log.toPlainText()
        job.call_args.args[0]()
        seed = acquisition.call_args.kwargs["initial_image"]
        assert seed is (previous if continuing and not stopping else None)
        controller.runner = controller.run_job = None


@pytest.mark.parametrize("preview", [True, False])
def test_xyz_geometry_is_editable_during_preview_and_recording(panel, preview):
    window, controller = panel
    controller.preview = preview
    names = tuple(name for axis in "xyz" for name in (f"spinBox_range_{axis}", f"spinBox_off_{axis}_um"))
    before = {name: getattr(window.ui, name).isEnabled() for name in names}
    controller._busy(True)
    for name in names:
        assert getattr(window.ui, name).isEnabled() == before[name]
    assert not window.ui.spinBox_nx.isEnabled()
    controller._busy(False)
    assert {name: getattr(window.ui, name).isEnabled() for name in names} == before


@pytest.mark.parametrize("laser", [1, 2, 3, 4])
def test_laser_checkboxes_send_live_on_and_off_and_are_inactive_for_other_detectors(panel, laser):
    window, controller = panel
    checkbox = getattr(window.ui, f"checkBox_laser{laser - 1}")
    with patch("brighteyes_mcs.hardware.flare.FlareClient") as factory:
        device = factory.return_value
        device.write_register.side_effect = lambda name, value: {"name": name, "value": value}
        checkbox.setChecked(False)
        checkbox.setChecked(True)
        QTest.qWait(100)
        factory.assert_not_called()
        controller.selection_changed("TCP/IP - FPGA Flare")
        controller.connected = True
        checkbox.setChecked(False)
        _wait_live_idle(controller)
        device.write_register.assert_called_with(f"laser_{laser}_enable", 0)
        checkbox.setChecked(True)
        _wait_live_idle(controller)
        device.write_register.assert_called_with(f"laser_{laser}_enable", 1)
        controller.selection_changed("FPGA - SPAD")
        device.write_register.reset_mock()
        checkbox.setChecked(False)
        QTest.qWait(100)
        device.write_register.assert_not_called()


def _wait_live_idle(controller):
    for _ in range(200):
        QApplication.processEvents()
        if not controller._live_timer.isActive() and controller.live_job is None:
            return
        QTest.qWait(10)
    pytest.fail("Live register worker did not finish")


def test_live_server_errors_appear_in_panel_without_changing_selection_or_retry(panel):
    window, controller = panel
    controller.selection_changed("TCP/IP - FPGA Flare")
    controller.connected = True
    error = "PUT /registers/laser_1_enable: HTTP 409, errno=16: busy"
    with patch("brighteyes_mcs.hardware.flare.FlareClient") as factory:
        factory.return_value.write_register.side_effect = FlareError(error)
        controller.queue_registers({"laser_1_enable": 1})
        _wait_live_idle(controller)
        assert error in window.ui.plainTextEdit_flare_log.toPlainText()
        assert error in window.ui.statusBar.currentMessage()
        assert controller.connected and controller.selected
        assert factory.return_value.write_register.call_count == 1
        factory.return_value.command.assert_not_called()


@pytest.mark.parametrize("axis", list("xyz"))
def test_position_and_range_controls_send_axis_arrays_and_commit_live(preview_panel, axis):
    window, controller = preview_panel
    controller.connected = True
    controller.preview = False
    controller._busy(True)
    original = window.getGUI_data
    window.getGUI_data = lambda: dict(original(), **{
        key: getattr(window.ui, widget).value() for name in "xyz" for key, widget in (
            (f"range_{name}", f"spinBox_range_{name}"),
            (f"offset_{name}_um", f"spinBox_off_{name}_um"),
        )
    })
    with patch("brighteyes_mcs.hardware.flare.FlareClient") as factory:
        device = factory.return_value
        device.write_register.side_effect = lambda name, value: {"name": name, "value": value}
        getattr(window.ui, f"spinBox_range_{axis}").setValue(0.4)
        getattr(window.ui, f"spinBox_off_{axis}_um").setValue(0.5)
        _wait_live_idle(controller)
        writes = dict(call.args for call in device.write_register.call_args_list)
        index = "xyz".index(axis)
        assert writes["axis_start_offset_volts"][index] == round(0.3 * 32768 / 10)
        count = window.getGUI_data()[{"x": "nx", "y": "ny", "z": "nframe"}[axis]]
        assert writes["axis_calibration_volts_per_step"][index] == round(0.4 / count * 32768 / 10)
        assert device.write_register.call_args.args == ("command", 1)
        device.configure.assert_not_called()
        device.command.assert_not_called()
    controller._busy(False)


def test_selected_lasers_are_passed_to_acquisition_instead_of_rejected(preview_panel):
    window, controller = preview_panel
    window.ui.checkBox_laser0.setChecked(True)
    window.ui.checkBox_laser3.setChecked(True)
    with (
        patch("brighteyes_mcs.ui.controllers.flare.FlareJob") as job,
        patch("brighteyes_mcs.hardware.flare.FlareClient") as factory,
        patch("brighteyes_mcs.acquisition.flare.FlareAcquisition") as acquisition,
    ):
        job.return_value.isRunning.return_value = False
        factory.return_value.firmware = {"clock_hz": 100000000}
        controller.begin(True)
        assert job.called, window.ui.plainTextEdit_flare_log.toPlainText()
        job.call_args.args[0]()
        assert acquisition.call_args.kwargs["live_controls"] is controller.live_controls
        device = Mock()
        device.write_register.side_effect = lambda name, value: {"name": name, "value": value}
        controller.live_controls.apply(device, restore=True)
        writes = dict(call.args for call in device.write_register.call_args_list)
        assert writes["laser_1_enable"] == writes["laser_4_enable"] == 1
        controller.runner = controller.run_job = None


@pytest.mark.parametrize("projection", ["xy", "yx"])
def test_pan_zoom_updates_display_immediately_and_reuses_it_in_next_scan(preview_panel, projection):
    window, controller = preview_panel
    window.ui.comboBox_view_projection.setCurrentText(projection)
    jobs = []

    def make_job(function, parent):
        job = Mock()
        job.function = function
        job.isRunning.return_value = False
        jobs.append(job)
        return job

    with (
        patch("brighteyes_mcs.ui.controllers.flare.FlareJob", side_effect=make_job),
        patch("brighteyes_mcs.hardware.flare.FlareClient") as client,
        patch("brighteyes_mcs.acquisition.flare.FlareAcquisition") as acquisition,
    ):
        client.return_value.firmware = {"clock_hz": 100000000}
        acquisition.return_value.run.return_value = {"complete": True, "result": "complete"}
        controller.begin(True)
        jobs[0].function()
        first_configuration = acquisition.call_args.args[1]
        publish = acquisition.call_args.kwargs["on_snapshot"]
        snapshot = dict(
            image=window.currentImage, bins=1, total_bins=18, receiver_bytes=120,
            expected_bytes=2160, status={}, fingerprint=np.zeros(25), trace=None,
        )
        publish(snapshot)
        first_snapshot = jobs[0].function.arguments["snapshots"].get_nowait()
        controller.render(first_snapshot)
        # Exercise the existing preview navigation handler with new view bounds.
        window.preview_view_box = SimpleNamespace(navigation_event_active=True)
        window.lock_parameters_changed_call = window.lock_range_changing = False
        bounds = {"bottom": (1, 3), "left": (-2, 0)}
        window.im_widget_plot_item = SimpleNamespace(
            getAxis=lambda name: SimpleNamespace(range=bounds[name])
        )
        window.updateLabelPixelSize = Mock()
        window.plotPreviewImage = lambda: MainWindow.plotPreviewImage(window)
        window.flare = controller
        window.positionSettingsChanged = Mock()
        MainWindow.axesRangeChanged(window)
        assert window.ui.spinBox_range_x.value() == 2
        assert window.ui.spinBox_range_y.value() == 2
        assert window.ui.spinBox_off_x_um.value() == (2 if projection == "xy" else -1)
        assert window.ui.spinBox_off_y_um.value() == (-1 if projection == "xy" else 2)
        # An old queued snapshot must not undo the synchronous display update.
        controller.render(first_snapshot)
        assert window.im_widget.setImage.call_args.kwargs["pos"] == (1, -2)
        assert window.im_widget.setImage.call_args.kwargs["autoRange"] is False
        assert window.im_widget.getView().setRange.call_count == 1
        np.testing.assert_array_equal(window.currentImage_pos, [2, -1, 0] if projection == "xy" else [-1, 2, 0])
        assert controller.last_snapshot["geometry"] == first_snapshot["geometry"]
        window._update_offset_voltage_labels = Mock()
        window.AutoRange_im_widget = Mock()
        MainWindow.offset_um_update(window)
        window.AutoRange_im_widget.assert_not_called()
        # Complete the finite run, then start the next one with the latest edits.
        controller._acquisition_result({"complete": True, "result": "complete"}, None)
        controller._run_finished()
        controller._repeat.stop()
        controller.begin(True)
        jobs[1].function()
        second_configuration = acquisition.call_args.args[1]
        assert second_configuration["x_start"] != first_configuration["x_start"]
        assert second_configuration["y_start"] != first_configuration["y_start"]
        assert second_configuration["x_step"] == round(2 / 3 * 32768 / 10)
        acquisition.call_args.kwargs["on_snapshot"](snapshot)
        controller.render(jobs[1].function.arguments["snapshots"].get_nowait())
        assert window.im_widget.setImage.call_args.kwargs["pos"] == (1, -2)
        assert window.im_widget.setImage.call_args.kwargs["autoRange"] is False
        assert window.im_widget.getView().setRange.call_count == 1
        controller.runner = controller.run_job = None


def test_stream_updates_preserve_manual_view_range(preview_panel):
    import pyqtgraph as pg

    window, controller = preview_panel
    window.im_widget = pg.ImageView(parent=window, view=pg.PlotItem())
    snapshot = dict(
        image=window.currentImage, bins=1, total_bins=18, receiver_bytes=120,
        expected_bytes=2160, status={}, fingerprint=np.zeros(25), trace=None,
        geometry=window.getGUI_data(),
    )
    controller.render(snapshot)
    view = window.im_widget.getView()
    view.setRange(xRange=(1, 3), yRange=(-2, 0), padding=0)
    manual_bounds = np.asarray(view.viewRange()).copy()
    controller.render(snapshot)
    controller.plot_image()
    np.testing.assert_allclose(view.viewRange(), manual_bounds)
    window.im_widget.close()


@pytest.mark.parametrize("slow_action", ["read_all", "write"])
def test_slow_register_requests_do_not_block_qt_or_other_reads(panel, slow_action):
    window, controller = panel
    controller.selection_changed("TCP/IP - FPGA Flare")
    controller._discovery = {
        "firmware": {}, "status": {"dma": {}},
        "registers": [{"name": "scratch", "address": 12, "write_policy": "live"}],
    }
    entered, release = threading.Event(), threading.Event()
    calls, ticks = [], []

    class Device:
        def __init__(self, settings):
            pass

        def discover(self):
            raise AssertionError("Register requests must reuse cached discovery")

        def read_all(self):
            if slow_action == "read_all":
                entered.set()
                assert release.wait(5)
            else:
                calls.append(("read_all",))
            return {"scratch": 3}

        def read_register(self, name):
            calls.append(("read", name))
            return {"name": name, "value": 1}

        def write_register(self, name, value):
            if slow_action == "write":
                entered.set()
                assert release.wait(5)
            else:
                calls.append(("write", name, value))
            return {"name": name, "value": value}

        def close(self):
            pass

    timer = QTimer(window)
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    window.ui.lineEdit_flare_register.setText("scratch")
    window.ui.lineEdit_flare_value.setText("7")
    try:
        with patch("brighteyes_mcs.hardware.flare.FlareClient", Device):
            controller.diagnostic(slow_action)
            for _ in range(100):
                QTest.qWait(5)
                if entered.is_set():
                    break
            assert entered.is_set()
            controller.diagnostic("read")
            controller.diagnostic("write" if slow_action == "read_all" else "read_all")
            for _ in range(100):
                QTest.qWait(5)
                if len(calls) == 2 and len(ticks) >= 3:
                    break
            assert ("read", "scratch") in calls
            assert (("write", "scratch", 7) if slow_action == "read_all" else ("read_all",)) in calls
            assert len(ticks) >= 3
            assert not release.is_set()
            assert controller.register_jobs  # The slow operation remains in flight.
            release.set()
            for _ in range(100):
                QTest.qWait(5)
                if not controller.register_jobs:
                    break
            assert not controller.register_jobs
    finally:
        release.set()
        timer.stop()


@pytest.mark.parametrize("gesture", ["wheel", "pan"])
@pytest.mark.parametrize("projection", ["xy", "yx"])
@pytest.mark.parametrize("viewport", [(900, 360), (360, 900)])
def test_real_preview_gestures_preserve_view_after_live_geometry_commit(
    preview_panel, gesture, projection, viewport,
):
    import pyqtgraph as pg
    from brighteyes_mcs.ui.qt.flim_image_view import ModifierGatedViewBox

    window, controller = preview_panel
    window.ui.comboBox_view_projection.setCurrentText(projection)
    window.ui.spinBox_nx.setValue(64)
    window.ui.spinBox_ny.setValue(64)
    window.currentImage = np.zeros((64, 64), dtype=np.uint64)
    view = ModifierGatedViewBox()
    view.setMouseMode(pg.ViewBox.PanMode)
    plot = pg.PlotItem(viewBox=view)
    window.im_widget = pg.ImageView(parent=window, view=plot)
    window.im_widget.resize(*viewport)
    window.im_widget.show()
    window.preview_view_box = view
    window.im_widget_plot_item = plot
    window.flare = controller
    window.updateLabelPixelSize = Mock()
    window.positionSettingsChanged = Mock(side_effect=AssertionError("NI callback during Flare gesture"))
    plot.sigRangeChanged.connect(lambda *_: MainWindow.axesRangeChanged(window))
    view.sigRangeChangedManually.connect(controller.preserve_preview_view)
    snapshot = dict(
        image=window.currentImage, bins=1, total_bins=18, receiver_bytes=120,
        expected_bytes=2160, status={}, fingerprint=np.zeros(25), trace=None,
        geometry=window.getGUI_data(),
    )
    controller.render(snapshot)
    QApplication.processEvents()
    start_bounds = np.asarray(view.viewRange()).copy()
    window.getGUI_data = Mock(side_effect=AssertionError("Full profile read during gesture"))
    try:
        for step in range(4):
            event = Mock()
            event.modifiers.return_value = Qt.KeyboardModifier.ControlModifier
            event.pos.return_value = pg.Point(160 + step * 5, 130 + step * 2)
            with patch.object(window.im_widget, "setImage", wraps=window.im_widget.setImage) as redraw:
                if gesture == "wheel":
                    event.delta.return_value = 120
                    view.wheelEvent(event)
                else:
                    event.button.return_value = Qt.MouseButton.LeftButton
                    event.lastPos.return_value = pg.Point(150 + step * 5, 120 + step * 2)
                    view.mouseDragEvent(event)
                redraw.assert_not_called()  # No histogram or image processing during the gesture.
            bounds = np.asarray(view.viewRange()).copy()
            assert controller._preserve_view
            span = min(high - low for low, high in bounds)
            assert window.ui.spinBox_range_x.value() == pytest.approx(span, abs=0.0005)
            assert window.ui.spinBox_range_y.value() == window.ui.spinBox_range_x.value()
            controller._live_timer.stop()  # Server acceptance is simulated below.
            # The cached image is already in the requested area, before any
            # write/COMMIT or next data frame. This catches the two-stage flicker.
            item = window.im_widget.getImageItem()
            rect = item.mapRectToParent(item.boundingRect())
            for index, axis in enumerate(projection):
                extent = rect.width() if index == 0 else rect.height()
                center = rect.center().x() if index == 0 else rect.center().y()
                assert extent == pytest.approx(getattr(window.ui, f"spinBox_range_{axis}").value())
                assert center == pytest.approx(getattr(window.ui, f"spinBox_off_{axis}_um").value())
            immediate_transform = item.transform()
            # A previously queued frame and an older COMMIT must not reintroduce
            # the old coordinates while the latest request is still pending.
            controller.render(snapshot)
            assert item.transform() == immediate_transform
            np.testing.assert_allclose(view.viewRange(), bounds, atol=1e-9)
            # Simulate the server accepting the latest spatial edit, then new data.
            device = Mock()
            device.write_register.side_effect = lambda name, value: {"name": name, "value": value}
            controller.live_controls.apply(device)
            controller.render(dict(snapshot, geometry=controller.live_controls.geometry()))
            assert item.transform() == immediate_transform
            QApplication.processEvents()
            np.testing.assert_allclose(view.viewRange(), bounds, atol=1e-9)
            # Check actual screen pixel dimensions after live data/COMMIT.
            item = window.im_widget.getImageItem()
            origin = item.mapToScene(pg.Point(0, 0))
            x_pixel = item.mapToScene(pg.Point(1, 0)) - origin
            y_pixel = item.mapToScene(pg.Point(0, 1)) - origin
            assert np.hypot(x_pixel.x(), x_pixel.y()) == pytest.approx(np.hypot(y_pixel.x(), y_pixel.y()))
            event.accept.assert_called()
        assert not np.allclose(view.viewRange(), start_bounds)
        window.getGUI_data.assert_not_called()
        window.positionSettingsChanged.assert_not_called()
    finally:
        controller._status_timer.stop()
        window.im_widget.close()


@pytest.mark.parametrize("projection", ["xy", "yx"])
@pytest.mark.parametrize("bounds", [
    {"bottom": (1, 7), "left": (-2, 0)},
    {"bottom": (1, 3), "left": (-4, 2)},
])
def test_flare_navigation_matches_spad_scan_ranges_in_rectangular_viewport(preview_panel, projection, bounds):
    window, controller = preview_panel
    window.ui.comboBox_view_projection.setCurrentText(projection)
    plot = SimpleNamespace(getAxis=lambda name: SimpleNamespace(range=bounds[name]))
    ni = SimpleNamespace(
        ui=window.ui, preview_view_box=SimpleNamespace(navigation_event_active=True),
        im_widget_plot_item=plot, lock_parameters_changed_call=False, lock_range_changing=False,
        updateLabelPixelSize=Mock(), started_preview=False, started_normal=False,
    )
    MainWindow.axesRangeChanged(ni)
    names = ("spinBox_range_x", "spinBox_range_y", "spinBox_off_x_um", "spinBox_off_y_um")
    expected = {name: getattr(window.ui, name).value() for name in names}
    for name in names:
        getattr(window.ui, name).setValue(1 if "range" in name else 0)
    window.im_widget_plot_item = plot
    window.updateLabelPixelSize = Mock()
    controller.navigate_preview()
    assert {name: getattr(window.ui, name).value() for name in names} == expected


def test_requested_preview_area_is_immediate_while_older_commits_are_in_flight(preview_panel):
    import pyqtgraph as pg

    window, controller = preview_panel
    window.im_widget = pg.ImageView(parent=window, view=pg.PlotItem())
    snapshot = dict(
        image=window.currentImage, bins=1, total_bins=18, receiver_bytes=120,
        expected_bytes=2160, status={}, fingerprint=np.zeros(25), trace=None,
        geometry=window.getGUI_data(),
    )
    controller.render(snapshot)
    entered, release_first = threading.Event(), threading.Event()
    second_commit, release_second = threading.Event(), threading.Event()
    commits = []

    class Device:
        def __init__(self, settings):
            pass

        def write_register(self, name, value):
            if name == "axis_start_offset_volts" and not entered.is_set():
                entered.set()
                assert release_first.wait(5)
            if name == "command":
                commits.append(value)
                if len(commits) == 2:
                    second_commit.set()
                    assert release_second.wait(5)
            return {"name": name, "value": value}

        def close(self):
            pass

    def wait_for(event):
        for _ in range(200):
            if event.is_set():
                return
            QTest.qWait(5)
        pytest.fail("Expected background register request did not arrive")

    item = window.im_widget.getImageItem()
    try:
        with patch("brighteyes_mcs.hardware.flare.FlareClient", Device):
            window.ui.spinBox_off_x_um.setValue(1)
            # The transform changes before the write timer even fires.
            assert not entered.is_set()
            assert item.mapRectToParent(item.boundingRect()).center().x() == pytest.approx(1)
            wait_for(entered)
            assert controller.live_controls.geometry() is None
            window.ui.spinBox_off_x_um.setValue(2)
            assert item.mapRectToParent(item.boundingRect()).center().x() == pytest.approx(2)
            requested_transform = item.transform()
            controller.render(snapshot)
            assert item.transform() == requested_transform
            release_first.set()
            wait_for(second_commit)
            # The board has accepted the older area, while the new area is
            # still blocked. Neither that confirmation nor its data may snap back.
            previous_geometry = controller.live_controls.geometry()
            assert previous_geometry["offset_x_um"] == 1
            controller.render(dict(snapshot, geometry=previous_geometry))
            assert item.transform() == requested_transform
            release_second.set()
            _wait_live_idle(controller)
            assert controller.live_controls.geometry()["offset_x_um"] == 2
            assert item.transform() == requested_transform
    finally:
        release_first.set()
        release_second.set()
        controller._status_timer.stop()
        window.im_widget.close()


def test_flare_dfd_profile_restores_ni_clock_and_bins(panel):
    window, controller = panel
    window.ui.spinBox_DFD_nbins.setValue(81)
    window.ui.spinBox_clk_base_multiplier.setValue(2)
    label = window.ui.label_120.text()
    controller.selection_changed("TCP/IP - FPGA Flare")
    assert window.ui.spinBox_DFD_nbins.value() == window.DFD_nbins == 91
    assert window.ui.spinBox_clk_base_multiplier.value() == 1
    assert not window.ui.spinBox_DFD_nbins.isEnabled()
    assert window.ui.checkBox_DFD.isEnabled()
    controller.selection_changed("FPGA - SPAD")
    assert window.ui.spinBox_DFD_nbins.value() == window.DFD_nbins == 81
    assert window.ui.spinBox_clk_base_multiplier.value() == 2
    assert window.ui.label_120.text() == label


def test_flare_dfd_begin_uses_existing_sequence_and_reference_controls(preview_panel):
    window, controller = preview_panel
    window.ui.checkBox_DFD.setChecked(True)
    window.ui.checkBox_DFD_LaserDebug.setChecked(True)
    window.ui.checkBox_laser0.setChecked(True)
    window.ui.comboLaserSeq_1.setCurrentText("1")
    window.ui.comboLaserSeq_2.setCurrentText("4")
    with (
        patch("brighteyes_mcs.ui.controllers.flare.FlareJob") as job,
        patch("brighteyes_mcs.hardware.flare.FlareClient") as factory,
        patch("brighteyes_mcs.acquisition.flare.FlareAcquisition") as acquisition,
    ):
        job.return_value.isRunning.return_value = False
        factory.return_value.firmware = {"clock_hz": 100000000}
        controller.begin(True)
        assert job.called, window.ui.plainTextEdit_flare_log.toPlainText()
        job.call_args.args[0]()
        configuration = acquisition.call_args.args[1]
        assert configuration["acquisition_mode"] == "dfd"
        assert configuration["laser_excitation_sequence"] == [1, 8, 0, 0, 0, 0]
        assert configuration["laser_enable_mask"] == 1
        assert configuration["dfd_reference_enable"] == 1
        factory.return_value.check_acquisition_support.assert_called_once_with(dfd=True)
        for name in ("comboLaserSeq_1", "checkBox_laser0", "spinBox_range_z", "checkBox_DFD_LaserDebug"):
            assert not getattr(window.ui, name).isEnabled()
        for axis in "xy":
            assert getattr(window.ui, f"spinBox_range_{axis}").isEnabled()
            assert getattr(window.ui, f"spinBox_off_{axis}_um").isEnabled()
        controller._busy(False)
        assert window.ui.comboLaserSeq_1.isEnabled()
        controller.runner = controller.run_job = None


def test_dfd_preview_geometry_is_committed_live_and_retained_next_frame(preview_panel):
    window, controller = preview_panel
    window.ui.checkBox_DFD.setChecked(True)
    with (
        patch("brighteyes_mcs.ui.controllers.flare.FlareJob") as job,
        patch("brighteyes_mcs.hardware.flare.FlareClient") as factory,
        patch("brighteyes_mcs.acquisition.flare.FlareAcquisition") as acquisition,
    ):
        job.return_value.isRunning.return_value = False
        factory.return_value.firmware = {"clock_hz": 100000000}
        controller.begin(True)
        job.call_args.args[0]()
        first = dict(acquisition.call_args.args[1])
        window.ui.spinBox_range_x.setValue(0.6)
        window.ui.spinBox_off_x_um.setValue(0.3)
        factory.return_value.write_register.side_effect = lambda name, value: {"name": name, "value": value}
        controller._start_live_write()
        task = job.call_args.args[0]
        assert task.action == "live"
        task()
        writes = factory.return_value.write_register.call_args_list
        assert [call.args[0] for call in writes] == [
            "axis_start_offset_volts", "axis_calibration_volts_per_step", "command",
        ]
        assert writes[0].args[1][0] == 0
        assert writes[1].args[1][0] == round(0.6 / 3 * 32768 / 10)
        assert writes[2].args == ("command", 1)
        assert controller.live_controls.geometry()["offset_x_um"] == 0.3
        controller.live_job = None
        controller._acquisition_result({"complete": True, "result": "complete"}, None)
        controller._run_finished()
        controller._repeat.stop()
        controller.begin(True)
        job.call_args.args[0]()
        second = acquisition.call_args.args[1]
        assert second["x_start"] != first["x_start"]
        assert second["x_step"] == round(0.6 / 3 * 32768 / 10)
        controller.run_job = None


@pytest.mark.parametrize("preview", [True, False])
def test_dfd_geometry_lock_depends_on_preview_or_recording(preview_panel, preview):
    window, controller = preview_panel
    window.ui.checkBox_DFD.setChecked(True)
    controller.preview = preview
    controller._busy(True)
    for axis in "xyz":
        for name in (f"spinBox_range_{axis}", f"spinBox_off_{axis}_um"):
            assert getattr(window.ui, name).isEnabled() == (preview and axis in "xy")
    controller._busy(False)


@pytest.mark.parametrize("channel", ["RGBDFD", "LIFETIME_HSV", "LIFETIME", "QUALITY", "Sum"])
def test_flare_dfd_preview_uses_existing_image_and_trace_controls(preview_panel, channel):
    window, controller = preview_panel
    window.ui.comboBox_plot_channel.setCurrentText(channel)
    window.renderDfdTrace = Mock()
    window.getLifetimeColorRenderMode = lambda _: "hsv"
    window.getLifetimeHueDisplayRange = lambda: (0, 1)
    window.getLifetimeForceQualityFull = lambda: False
    window.ui.doubleSpinBox_delta_tau_ns = SimpleNamespace(value=lambda: 0)
    snapshot = dict(
        image=np.ones((2, 3), dtype=np.uint64), bins=6, total_bins=6,
        receiver_bytes=6 * 5144, expected_bytes=6 * 5144, status={},
        fingerprint=np.zeros(25), trace=None, geometry=window.getGUI_data(),
        hcl_image=np.ones((2, 3, 3)), rgb_image=np.ones((2, 3, 3)),
        dfd_hist_live=np.ones(91), dfd_hist_sum=np.ones(91),
        dfd_bins=91, dfd_laser_hz=40000000, bin_seconds=0.003,
        dfd_live_records=6, dfd_hist_records=6,
    )
    controller.render(snapshot)
    assert window.renderDfdTrace.call_args.args[2:] == (40000000, 91)
    if channel == "LIFETIME_HSV":
        kwargs = window.im_widget.setFlimImage.call_args.kwargs
        assert kwargs["h_display_max"] == 25
        assert kwargs["render_mode"] == "hsv"
    else:
        call = window.im_widget.setImage.call_args
        assert call.args[0].shape == ((3, 2, 3) if channel == "RGBDFD" else (3, 2))
        assert call.kwargs["levelMode"] == ("rgba" if channel == "RGBDFD" else "mono")
