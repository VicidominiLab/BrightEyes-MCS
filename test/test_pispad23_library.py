"""Exercise the library inside MCS worker processes, without Qt or hardware."""

import multiprocessing as mp
import threading
import time
from types import SimpleNamespace

import h5py
import numpy as np
import pytest

from brighteyes_mcs.acquisition.detectors.pispad23.library_worker import LibraryMicroimageWorker
from brighteyes_mcs.acquisition.detectors.pispad23.timestamp_pipeline import PISPAD23MicroimagePipeline

pispad = pytest.importorskip("brighteyes_pispad")
simulator = pytest.importorskip("brighteyes_pispad.simulator")
SimulatedDevice, SimulationConfig = simulator.SimulatedDevice, simulator.SimulationConfig
simulated_raw = simulator.simulated_raw


def run_worker(worker, config, timeout=15):
    worker.configure(vars(config))
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        worker.stop()
        worker.join(3)
        if worker.is_alive():
            worker.terminate()
            worker.join(3)
        pytest.fail("library worker did not stop")
    assert worker.done.is_set()
    return worker.statistics()


@pytest.mark.parametrize("mode", ["timestamp", "intensity"])
def test_gui_heartbeat_loss_aborts_even_when_python_worker_keeps_polling(mode):
    with SimulatedDevice(acquisition_gate=threading.Event()) as device:
        worker = LibraryMicroimageWorker(4, 1, 4, mode=mode)
        worker.configure(vars(pispad.AcquisitionConfig(addr=device.addr, mode=mode,
                                width=4, height=1, watchdog_timeout_sec=1)))
        worker.start()
        try:
            deadline = time.monotonic() + 10
            while not worker.connected.is_set():
                assert time.monotonic() < deadline
                worker.keep_alive()
                assert worker.is_alive()
                time.sleep(0.05)
            deadline = time.monotonic() + 1.3
            while time.monotonic() < deadline:
                worker.keep_alive()
                assert worker.is_alive()
                time.sleep(0.05)
            assert worker.connected.is_set()
            worker.join(5)  # Freeze the GUI pulse while the worker still runs.
            assert not worker.is_alive()
            status = worker.statistics()
            assert "heartbeat expired" in status["error"]
            assert status["abort_sent"]
            commands = [c for c in device.commands if c.startswith(("SB,", "CS,"))]
            assert len(commands) == 2 and commands[0] == commands[1]
        finally:
            worker.stop()
            worker.join(2)
            if worker.is_alive():
                worker.terminate()
                worker.join(2)


@pytest.mark.parametrize("mode", ["timestamp", "intensity"])
def test_terminated_mcs_worker_sends_abort_through_native_owner_death_guard(mode):
    with SimulatedDevice(acquisition_gate=threading.Event()) as device:
        worker = LibraryMicroimageWorker(4, 1, 4, mode=mode)
        worker.configure(vars(pispad.AcquisitionConfig(addr=device.addr, mode=mode, width=4, height=1)))
        worker.start()
        try:
            assert worker.connected.wait(10)
            worker.terminate()
            worker.join(3)
            deadline = time.monotonic() + 5
            while len([c for c in device.commands if c.startswith(("SB,", "CS,"))]) < 2:
                assert time.monotonic() < deadline
                time.sleep(0.01)
            commands = [c for c in device.commands if c.startswith(("SB,", "CS,"))]
            assert len(commands) == 2 and commands[0] == commands[1]
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(2)


class FailingPreviewWorker(LibraryMicroimageWorker):
    def _publish_preview(self, preview, status):
        if status.get("runs_started"):
            raise RuntimeError("simulated MCS preview failure")
        super()._publish_preview(preview, status)


@pytest.mark.parametrize("mode", ["timestamp", "intensity"])
def test_mcs_failure_sends_abort(mode):
    with SimulatedDevice(acquisition_gate=threading.Event()) as device:
        worker = FailingPreviewWorker(4, 1, 4, {}, {}, mode=mode)
        status = run_worker(worker, pispad.AcquisitionConfig(addr=device.addr, mode=mode, width=4, height=1))
        assert "simulated MCS preview failure" in status["error"]
        assert status["abort_sent"]
        commands = [c for c in device.commands if c.startswith(("SB,", "CS,"))]
        assert len(commands) == 2 and commands[0] == commands[1]


@pytest.mark.parametrize("format", ["raw", "h5"])
def test_library_worker_saves_timestamps_and_mcs_microimages(tmp_path, format, h5_writer):
    simulation = SimulationConfig(width=3, height=2, frames=2, photons_per_dwell=5,
                                  fragment_bytes=1, empty_every=4)
    timestamps, mcs_path = tmp_path / f"timestamps.{format}", tmp_path / "mcs.h5"
    with mp.Manager() as manager, SimulatedDevice(simulation) as device:
        shared = manager.dict(channel="Sum")
        worker = LibraryMicroimageWorker(3, 2, 3, h5_writer.shared_objects, shared, snake=True, saving=dict(
            filename=str(mcs_path), frames=2, repetitions=1, dwell_seconds=0.001))
        status = run_worker(worker, pispad.AcquisitionConfig(addr=device.addr, output=timestamps,
                                                            format=format))
        assert not status["error"]
        assert status["state"] == "complete"
        assert shared["pispad23_uimg_status"]["total_dwells"] == 12
    with h5py.File(mcs_path) as saved:
        assert saved["data"].shape == (1, 2, 2, 3, 1, 25)
        assert saved["pispad23_microimages"].attrs["complete"]
        assert saved["pispad23_microimages/valid"][:].all()
        for dwell in range(12):
            frame, pixel = divmod(dwell, 6)
            y, x = divmod(pixel, 3)
            x = 2 - x if y % 2 else x
            expected = np.zeros(25, dtype=np.uint32)
            if dwell % 4:
                expected[(dwell + np.arange(5)) % 25] = 1
            np.testing.assert_array_equal(saved["data"][0, frame, y, x, 0], expected)
    if format == "raw":
        assert timestamps.read_bytes() == simulated_raw(simulation)
    else:
        with h5py.File(timestamps) as saved:
            assert saved.attrs["acquisition_status"] == "complete"
            assert saved.attrs["event_count"] == len(simulated_raw(simulation)) // 6


def test_preview_only_creates_no_timestamp_file(tmp_path):
    with SimulatedDevice() as device:
        worker = LibraryMicroimageWorker(8, 4, 7, {}, {})
        status = run_worker(worker, pispad.AcquisitionConfig(addr=device.addr))
        assert status["state"] == "complete" and status["sequence"] == 64
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["disconnect", "overflow"])
def test_library_error_reaches_mcs_and_preserves_recording(tmp_path, failure):
    options = dict(disconnect_after_bytes=38) if failure == "disconnect" else dict(overflow_at_dwell=1)
    with SimulatedDevice(SimulationConfig(**options)) as device:
        worker = LibraryMicroimageWorker(8, 4, 7, {}, {})
        status = run_worker(worker, pispad.AcquisitionConfig(addr=device.addr, output=tmp_path / "failed.h5",
                                                            format="h5"))
        assert status["state"] == "failed" and status["error"]
    with h5py.File(tmp_path / "failed.h5") as saved:
        assert len(saved["event_id"]) >= 6


def test_worker_stops_while_waiting_for_configuration():
    worker = LibraryMicroimageWorker(2, 2, 3)
    worker.start()
    worker.stop()
    worker.join(10)
    try:
        assert not worker.is_alive() and worker.done.is_set()
        assert worker.statistics()["state"] == "interrupted"
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(2)


def test_stop_drains_partial_event_and_marks_mcs_incomplete(tmp_path, h5_writer):
    with SimulatedDevice(SimulationConfig(stall_after_bytes=38)) as device:
        worker = LibraryMicroimageWorker(8, 4, 4, h5_writer.shared_objects, {}, saving=dict(
            filename=str(tmp_path / "mcs.h5"), frames=2, repetitions=1, dwell_seconds=0.001))
        worker.configure(vars(pispad.AcquisitionConfig(addr=device.addr, output=tmp_path / "partial.h5",
                                                       format="h5", flush_ms=20)))
        worker.start()
        try:
            deadline = time.monotonic() + 10
            while worker.statistics().get("events", 0) < 6:
                assert time.monotonic() < deadline
                time.sleep(0.01)
            worker.stop()
            worker.join(10)
            assert not worker.is_alive()
            assert worker.statistics()["state"] == "interrupted"
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(2)
    with h5py.File(tmp_path / "partial.h5") as saved:
        assert saved.attrs["acquisition_status"] == "interrupted"
        assert saved.attrs["trailing_bytes_ignored"] == 2
    with h5py.File(tmp_path / "mcs.h5") as saved:
        assert not saved["pispad23_microimages"].attrs["complete"]


def test_pipeline_uses_only_library_worker():
    acquisition = SimpleNamespace(dim_x=2, dim_y=2, shared_dict={}, shared_objects={})
    assert isinstance(PISPAD23MicroimagePipeline().make_acquisition_loop(acquisition, True),
                      LibraryMicroimageWorker)


@pytest.mark.parametrize("mode", ["timestamp", "intensity"])
def test_mcs_worker_pulls_microimages_from_a_separate_rust_process(mode):
    with SimulatedDevice() as device:
        worker = LibraryMicroimageWorker(8, 4, 7, mode=mode)
        status = run_worker(worker, pispad.AcquisitionConfig(
            addr=device.addr, mode=mode, width=8, height=4, frames=2))
        assert status["state"] == "complete"
        assert status["worker_kind"] == "rust_process"
        assert status["pid"] != worker.pid
        assert status["sequence"] == 64


def test_intensity_uses_standard_mcs_h5_without_a_native_recording(tmp_path, h5_writer):
    path = tmp_path / "scan.h5"
    with SimulatedDevice(SimulationConfig(width=3, height=2, frames=2)) as device:
        worker = LibraryMicroimageWorker(3, 2, 3, h5_writer.shared_objects, {},
            mode="intensity", saving=dict(filename=str(path), frames=2, repetitions=1,
                                           dwell_seconds=0.001))
        status = run_worker(worker, pispad.AcquisitionConfig(
            addr=device.addr, mode="intensity", width=3, height=2, frames=2,
            intensity_dwell_us=2000, output=tmp_path / "native.raw"))
    assert status["state"] == "complete" and status["sequence"] == 12
    assert list(tmp_path.iterdir()) == [path]
    with h5py.File(path) as saved:
        assert saved["data"].shape == (1, 2, 2, 3, 1, 25)
        assert saved["data"].maxshape[0] is None
        assert saved["data"][:].max() > 15
        assert saved["data"].attrs["dwell_seconds"] == 0.002
        assert saved["pispad23_microimages/valid"][:].all()
