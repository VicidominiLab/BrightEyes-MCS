"""Qt readiness and recording through the public library, using a gated TCP device."""

import multiprocessing as mp
import threading

import h5py
import pytest

from test.test_pispad23_timetagging import app as app, ui as ui, wait_for
from brighteyes_mcs.ui.qt.pispad23_timetagging import PISPAD23Timetagging
from brighteyes_mcs.ui.qt.main_window import MainWindow
from brighteyes_mcs.acquisition.detectors.models import DETECTOR_PISPAD23_TS_UIMG
from brighteyes_mcs.acquisition.detectors.pispad23.library_worker import LibraryMicroimageWorker

pispad = pytest.importorskip("brighteyes_pispad")
simulator = pytest.importorskip("brighteyes_pispad.simulator")


class FailingTeardownWorker(LibraryMicroimageWorker):
    def run(self):
        super().run()
        raise RuntimeError("Simulated failure after file closure")


def configure(ui, addr, format="HDF5"):
    ui.comboBox_pispad23ttm_format.setCurrentText(format)
    ui.lineEdit_pispad23ttm_address.setText(addr)
    ui.lineEdit_pispad23ttm_folder.setText("")
    ui.spinBox_nx.setValue(3)
    ui.spinBox_ny.setValue(2)
    ui.spinBox_nframe.setValue(2)
    ui.spinBox_nrepetition.setValue(1)
    ui.doubleSpinBox_pispad23ttm_settle.setValue(0.02)
    ui.doubleSpinBox_pispad23ttm_timeout.setValue(10)


@pytest.mark.parametrize("mode", ["timestamp", "intensity"])
@pytest.mark.parametrize("format,record", [("RAW", True), ("HDF5", True), ("HDF5", False)])
def test_library_gui_waits_for_armed_then_records_and_finishes(app, ui, tmp_path, format, record, mode, h5_writer):
    gate = threading.Event()
    simulation = simulator.SimulationConfig(width=3, height=2, frames=2, fragment_bytes=7)
    with mp.Manager() as manager, simulator.SimulatedDevice(simulation, acquisition_gate=gate) as device:
        configure(ui, device.addr, format)
        if mode == "intensity":
            ui.doubleSpinBox_pispad23_intensity_dwell.setValue(2000)
        shared = manager.dict(channel="Sum")
        mcs_path = tmp_path / "scan.h5"
        worker = LibraryMicroimageWorker(3, 2, 7, h5_writer.shared_objects, shared, mode=mode, saving=dict(
            filename=str(mcs_path), frames=2, repetitions=1, dwell_seconds=0.001))
        worker.start()
        recorder = PISPAD23Timetagging(ui)
        starts, failures = [], []

        def trigger():
            starts.append((worker.connected.is_set(), worker.statistics()["armed"]))
            gate.set()

        recorder.ready.connect(trigger)
        recorder.failed.connect(failures.append)
        try:
            recorder.start(str(mcs_path), stream_microimage=True, microimage_worker=worker, record=record, mode=mode)
            wait_for(app, lambda: not recorder.active, timeout=20)
            assert starts == [(True, True)]
            assert not failures
            assert shared["pispad23_uimg_status"]["total_dwells"] == 12
            if record and mode == "timestamp":
                assert recorder.path.is_file()
                if format == "RAW":
                    assert recorder.path.read_bytes() == (device.payload if mode == "timestamp" else simulator.simulated_intensity(3, 2, 2))
                else:
                    with h5py.File(recorder.path) as saved:
                        assert saved.attrs["acquisition_status"] == "complete"
            else:
                assert recorder.path is None
                assert list(tmp_path.iterdir()) == [mcs_path]
            with h5py.File(mcs_path) as saved:
                assert saved["pispad23_microimages"].attrs["complete"]
                assert saved["pispad23_microimages"].attrs["dwell_seconds"] == pytest.approx(
                    0.002 if mode == "intensity" else 0.001)
            assert "--stream-image-port" not in ui.plainTextEdit_pispad23ttm_log.toPlainText()
        finally:
            recorder.close()
            worker.stop()
            worker.join(5)
            if worker.is_alive():
                worker.terminate()
                worker.join(2)


def test_library_recording_without_microimage_pipeline(app, ui, tmp_path):
    gate = threading.Event()
    with simulator.SimulatedDevice(acquisition_gate=gate) as device:
        configure(ui, device.addr)
        recorder = PISPAD23Timetagging(ui)
        failures = []
        recorder.failed.connect(failures.append)
        recorder.ready.connect(gate.set)
        try:
            recorder.start(str(tmp_path / "scan.h5"))
            wait_for(app, lambda: not recorder.active, timeout=20)
            assert not failures
            with h5py.File(recorder.path) as saved:
                assert saved.attrs["acquisition_status"] == "complete"
        finally:
            recorder.close()


def test_frozen_qt_loop_triggers_rust_abort_without_gui_callbacks(app, ui, tmp_path):
    with simulator.SimulatedDevice(acquisition_gate=threading.Event()) as device:
        configure(ui, device.addr)
        recorder = PISPAD23Timetagging(ui)
        ready, failures = [], []
        recorder.ready.connect(lambda: ready.append(True))
        recorder.failed.connect(failures.append)
        try:
            recorder.start(str(tmp_path / "unused.h5"), record=False)
            wait_for(app, lambda: bool(ready))
            worker = recorder.library_worker
            # Deliberately block the real Qt timer. The MCS Python worker keeps
            # polling data/status, so only the explicit GUI heartbeat can expire.
            worker.join(timeout=13)
            assert not worker.is_alive()
            status = worker.statistics()
            assert status["abort_sent"] and "heartbeat expired" in status["error"]
            commands = [c for c in device.commands if c.startswith("SB,")]
            assert len(commands) == 2 and commands[0] == commands[1]
            wait_for(app, lambda: not recorder.active)
            assert any("heartbeat expired" in message for message in failures)
        finally:
            recorder.close()


def test_intensity_standard_h5_is_finalized_with_normal_mcs_metadata(app, ui, tmp_path,
                                                                   h5_writer, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from brighteyes_mcs.storage.h5 import H5Manager

    path = tmp_path / "intensity.h5"
    with simulator.SimulatedDevice(simulator.SimulationConfig(width=3, height=2, frames=2)) as device:
        configure(ui, device.addr)
        ui.comboBox_detector_model.setCurrentText("TCP/IP - PI SPAD23R (Intensity)")
        worker = LibraryMicroimageWorker(3, 2, 7, h5_writer.shared_objects, {}, mode="intensity",
            saving=dict(filename=str(path), frames=2, repetitions=1, dwell_seconds=0.001))
        worker.start()
        recorder = PISPAD23Timetagging(ui)
        try:
            recorder.start(str(path), stream_microimage=True, microimage_worker=worker,
                           mode="intensity", record=True)
            wait_for(app, lambda: not recorder.active, timeout=20)
            assert worker.statistics()["state"] == "complete"
            assert recorder.path is None
            assert str(path) in ui.label_pispad23ttm_status.text()
            assert "preview only" not in ui.label_pispad23ttm_status.text()
        finally:
            recorder.close()
            worker.join(5)
            if worker.is_alive():
                worker.terminate()
                worker.join(2)

    # Exercise the real finalizer/metadata writer after the bulk writer closes.
    monkeypatch.setattr(H5Manager, "metadata_add_thumbnail", lambda *args: None)
    ui.checkBox_uttmActivate.setChecked(False)
    ui.lineEdit_comment.setText("Intensity scan")
    configuration = dict(detector_model="PISPAD23", pispad23_channels=25)
    window = SimpleNamespace(
        started_normal=True, _mcs_saving_suppressed=False, ui=ui,
        completed_acquisition_count=0, raw_stream_mode=False,
        mcs_manager=SimpleNamespace(shared_dict=dict(filenameh5=str(path)),
                                    registers_configuration=dict(time_resolution=1000)),
        configurationFPGA_dict=dict(max_pixel=3),
        configurationGUI_dict_beforeStart=configuration,
        getGUI_data=lambda: configuration, _gui_config_for_h5=MainWindow._gui_config_for_h5,
        _make_status_timestamp=lambda: "test", PROGRAM_STATE_ACQUISITION_DONE="done",
        im_widget=SimpleNamespace(imageItem=None),
        currentImage_size=(3, 2), currentImage_pos=(0, 0), currentImage_pixels=(3, 2),
        _publish_filename_to_console=MagicMock(), ttm_remote_is_up=lambda: False,
        plugin_signals=MagicMock())
    window.stop = lambda: setattr(window, "started_normal", False)
    MainWindow.finalizeAcquisition(window)
    assert window.completed_acquisition_count == 1
    assert list(tmp_path.iterdir()) == [path]
    with h5py.File(path) as saved:
        assert saved.attrs["comment"] == "Intensity scan"
        assert saved["configurationGUI"].attrs["detector_model"] == "PISPAD23"
        assert "configurationFPGA" in saved
        assert "configurationSpadFCSmanager" in saved
        assert "configurationGUI_beforeStart" in saved
        assert saved["data"].shape == (1, 2, 2, 3, 1, 25)


@pytest.mark.parametrize("model,suppressed", [("TCP/IP - PI SPAD23R (Intensity)", False),
                                               (DETECTOR_PISPAD23_TS_UIMG, True)])
def test_saved_tdc_checkbox_does_not_suppress_intensity_saving(ui, model, suppressed):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    ui.checkBox_noMcsSaveWithTtm.setChecked(True)
    ui.checkBox_pispad23ttmActivate.setChecked(True)
    ui.checkBox_ttmActivate.setChecked(False)
    ui.checkBox_uttmActivate.setChecked(False)
    window = SimpleNamespace(ui=ui, pispad23_timetagging=SimpleNamespace(active=False),
        _current_detector_model=lambda: model,
        _prepare_fpga_for_acquisition=MagicMock(side_effect=RuntimeError("No FPGA in this test")),
        mcs_manager=SimpleNamespace(is_connected=False),
        _update_fpga_connection_button=MagicMock(), _show_fpga_initialization_error=MagicMock())
    MainWindow.beginAcquisition(window)
    assert window._mcs_saving_suppressed == suppressed


def test_intensity_requires_the_mcs_microimage_pipeline(ui):
    recorder = PISPAD23Timetagging(ui)
    with pytest.raises(ValueError, match="standard MCS microimage pipeline"):
        recorder.start("unused.h5", mode="intensity")
    assert not recorder.active


def test_library_stop_cancels_pending_fpga_trigger_and_closes_file(app, ui, tmp_path):
    gate = threading.Event()
    with simulator.SimulatedDevice(acquisition_gate=gate) as device:
        configure(ui, device.addr)
        ui.doubleSpinBox_pispad23ttm_settle.setValue(5)
        recorder = PISPAD23Timetagging(ui)
        starts = []
        recorder.ready.connect(lambda: starts.append(True))
        try:
            recorder.start(str(tmp_path / "stopped.h5"))
            wait_for(app, lambda: recorder.armed)
            recorder.stop()
            wait_for(app, lambda: not recorder.active)
            assert not starts and not gate.is_set()
            with h5py.File(recorder.path) as saved:
                assert saved.attrs["acquisition_status"] == "interrupted"
        finally:
            recorder.close()


def test_library_format_remains_selectable_in_timestamp_mode(ui):
    from types import SimpleNamespace

    ui.comboBox_detector_model.setCurrentText(DETECTOR_PISPAD23_TS_UIMG)
    ui.comboBox_pispad23ttm_format.setCurrentText("HDF5")
    window = SimpleNamespace(ui=ui, pispad23_timetagging=SimpleNamespace(active=False), started_normal=False, started_preview=False)
    MainWindow._sync_pispad23_ttm_detector(window)
    assert ui.comboBox_pispad23ttm_format.isEnabled()
    assert ui.comboBox_pispad23ttm_format.currentText() == "HDF5"


@pytest.mark.parametrize("model,intensity", [("TCP/IP - PI SPAD23R (Intensity)", True),
                                            (DETECTOR_PISPAD23_TS_UIMG, False)])
def test_shared_panel_selects_mode_controls_and_tdc_recording(ui, model, intensity):
    from types import SimpleNamespace

    ui.comboBox_detector_model.setCurrentText(model)
    ui.checkBox_pispad23ttmActivate.setChecked(True)
    window = SimpleNamespace(ui=ui, pispad23_timetagging=SimpleNamespace(active=False),
                             started_normal=False, started_preview=False)
    MainWindow._sync_pispad23_ttm_detector(window)
    assert ui.checkBox_pispad23ttmActivate.isEnabled() != intensity
    assert ui.comboBox_pispad23ttm_format.isEnabled() != intensity
    assert ui.lineEdit_pispad23ttm_folder.isEnabled() != intensity
    assert ui.spinBox_pispad23_channels.isEnabled() == intensity
    assert ui.checkBox_pispad23_external_frame.isEnabled() == intensity
    assert ui.pushButton_pispad23ttm_force_calibration.isEnabled() != intensity
    assert not ui.checkBox_rawStreamAcquisition.isEnabled()
    assert ui.comboBox_spad_channels.currentText() == "25"
    assert not hasattr(ui, "comboBox_pispad23ttm_backend")
    assert not hasattr(ui, "lineEdit_pispad23_ip_addr")


def test_library_missing_dependency_is_reported_without_legacy_fallback(ui, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "brighteyes_pispad", None)
    recorder = PISPAD23Timetagging(ui)
    with pytest.raises(RuntimeError, match="Install brighteyes-pispad-libs"):
        recorder.start("unused.h5")
    assert not recorder.active


def test_library_without_process_support_requires_an_update(ui, monkeypatch):
    from types import SimpleNamespace
    import sys

    monkeypatch.setitem(sys.modules, "brighteyes_pispad", SimpleNamespace(AcquisitionSession=object))
    recorder = PISPAD23Timetagging(ui)
    with pytest.raises(RuntimeError, match="version 0.3 or newer"):
        recorder.start("unused.h5")
    assert not recorder.active


@pytest.mark.parametrize("mcs_level", [0, 3])
@pytest.mark.parametrize("selected,level", [("Minimal", 1), ("Normal", 2), ("Full", 3)])
def test_protocol_setting_is_independent_of_mcs_logging(app, ui, tmp_path, monkeypatch,
                                                      mcs_level, selected, level):
    monkeypatch.setenv("BRIGHTEYES_LOG_VERBOSITY", str(mcs_level))
    monkeypatch.setenv("BRIGHTEYES_LOG_DIR", str(tmp_path / "logs"))
    with simulator.SimulatedDevice(simulator.SimulationConfig(width=3, height=2, frames=2)) as device:
        configure(ui, device.addr)
        ui.comboBox_pispad23_verbosity.setCurrentText(selected)
        recorder = PISPAD23Timetagging(ui)
        try:
            recorder.start(str(tmp_path / "scan.h5"), record=False)
            assert not ui.comboBox_pispad23_verbosity.isEnabled()
            wait_for(app, lambda: not recorder.active, timeout=20)
            assert ui.comboBox_pispad23_verbosity.isEnabled()
            log = recorder.protocol_log_path.read_text()
            assert "state=complete" in log
            assert ("TX command" in log) == (level >= 2)
            assert ("RX stream offset=" in log) == (level == 3)
            assert str(recorder.protocol_log_path) in ui.plainTextEdit_pispad23ttm_log.toPlainText()
        finally:
            recorder.close()


def test_nonzero_worker_exit_is_reported_even_after_done(app, ui, tmp_path):
    gate = threading.Event()
    with simulator.SimulatedDevice(simulator.SimulationConfig(width=3, height=2),
                                    acquisition_gate=gate) as device:
        configure(ui, device.addr)
        worker = FailingTeardownWorker(3, 2, 7, {}, {})
        worker.start()
        recorder = PISPAD23Timetagging(ui)
        failures = []
        recorder.failed.connect(failures.append)
        recorder.ready.connect(gate.set)
        try:
            recorder.start(str(tmp_path / "failed.h5"), stream_microimage=True,
                           microimage_worker=worker, record=False)
            wait_for(app, lambda: not recorder.active, timeout=20)
            assert worker.done.is_set() and worker.exitcode != 0
            assert any("exited unexpectedly" in message for message in failures)
        finally:
            recorder.close()
            worker.stop()
            worker.join(5)
            if worker.is_alive():
                worker.terminate()
                worker.join(2)


def test_library_preview_repeats_without_recording_or_retriggering(app, ui, tmp_path):
    gate = threading.Event()
    simulation = simulator.SimulationConfig(width=3, height=2, frames=1, start_delay=0.015)
    with mp.Manager() as manager, simulator.SimulatedDevice(simulation, acquisition_gate=gate) as device:
        configure(ui, device.addr)
        shared = manager.dict(channel="Sum")
        worker = LibraryMicroimageWorker(3, 2, 7, {}, shared)
        worker.start()
        recorder = PISPAD23Timetagging(ui)
        starts, failures = [], []

        def trigger():
            starts.append(True)
            gate.set()

        recorder.ready.connect(trigger)
        recorder.failed.connect(failures.append)
        try:
            recorder.start(str(tmp_path / "preview.h5"), stream_microimage=True,
                           microimage_worker=worker, record=False, preview=True)
            wait_for(app, lambda: shared.get("pispad23_uimg_status", {}).get("total_dwells", 0) >= 12)
            assert len([c for c in device.commands if c.startswith("SB,")]) >= 2
            assert starts == [True]
            recorder.stop()
            wait_for(app, lambda: not recorder.active)
            assert not failures and recorder.path is None
            assert not list(tmp_path.iterdir())
        finally:
            recorder.close()
            worker.stop()
            worker.join(5)
            if worker.is_alive():
                worker.terminate()
                worker.join(2)
