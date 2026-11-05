"""Real Windows-spawn IPC tests; simulated device traffic never touches hardware."""

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
import multiprocessing
import os
import queue
import time
import threading
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import pytest

from brighteyes_mcs.acquisition.detectors.flare.config import FlareSettings, configuration_from_gui
from brighteyes_mcs.acquisition.detectors.flare.controls import FlareLiveControls
from brighteyes_mcs.acquisition.flare import FlareAcquisition
from brighteyes_mcs.acquisition.flare_worker import FlareTask, SnapshotPublisher, publish_latest
from test.test_flare import FakeClient


def test_blocked_gui_publisher_does_not_block_acquisition_and_keeps_latest_frame():
    entered, release, produced = threading.Event(), threading.Event(), threading.Event()
    received = []

    def slow_gui(frame):
        if frame == 1:
            entered.set()
            assert release.wait(5)
        received.append(frame)

    publisher = SnapshotPublisher(slow_gui)
    producer = None
    try:
        publisher.publish(1)
        assert entered.wait(2)

        def acquire():
            for frame in range(2, 101):
                publisher.publish(frame)
            produced.set()

        producer = threading.Thread(target=acquire)
        producer.start()
        assert produced.wait(2), "Acquisition waited for GUI IPC"
        assert publisher.mailbox.qsize() == 1
    finally:
        release.set()
        if producer:
            producer.join(2)
        publisher.close(timeout=2)
    assert received == [1, 100]
    assert not publisher.thread.is_alive()


def test_preview_delivery_error_does_not_stop_publishing(caplog):
    received = []

    def callback(frame):
        received.append(frame)
        raise RuntimeError("GUI connection lost")

    publisher = SnapshotPublisher(callback)
    publisher.publish(100)
    publisher.close(timeout=2)
    assert received == [100]
    assert "Flare preview delivery failed" in caplog.text
    assert not publisher.thread.is_alive()


@pytest.mark.parametrize('supported', [True, False])
def test_dfd_mode_switch_writes_reference_and_checks_readback(supported):
    from unittest.mock import Mock
    from brighteyes_mcs.acquisition.detectors.flare.dfd import REFERENCE_FACTOR

    controls = FlareLiveControls()
    client = Mock()
    discovery = {'firmware': {'board_capabilities': 2046 if supported else 1022}}
    client.discover.return_value = discovery
    client.write_register.return_value = {'name': REFERENCE_FACTOR, 'value': 7}
    task = FlareTask('reference_factor', FlareSettings(), controls, {'value': 7})
    with patch('brighteyes_mcs.hardware.flare.FlareClient', return_value=client):
        result = task()
    if supported:
        client.write_register.assert_called_once_with(REFERENCE_FACTOR, 7)
        assert result['result']['value'] == 7
        assert controls.events()[0]['readback'] == 7
    else:
        client.write_register.assert_not_called()
        assert result['result'] is None
    client.command.assert_not_called()
    client.close.assert_called_once_with()


def test_dfd_mode_switch_rejects_incorrect_reference_readback():
    from unittest.mock import Mock

    client = Mock()
    client.discover.return_value = {'firmware': {'board_capabilities': 2046}}
    client.write_register.return_value = {'value': 101}
    task = FlareTask('reference_factor', FlareSettings(), FlareLiveControls(), {'value': 7})
    with patch('brighteyes_mcs.hardware.flare.FlareClient', return_value=client):
        with pytest.raises(RuntimeError, match='readback differs'):
            task()


def simulated_acquisition(task):
    """Install the fake inside the child, rather than relying on forked mocks."""
    config = configuration_from_gui(
        task.arguments["values"], 100000000, task.settings, preview=True,
    )
    device = FakeClient(task.settings, config)
    device.write_register = lambda name, value: {"name": name, "value": value}

    def acquisition(settings, configuration, **kwargs):
        return FlareAcquisition(settings, configuration, client_factory=lambda s: device, **kwargs)

    with (
        patch("brighteyes_mcs.hardware.flare.FlareClient", return_value=device),
        patch("brighteyes_mcs.acquisition.flare.FlareAcquisition", side_effect=acquisition),
    ):
        return os.getpid(), task()


@pytest.mark.parametrize("cancelled", [False, True])
def test_spawned_acquisition_shares_controls_cancellation_and_latest_image(cancelled):
    context = multiprocessing.get_context("spawn")
    with context.Manager() as manager, ProcessPoolExecutor(max_workers=1, mp_context=context) as pool:
        controls = FlareLiveControls(manager)
        controls.request({"laser_1_enable": 1, "axis_start_offset_volts": [0, 0, 0]}, geometry={"range_x": 4})
        snapshots = manager.Queue(maxsize=1)
        cancel = manager.Event()
        if cancelled:
            cancel.set()
        task = FlareTask("acquire", FlareSettings(
            host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0,
        ), controls, dict(
            values=dict(
                projection="xy", preview_channel="Sum", nx=3, ny=2, nframe=1,
                range_x=0, range_y=0, offset_x_um=0, offset_y_um=0,
                nrep=1, timebin_per_pixel=3, time_resolution=1000, spad_channels="25",
                calib_x=1, calib_y=1, dfd_enable=False,
            ),
            preview=True, dummy=True, filename=None, raw_only=False, initial_image=None,
            cancel=cancel, snapshots=snapshots, display=manager.dict(channels=None),
        ))
        pid, result = pool.submit(simulated_acquisition, task).result(timeout=30)
        assert pid != os.getpid()
        assert result["complete"] is not cancelled
        if cancelled:
            assert result["result"] == "cancelled"
            assert "cancelled before configuration" in result["error"]
        else:
            snapshot = snapshots.get_nowait()
            assert snapshot["bins"] == snapshot["total_bins"]
            assert snapshot["geometry"] == {"range_x": 4}
            assert np.all(snapshot["image"] > 0)
            assert not controls.has_pending()
            assert controls.events()[0]["name"] == "laser_1_enable"
            with pytest.raises(queue.Empty):
                snapshots.get_nowait()


def test_display_mailbox_replaces_old_updates():
    mailbox = queue.Queue(maxsize=1)
    for index in range(100):
        publish_latest(mailbox, index)
    assert mailbox.get_nowait() == 99


def test_final_snapshot_racing_completion_is_delivered_before_result():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication
    from brighteyes_mcs.ui.controllers.flare_job import FlareJob

    app = QApplication.instance() or QApplication([])
    parent = QObject()
    mailbox = queue.Queue(maxsize=1)
    received = []
    task = FlareTask("acquire", arguments={"snapshots": mailbox})
    job = FlareJob(task, parent)

    def complete_between_mailbox_read_and_result():
        mailbox.put_nowait({"bins": 6, "total_bins": 6})
        return True

    job.future = SimpleNamespace(
        done=complete_between_mailbox_read_and_result, result=lambda: {"complete": True},
    )
    job.snapshot.connect(lambda value: received.append(("image", value)))
    job.result.connect(lambda value, error: received.append(("result", value)))
    job._poll()
    assert received == [
        ("image", {"bins": 6, "total_bins": 6}), ("result", {"complete": True}),
    ]
    assert app is not None


@dataclass
class ProbeTask:
    crash: bool = False
    arguments: dict = field(default_factory=dict)

    def __call__(self):
        if self.crash:
            os._exit(7)
        time.sleep(0.3)
        return os.getpid()


def crash_while_holding_io_lock(controls):
    with controls.io_lock:
        os._exit(7)


def read_desired_with_io_lock(controls):
    with controls.io_lock:
        return dict(controls._requested)


def test_worker_restart_replaces_lock_left_by_crashed_process(monkeypatch, tmp_path):
    from concurrent.futures.process import BrokenProcessPool
    from brighteyes_mcs.ui.controllers.flare import FlareController

    monkeypatch.setenv("BRIGHTEYES_LOG_DIR", str(tmp_path))
    state = SimpleNamespace(
        _process_pool=None, _ipc_manager=None, _pool_failed=False,
        live_controls=FlareLiveControls(), _log_mailbox=None,
        _log_timer=SimpleNamespace(start=lambda: None),
    )
    state.live_controls.request({"laser_1_enable": 1})
    try:
        FlareController._ensure_processes(state)
        with pytest.raises(BrokenProcessPool):
            state._process_pool.submit(crash_while_holding_io_lock, state.live_controls).result(timeout=20)
        state._pool_failed = True
        FlareController._ensure_processes(state)
        assert state._process_pool.submit(read_desired_with_io_lock, state.live_controls).result(timeout=20) == {
            "laser_1_enable": 1,
        }
    finally:
        if state._process_pool is not None:
            state._process_pool.shutdown(wait=True)
        if state._ipc_manager is not None:
            state._ipc_manager.shutdown()


@pytest.mark.parametrize("crash", [False, True])
def test_qt_keeps_ticking_and_reports_worker_exit(crash):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from brighteyes_mcs.ui.controllers.flare_job import FlareJob

    app = QApplication.instance() or QApplication([])
    parent = QObject()
    results, finished, ticks = [], [], []
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=context) as pool:
        parent._process_pool = pool
        job = FlareJob(ProbeTask(crash), parent)
        job.result.connect(lambda value, error: results.append((value, error)))
        job.finished.connect(lambda: finished.append(True))
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(True))
        timer.start()
        job.start()
        deadline = time.monotonic() + 20
        while not finished and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(10)
        timer.stop()
        assert finished == [True]
        assert len(ticks) >= 2
        assert not job.isRunning()
        value, error = results[0]
        if crash:
            assert value is None
            assert "worker failed" in error
            assert parent._pool_failed
        else:
            assert error is None
            assert value != os.getpid()
