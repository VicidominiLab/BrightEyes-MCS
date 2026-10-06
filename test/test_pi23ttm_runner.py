"""Stop a hung recorder without depending on its handlers or Qt event loop."""

import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import pytest

from brighteyes_mcs.hardware import pi23ttm_runner


def launch_bridge():
    options = {"start_new_session": True}
    job = None
    bridge_args = []
    if os.name == "nt":
        from brighteyes_mcs.hardware.pi23ttm_job import RecorderJob

        job = RecorderJob()
        bridge_args = ["--job-name", job.name]
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        options = {"creationflags": subprocess.CREATE_NEW_CONSOLE, "startupinfo": startup}
    process = subprocess.Popen(
        [sys.executable, "-u", str(Path(pi23ttm_runner.__file__).resolve()), *bridge_args,
         sys.executable, "-u", "-c",
         "import signal,time; signal.signal(signal.SIGINT,lambda *args:None); "
         "print('STUB_READY',flush=True); time.sleep(120)"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, **options,
    )
    process.recorder_job = job
    lines = queue.Queue()
    def read():
        for line in process.stdout:
            lines.put(line)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    assert lines.get(timeout=10).strip() == "STUB_READY"
    return process, lines, reader


@pytest.mark.parametrize("eof", [False, True])
def test_bridge_forces_unresponsive_child_after_stop_or_parent_close(eof):
    process, lines, reader = launch_bridge()
    try:
        started = time.monotonic()
        if eof:
            process.stdin.close()
        else:
            process.stdin.write("stop\n")
            process.stdin.flush()
        process.wait(timeout=8)
        reader.join(timeout=2)
        assert time.monotonic() - started < 8
        assert not reader.is_alive()  # No descendant retains the log pipe.
        log = "".join(list(lines.queue))
        assert "forcing termination" in log
    finally:
        if process.poll() is None:
            pi23ttm_runner.stop_watchdog(process, lines)
        process.stdin.close()
        process.stdout.close()
        if process.recorder_job is not None:
            process.recorder_job.close()


def test_watchdog_terminates_launcher_tree_when_stop_pipe_is_unusable(monkeypatch):
    process, lines, reader = launch_bridge()
    try:
        monkeypatch.setattr(pi23ttm_runner, "STOP_WATCHDOG_SECONDS", 0.1)
        # Deliberately send no stop command: exercise the independent fallback.
        pi23ttm_runner.stop_watchdog(process, lines)
        assert not any("termination failed" in line for line in list(lines.queue)), list(lines.queue)
        process.wait(timeout=5)
        reader.join(timeout=2)
        assert not reader.is_alive()
        assert "forcing its process tree" in "".join(list(lines.queue))
    finally:
        if process.poll() is None:
            pi23ttm_runner.stop_watchdog(process, lines)
        process.stdin.close()
        process.stdout.close()
        if process.recorder_job is not None:
            process.recorder_job.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object lifetime")
def test_closing_gui_job_handle_terminates_recorder_and_launcher():
    process, lines, reader = launch_bridge()
    try:
        process.recorder_job.close()
        process.wait(timeout=5)
        reader.join(timeout=2)
        assert not reader.is_alive()
    finally:
        process.recorder_job.close()
        process.stdin.close()
        process.stdout.close()
