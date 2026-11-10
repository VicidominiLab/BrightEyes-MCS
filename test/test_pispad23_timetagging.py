"""Recorder lifecycle tests use a fake TCP detector, never microscope hardware."""

from pathlib import Path
import json
import socket
import threading
import time
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

from brighteyes_mcs.ui.qt.main_window_design import Ui_MainWindowDesign
from brighteyes_mcs.ui.qt.pispad23_timetagging import PISPAD23Timetagging, measurement_ms, output_path
from brighteyes_mcs.ui.qt.main_window import MainWindow
from brighteyes_mcs.acquisition.detectors.models import DETECTOR_PISPAD23_TS_UIMG, normalize_detector_model


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
        / "brighteyes_mcs/cfg/plugins_cfg/pispad23_timetagging.cfg"
    )
    settings = json.loads(defaults.read_text(encoding="utf-8"))
    adapter = SimpleNamespace(ui=ui)
    adapter._pispad23_timetagging_bindings = lambda: (
        MainWindow._pispad23_timetagging_bindings(adapter)
    )
    MainWindow._apply_pispad23_timetagging_configuration(adapter, settings)
    yield ui
    window.close()


def wait_for(app, condition, timeout=10):
    deadline = time.monotonic() + timeout
    while not condition():
        app.processEvents()
        assert time.monotonic() < deadline, "Timed out waiting for recorder"
        time.sleep(0.01)




def test_detector_selector_keeps_full_names_without_growing(ui, app):
    combo = ui.comboBox_detector_model
    expected = "TCP/IP - PI SPAD23R (TS mode - uimg)"
    combo.setCurrentText(expected)
    assert combo.currentText() == expected
    assert combo.toolTip() == expected
    width = combo.sizeHint().width()
    combo.addItem("An unusually long detector description " * 10)
    assert combo.sizeHint().width() == width
    combo.resize(160, 30)
    app.processEvents()
    assert combo.fontMetrics().horizontalAdvance(expected) > combo.width()
    assert not combo.grab().isNull()
    assert normalize_detector_model(combo.currentText()) == DETECTOR_PISPAD23_TS_UIMG


@pytest.mark.parametrize("retired", ["TCP/IP - PI SPAD23R (TS mode)", "TCP/IP - PI SPAD23R (TS mode - img)"])
def test_removed_image_mode_is_unavailable_and_loads_disabled(ui, retired):
    assert ui.comboBox_detector_model.findText(retired) == -1
    assert ui.comboBox_detector_model.findText(DETECTOR_PISPAD23_TS_UIMG) >= 0
    window = SimpleNamespace(ui=ui, detectorModelChanged=MagicMock())
    window._current_detector_model = lambda: MainWindow._current_detector_model(window)
    MainWindow._set_detector_model_combo(window, retired)
    assert ui.comboBox_detector_model.currentText() == "Disable"
    window.detectorModelChanged.assert_called_once_with("Disable")


def test_removed_image_stream_argument_is_rejected(ui):
    recorder = PISPAD23Timetagging(ui)
    with pytest.raises(TypeError, match="stream_image"):
        recorder.start("unused.h5", stream_image=True)


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
    ui.doubleSpinBox_pispad23ttm_settle.setValue(0.5)
    ui.doubleSpinBox_pispad23ttm_margin.setValue(2)
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
    ui.doubleSpinBox_pispad23ttm_settle.setValue(0.5)
    ui.doubleSpinBox_pispad23ttm_margin.setValue(10)
    assert measurement_ms(ui, preview=True) == 6400
    ui.doubleSpinBox_pispad23ttm_preview_margin.setValue(1.25)
    assert measurement_ms(ui, preview=True) == 7150
    ui.spinBox_nx.setValue(1)
    ui.spinBox_ny.setValue(1)
    assert measurement_ms(ui, preview=True) == 6751
    ui.spinBox_waitAfterFrame.setValue(0)
    ui.spinBox_waitForLaser.setValue(0)
    ui.doubleSpinBox_pispad23ttm_settle.setValue(0)
    ui.doubleSpinBox_pispad23ttm_preview_margin.setValue(0.001)
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
    assert ui.groupBox_10.isAncestorOf(ui.checkBox_pispad23ttmActivate)
    assert ui.dockWidget_adv2.isAncestorOf(ui.checkBox_noMcsSaveWithTtm)
    assert ui.pushButton_pispad23ttm_force_calibration.text() == "Force Calibration"


def test_timetagging_defaults_are_loaded_from_plugins_cfg(ui):
    config_path = (
        Path(__file__).parents[1]
        / "brighteyes_mcs/cfg/plugins_cfg/pispad23_timetagging.cfg"
    )
    configuration = json.loads(config_path.read_text(encoding="utf-8"))
    window = SimpleNamespace(ui=ui)
    window._pispad23_timetagging_bindings = lambda: (
        MainWindow._pispad23_timetagging_bindings(window)
    )

    MainWindow._apply_pispad23_timetagging_configuration(window, configuration)

    assert ui.lineEdit_pispad23ttm_address.text() == "127.0.0.1:9997"
    assert ui.doubleSpinBox_pispad23ttm_margin.value() == 2.0
    assert ui.doubleSpinBox_pispad23ttm_settle.value() == 0.5
    assert ui.doubleSpinBox_pispad23ttm_preview_margin.value() == 0.5
    assert ui.doubleSpinBox_pispad23ttm_timeout.value() == 120.0
    assert (
        MainWindow._get_pispad23_timetagging_configuration(window)
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
            connection.sendall(b"Fake PISPAD23\n")
            received.append(connection.recv(128))
            connection.sendall(b"calibration complete\n")
        server.close()

    thread = threading.Thread(target=device, daemon=True)
    thread.start()
    ui.lineEdit_pispad23ttm_address.setText(f"127.0.0.1:{server.getsockname()[1]}")
    recorder = PISPAD23Timetagging(ui)
    recorder.force_calibration()
    wait_for(app, lambda: not recorder.calibrating)
    thread.join(timeout=1)
    assert received == [b"T,c,1\n"]
    assert "calibration complete" in ui.plainTextEdit_pispad23ttm_log.toPlainText()
    assert ui.pushButton_pispad23ttm_force_calibration.isEnabled()


def test_force_calibration_is_not_available_while_recording(ui):
    recorder = PISPAD23Timetagging(ui)
    recorder.process = MagicMock()
    recorder.force_calibration()
    recorder.process.assert_not_called()
    assert "Cannot force calibration" in ui.plainTextEdit_pispad23ttm_log.toPlainText()






def test_microimage_preview_displays_worker_buffers_and_fingerprint(ui):
    import numpy as np
    from brighteyes_mcs.acquisition.shared_memory import SharedMemoryRegistry
    from brighteyes_mcs.acquisition.preview import PreviewRepository
    from brighteyes_mcs.acquisition.detectors.pispad23.microimage import MicroimagePreview
    from brighteyes_mcs.acquisition.detectors.pispad23.microimage import MicroimageSnapshot

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
        shared_dict={"pispad23_uimg_status": dict(frame=3, frame_dwells=1, recent_dwells=1,
                                           last_frame_dwells=0, total_dwells=1)},
        getFingerprintSaturation=lambda: repository.get_fingerprint(4))
    window = SimpleNamespace(ui=ui, _current_detector_model=lambda: DETECTOR_PISPAD23_TS_UIMG,
        mcs_manager=manager, im_widget=MagicMock(), autoscale_image=True,
        fingerprint_mask=np.ones((5, 5), dtype=np.uint8), fingerprint_visualization=0,
        draw_fingerprint=MagicMock(), microimage_analysis=MagicMock(),
        currentImage_size=[30, 10, 1], currentImage_pos=[20, 10, 0], currentImage_pixels=[3, 2, 1])
    window.getCurrentPreviewImage = lambda: MainWindow.getCurrentPreviewImage(window, repository.get_preview_image())
    window.isLifetimeColorChannel = lambda ch: False
    ui.checkBox_showPreview.setChecked(True)
    ui.comboBox_plot_channel.setCurrentText("Sum")
    ui.comboBox_view_projection.setCurrentText("xy")
    MainWindow._plot_pispad23_microimage(window)
    args, kwargs = window.im_widget.setImage.call_args
    assert args[0].shape == (3, 2) and args[0][2, 1] == 7
    assert kwargs["scale"] == (10, 5)
    assert window.draw_fingerprint.call_args.args[0][4, 4] > 0
    preview.publish("24")
    ui.comboBox_plot_channel.setCurrentText("24")
    MainWindow._plot_pispad23_microimage(window)
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
    window = SimpleNamespace(ui=ui, _current_detector_model=lambda: DETECTOR_PISPAD23_TS_UIMG,
        mcs_manager=SimpleNamespace(shared_dict={"pispad23_uimg_status": status}))
    monkeypatch.setattr(main_window, "time", SimpleNamespace(monotonic=lambda: 10.0))
    MainWindow._plot_pispad23_microimage(window)
    assert ui.label_preview_delay.text() == "2.000"
    assert "rgb(255,128,128)" in ui.label_preview_delay.styleSheet()
    monkeypatch.setattr(main_window, "time", SimpleNamespace(monotonic=lambda: 10.5))
    MainWindow._plot_pispad23_microimage(window)
    assert ui.label_preview_delay.text() == "2.000"
    assert "rgb(255,128,128)" not in ui.label_preview_delay.styleSheet()
    monkeypatch.setattr(main_window, "time", SimpleNamespace(monotonic=lambda: 11.0))
    status["pending_dwells"] //= 2
    MainWindow._plot_pispad23_microimage(window)
    assert ui.label_preview_delay.text() == "1.000"
    assert "red" not in ui.label_preview_delay.styleSheet()
    window.mcs_manager.shared_dict["pispad23_uimg_status"] = {}
    MainWindow._plot_pispad23_microimage(window)
    assert ui.label_preview_delay.text() == "0.000"
    assert "red" not in ui.label_preview_delay.styleSheet()
