from pathlib import Path
from types import SimpleNamespace
import threading

import h5py
from PySide6.QtCore import QTimer

from test.test_pispad23_timetagging import app as app, ui as ui, wait_for
from test.test_tdc_conversion import recording
from brighteyes_mcs.ui.qt import tdc_conversion
from brighteyes_mcs.ui.qt.tdc_conversion import TdcConversionDialog
from brighteyes_mcs.ui.qt.main_window import MainWindow
from brighteyes_mcs.ui.qt.pispad23_timetagging import PISPAD23Timetagging
from brighteyes_mcs.storage.converters.pispad23 import ConversionCancelled, tdc_output_paths
from brighteyes_mcs.storage.tdc_metadata import read_geometry, sidecar_path
from brighteyes_pispad.simulator import SimulatedDevice, SimulationConfig


def test_batch_dialog_converts_multiple_files_and_keeps_failures_visible(app, tmp_path):
    first, _, _, _ = recording(tmp_path, "first-ts.raw")
    second, _, _, _ = recording(tmp_path, "second-ts.raw")
    bad = tmp_path / "truncated.raw"
    bad.write_bytes(b"bad")
    dialog = TdcConversionDialog()
    dialog.add_files([first, second, bad, first])
    assert len(dialog.jobs) == 3
    responsive = []
    QTimer.singleShot(0, lambda: responsive.append(True))
    # TDC-only needs no geometry for the intentionally truncated third file.
    dialog.intensity.setChecked(False)
    try:
        dialog.start_conversion()
        wait_for(app, lambda: dialog.worker is None, timeout=20)
        assert responsive
        assert "2 file(s) converted; 1 failed" in dialog.status.text()
        assert "Saved:" in dialog.table.item(0, 2).text()
        assert "Failed:" in dialog.table.item(2, 2).text()
        for raw in (first, second):
            with h5py.File(tdc_output_paths(raw)["tdc"]) as file:
                assert file.attrs["comment"] == "Sample α"
                assert file.attrs["schema_version"] == 3
            assert not tdc_output_paths(raw)["intensity"].exists()
    finally:
        dialog.close()


def test_batch_dialog_selects_both_outputs(app, tmp_path):
    raw, _, _, _ = recording(tmp_path)
    dialog = TdcConversionDialog()
    dialog.add_files([raw])
    try:
        dialog.start_conversion()
        wait_for(app, lambda: dialog.worker is None, timeout=20)
        assert "1 file(s) converted; 0 failed" in dialog.status.text()
        assert all(p.exists() for p in tdc_output_paths(raw).values())
    finally:
        dialog.close()


def test_close_during_conversion_requests_cancel_and_keeps_worker_alive(app, tmp_path, monkeypatch):
    raw = tmp_path / "cancel.raw"
    raw.touch()
    entered = threading.Event()
    def slow_conversion(*args, cancel_event=None, **kwargs):
        entered.set()
        while not cancel_event.wait(0.01):
            pass
        raise ConversionCancelled()
    monkeypatch.setattr(tdc_conversion, "convert_tdc_raw", slow_conversion)
    dialog = TdcConversionDialog()
    dialog.add_files([raw])
    dialog.show()
    dialog.start_conversion()
    wait_for(app, entered.is_set)
    dialog.close()
    wait_for(app, lambda: dialog.worker is None)
    assert "cancelled" in dialog.status.text()
    assert dialog.isVisible()
    dialog.close()


def test_conversion_button_opens_the_batch_dialog(ui, monkeypatch):
    opened = []
    class Dialog:
        def __init__(self, parent, **kwargs):
            opened.append(kwargs)
        def exec(self):
            opened.append("opened")
    monkeypatch.setattr(tdc_conversion, "TdcConversionDialog", Dialog)
    assert ui.pushButton_pispad23_convert_tdc.text() == "Convert TDC RAW files…"
    MainWindow.cmd_convertTdcRaw(SimpleNamespace(ui=ui))
    assert opened[-1] == "opened"
    assert opened[0]["geometry"].width == ui.spinBox_nx.value()


def test_raw_recording_keeps_metadata_when_no_main_mcs_file_is_saved(app, ui, tmp_path):
    gate = threading.Event()
    simulation = SimulationConfig(width=3, height=2, frames=2)
    with SimulatedDevice(simulation, acquisition_gate=gate) as device:
        ui.lineEdit_pispad23ttm_address.setText(device.addr)
        ui.lineEdit_pispad23ttm_folder.setText(str(tmp_path))
        ui.comboBox_pispad23ttm_format.setCurrentText("RAW")
        ui.spinBox_nx.setValue(3)
        ui.spinBox_ny.setValue(2)
        ui.spinBox_nframe.setValue(2)
        ui.spinBox_nrepetition.setValue(1)
        ui.doubleSpinBox_pispad23ttm_settle.setValue(0)
        recorder = PISPAD23Timetagging(ui)
        recorder.ready.connect(gate.set)
        try:
            recorder.start(str(tmp_path / "no-main.h5"), metadata=dict(comment="TDC only", groups={
                "configurationGUI": dict(nx=3, ny=2), "configurationFPGA": dict(max_pixel=3)}))
            wait_for(app, lambda: not recorder.active, timeout=20)
            assert not (tmp_path / "no-main.h5").exists()
            with h5py.File(sidecar_path(recorder.path)) as file:
                assert file.attrs["comment"] == "TDC only"
                assert file.attrs["acquisition_status"] == "complete"
                assert file["configurationGUI"].attrs["nx"] == 3
            assert read_geometry(sidecar_path(recorder.path)).width == 3
        finally:
            recorder.close()


def test_final_metadata_is_copied_only_to_the_matching_raw_acquisition(ui, tmp_path):
    raw, metadata, _, _ = recording(tmp_path)
    matching, unrelated = tmp_path / "scan.h5", tmp_path / "another.h5"
    for path, comment in ((matching, "Final comment"), (unrelated, "Unrelated scan")):
        with h5py.File(path, "w") as file:
            file.attrs["comment"] = comment
            file.create_group("configurationGUI").attrs["nx"] = 3
    recorder = PISPAD23Timetagging(ui)
    recorder.path = raw
    recorder.metadata_source = matching.resolve()
    recorder.preserve_final_metadata(unrelated)
    with h5py.File(metadata) as file:
        assert file.attrs["comment"] == "Sample α"
    recorder.preserve_final_metadata(matching)
    with h5py.File(metadata) as file:
        assert file.attrs["comment"] == "Final comment"
    assert recorder.metadata_source is None
