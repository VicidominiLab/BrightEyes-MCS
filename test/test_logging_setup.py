"""Logging levels and propagation across real Windows/spawn process boundaries."""

import logging
import multiprocessing as mp
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from inspect import signature
from time import monotonic

import pytest

from brighteyes_mcs import logging_setup as logs
from brighteyes_mcs.application.bootstrap import _logging_options


@pytest.fixture
def log_session(tmp_path, monkeypatch):
    previous_level = logs.logger.level
    previous_propagate = logs.logger.propagate
    monkeypatch.setenv(logs.LOG_DIR_ENV_VAR, str(tmp_path / "logs"))
    monkeypatch.setenv(logs.SESSION_ENV_VAR, "test-session")
    monkeypatch.setenv(logs.VERBOSITY_ENV_VAR, "2")
    monkeypatch.setattr(logs, "_reported_failures", set())
    yield tmp_path / "logs"
    logs.configure_logging(verbosity=0)
    logs.logger.setLevel(previous_level)
    logs.logger.propagate = previous_propagate


@logs.trace_action
def _action_example(self=None):
    logs.logger.info("normal-message")
    logs.logger.debug("packet-message")


@logs.logged_worker
def _child_messages():
    _action_example()


@logs.logged_worker
def _child_failure():
    raise RuntimeError("PISPAD23 synthetic connection failure")


@logs.logged_worker
def _child_abrupt_exit():
    logs.logger.error("Diagnostic written just before abrupt process exit")
    os._exit(23)


def test_shared_log_survives_abrupt_exit_and_keeps_process_identity(log_session):
    path = logs.configure_logging(verbosity=2)
    process = mp.get_context("spawn").Process(target=_child_abrupt_exit,
                                               name="MicroimageWorker:crash/test")
    process.start()
    process.join(timeout=20)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("Crash probe did not finish")
    assert process.exitcode == 23
    content = path.read_text(encoding="utf-8")
    assert "Diagnostic written just before abrupt process exit" in content
    assert f"pid={process.pid} process=MicroimageWorker:crash/test" in content
    assert "WORKER_EXIT" not in content  # No finally/atexit/clean shutdown ran.
    logs.configure_logging(verbosity=2)
    logs.logger.info("Parent continues after child crash")
    assert path.read_text(encoding="utf-8").startswith(content)
    assert "Parent continues after child crash" in path.read_text(encoding="utf-8")
    assert list(log_session.iterdir()) == [path]


@pytest.mark.parametrize("level", range(4))
def test_levels_and_worker_flags_cannot_override_launcher(level, log_session):
    path = logs.configure_logging(verbosity=level)
    logs.set_debug(True)
    logs.set_debug(False)
    _action_example()
    logs.logger.error("failure-message")
    if level == 0:
        assert path is None
        assert not log_session.exists()
        return
    content = path.read_text(encoding="utf-8")
    assert "normal-message" in content
    assert "failure-message" in content
    assert ("ACTION_BEGIN" in content) == (level >= 2)
    assert ("packet-message" in content) == (level == 3)


@pytest.mark.parametrize("level", range(4))
def test_spawn_inherits_level_session_and_directory(level, log_session):
    path = logs.configure_logging(verbosity=level)
    process = mp.get_context("spawn").Process(target=_child_messages)
    process.start()
    process.join(timeout=20)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("Logging worker did not finish")
    assert process.exitcode == 0
    if level == 0:
        assert not log_session.exists()
        return
    assert list(log_session.iterdir()) == [path]
    content = path.read_text(encoding="utf-8")
    assert "normal-message" in content
    assert ("ACTION_BEGIN" in content) == (level >= 2)
    assert ("packet-message" in content) == (level == 3)
    assert f"pid={process.pid}" in content
    assert f"process={process.name}" in content


def test_worker_failure_keeps_traceback(log_session):
    path = logs.configure_logging(verbosity=2)
    process = mp.get_context("spawn").Process(target=_child_failure)
    process.start()
    process.join(timeout=20)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("Failing worker did not finish")
    assert process.exitcode != 0
    content = path.read_text()
    assert "WORKER_FAILED" in content
    assert "Traceback" in content
    assert "PISPAD23 synthetic connection failure" in content


@logs.logged_worker
def _concurrent_messages(ready):
    assert ready.wait(10)

    def write_records(thread):
        for index in range(30):
            token = f"{os.getpid()}-{thread}-{index}"
            try:
                raise ValueError("failure-" + token)
            except ValueError:
                logs.logger.exception("BEGIN-%s\n%s\nEND-%s", token, "x" * 8192, token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(write_records, range(2)))


def test_processes_and_threads_share_one_file_without_lost_or_interleaved_records(log_session):
    path = logs.configure_logging(verbosity=2)
    context = mp.get_context("spawn")
    ready = context.Event()
    processes = [context.Process(target=_concurrent_messages, args=(ready,)) for _ in range(3)]
    try:
        for process in processes:
            process.start()
        ready.set()
        # The GUI/main process also writes concurrently with the workers.
        for index in range(30):
            logs.logger.info("parent-record-%s", index)
        for process in processes:
            process.join(20)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.kill()
                process.join(5)

    assert list(log_session.iterdir()) == [path]
    content = path.read_text(encoding="utf-8")
    assert content.count("BEGIN-") == 180
    for process in processes:
        assert f"pid={process.pid} process={process.name}" in content
        for thread in range(2):
            for index in range(30):
                token = f"{process.pid}-{thread}-{index}"
                block = f"BEGIN-{token}\n" + "x" * 8192 + f"\nEND-{token}\nTraceback"
                assert content.count(block) == 1
                traceback = content.split(f"END-{token}\n", 1)[1].split(f"ValueError: failure-{token}", 1)[0]
                assert "BEGIN-" not in traceback
                assert "parent-record-" not in traceback
    assert content.count("parent-record-") == 30


@logs.logged_worker
def _hold_log_lock(ready, release):
    handler = next(h for h in logs.logger.handlers if isinstance(h, logs.ResilientFileHandler))
    assert handler._process_lock.acquire()
    try:
        ready.set()
        assert release.wait(20)
    finally:
        handler._process_lock.release()


def test_busy_log_cannot_block_actions_and_killed_owner_does_not_poison_lock(log_session, capsys):
    path = logs.configure_logging(verbosity=2)
    context = mp.get_context("spawn")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_log_lock, args=(ready, release))
    process.start()
    calls = []

    @logs.trace_action
    def action(self=None):
        calls.append("ran")
        return 42

    try:
        assert ready.wait(10)
        start = monotonic()
        assert action() == 42
        assert monotonic() - start < 2
        assert calls == ["ran"]
        assert capsys.readouterr().err.count("shared log busy") == 1
    finally:
        # Kill while holding the lock: no finally block or clean shutdown.
        process.kill()
        process.join(5)
    assert not process.is_alive()
    logs.logger.info("Recovered after lock owner died")
    assert "Recovered after lock owner died" in path.read_text(encoding="utf-8")
    assert list(log_session.iterdir()) == [path]


def test_native_fatal_crash_appends_to_shared_log_and_parent_continues(log_session):
    path = logs.configure_logging(verbosity=2)
    source = """
import faulthandler
import os
from brighteyes_mcs import logging_setup as logs
if os.name == 'nt':
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(3)  # No OS error-report dialog in tests.
logs.configure_logging()
logs.logger.error('Immediately before native crash')
handler = next(h for h in logs.logger.handlers if isinstance(h, logs.ResilientFileHandler))
assert handler._process_lock.acquire()
faulthandler._sigsegv()
"""
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, timeout=20)
    assert result.returncode != 0
    content = path.read_text(encoding="utf-8")
    assert "Immediately before native crash" in content
    assert "Windows fatal exception" in content or "Fatal Python error" in content
    assert '<module>' in content
    logs.logger.info("Parent continues after native crash")
    assert path.read_text(encoding="utf-8").startswith(content)
    assert "Parent continues after native crash" in path.read_text(encoding="utf-8")
    assert list(log_session.iterdir()) == [path]


def test_first_handler_correlates_nested_calls_and_exception(log_session):
    path = logs.configure_logging(verbosity=2)

    @logs.trace_action
    def fail(self=None):
        _action_example()
        raise ValueError("synthetic failure")

    with pytest.raises(ValueError):
        fail()
    content = path.read_text()
    assert content.count("ACTION_BEGIN") == 1
    assert "ACTION_FAILED" in content
    assert "ValueError: synthetic failure" in content
    assert "ACTION_END" not in content
    action_lines = [line for line in content.splitlines() if "action=" in line][1:]
    assert len({line.split("action=")[1].split()[0] for line in action_lines}) == 1
    assert logs._action.get() == "-"


def test_reconfigure_moves_destination_without_duplicate_handlers(log_session, tmp_path):
    first = logs.configure_logging(verbosity=2)
    second = logs.configure_logging(verbosity=3, log_dir=tmp_path / "other")
    logs.logger.info("only-in-second")
    assert "only-in-second" not in first.read_text()
    assert second.read_text().count("only-in-second") == 1
    assert logs.default_log_dir() == second.parent
    logs.configure_logging(verbosity=0)
    assert not any(isinstance(h, logging.FileHandler) for h in logs.logger.handlers)


def test_action_still_runs_when_qt_sender_is_unavailable(log_session):
    path = logs.configure_logging(verbosity=2)

    class ClosingWindow:
        def sender(self):
            raise RuntimeError("Qt object is no longer available")

        @logs.trace_action
        def stop(self):
            return "stopped"

    assert ClosingWindow().stop() == "stopped"
    assert "ACTION_END" in path.read_text()


def test_trace_wrapper_preserves_code_signature_and_default_objects(log_session):
    default = object()

    def original(self, value=default, /, checked=False, *args, required, option=default, **kwargs):
        return value, checked, args, required, option, kwargs

    traced = logs.trace_action(original)
    assert signature(traced, follow_wrapped=False) == signature(original)
    assert traced.__code__.co_argcount == original.__code__.co_argcount
    assert traced.__code__.co_posonlyargcount == original.__code__.co_posonlyargcount
    assert traced.__code__.co_kwonlyargcount == original.__code__.co_kwonlyargcount
    assert traced(None, required="keyword", extra=1) == (
        default, False, (), "keyword", default, {"extra": 1})
    assert traced(None, 42, True, "extra", required=None, option="set") == (
        42, True, ("extra",), None, "set", {})
    with pytest.raises(TypeError):
        traced(None)


def test_launcher_default_aliases_qt_passthrough_and_rejected_levels():
    assert _logging_options(["mcs"]) == (["mcs"], 2)
    for flag in ("--log-level", "--verbosity"):
        assert _logging_options(["mcs", flag, "3", "-platform", "offscreen", "debug"]) == (
            ["mcs", "-platform", "offscreen", "debug"], 3)
        assert _logging_options(["mcs", f"{flag}=0"])[1] == 0
        for invalid in ("-1", "4", "text"):
            with pytest.raises(SystemExit):
                _logging_options(["mcs", flag, invalid])


def test_pispad23_debug_obeys_level_even_with_legacy_environment(log_session, monkeypatch):
    from brighteyes_mcs.acquisition.detectors.pispad23.backend import pispad23_debug, pispad23_debug_enabled

    monkeypatch.setenv("PISPAD23_DEBUG", "1")
    for level in range(4):
        path = logs.configure_logging(verbosity=level)
        assert pispad23_debug_enabled(True) == (level == 3)
        pispad23_debug("PISPAD23 packet detail")
        if path:
            assert ("PISPAD23 packet detail" in path.read_text()) == (level == 3)
    assert os.environ[logs.VERBOSITY_ENV_VAR] == "3"


def test_unwritable_log_folder_does_not_stop_startup_or_worker(log_session, monkeypatch):
    from pathlib import Path

    def denied(*args, **kwargs):
        raise PermissionError("Log directory is read-only")

    monkeypatch.setattr(Path, "mkdir", denied)
    assert logs.configure_logging(verbosity=2) is None
    calls = []

    @logs.logged_worker
    def work():
        calls.append("ran")
        return 42

    assert work() == 42
    assert calls == ["ran"]


def test_native_crash_logging_failure_keeps_regular_file_logging(log_session, monkeypatch):
    def fail(**kwargs):
        raise OSError("Native crash descriptor unavailable")

    monkeypatch.setattr(logs.faulthandler, "enable", fail)
    path = logs.configure_logging(verbosity=2)
    logs.logger.info("still running")
    assert "still running" in path.read_text()
    assert logs._fault_file is None


@pytest.mark.parametrize("failure", ["disk", "formatter", "filter", "record", "lock"])
def test_logging_pipeline_failure_does_not_interrupt_action(log_session, monkeypatch, failure):
    path = logs.configure_logging(verbosity=2)
    handler = next(h for h in logs.logger.handlers if isinstance(h, logs.ResilientFileHandler))

    def broken(*args, **kwargs):
        raise OSError("Simulated diagnostic failure")

    if failure == "disk":
        monkeypatch.setattr(handler.stream, "write", broken)
    elif failure == "lock":
        monkeypatch.setattr(handler._process_lock, "acquire", broken)
    elif failure == "formatter":
        monkeypatch.setattr(handler.formatter, "format", broken)
    elif failure == "filter":
        monkeypatch.setattr(handler.filters[0], "filter", broken)
    else:
        monkeypatch.setattr(logs.logger.logger, "makeRecord", broken)
    calls = []

    @logs.trace_action
    def action(self=None):
        calls.append("ran")
        logs.logger.info("Application code can also write logs")
        return "result"

    assert action() == "result"
    assert calls == ["ran"]
    assert logs._action.get() == "-"
    assert path.exists()


@pytest.mark.parametrize("fail_on", ["ACTION_BEGIN", "ACTION_END", "ACTION_FAILED"])
def test_trace_output_failure_never_retries_action_or_masks_its_error(log_session, monkeypatch, fail_on):
    logs.configure_logging(verbosity=2)
    write = logs.logger.log

    def broken(level, message, *args, **kwargs):
        if message.startswith(fail_on):
            raise OSError("Output failed")
        write(level, message, *args, **kwargs)

    monkeypatch.setattr(logs.logger, "log", broken)
    calls = []
    original_error = ValueError("Real action error")

    @logs.trace_action
    def action(self=None):
        calls.append("ran")
        if fail_on == "ACTION_FAILED":
            raise original_error
        return "result"

    if fail_on == "ACTION_FAILED":
        with pytest.raises(ValueError) as caught:
            action()
        assert caught.value is original_error
    else:
        assert action() == "result"
    assert calls == ["ran"]
    assert logs._action.get() == "-"


def test_bad_metadata_and_wrapper_setup_do_not_prevent_actions(log_session, monkeypatch):
    logs.configure_logging(verbosity=2)

    class Owner:
        def sender(self):
            raise ValueError("Broken sender metadata")

        @logs.trace_action
        def action(self):
            return 42

    assert Owner().action() == 42
    assert logs._action.get() == "-"

    def cannot_wrap(*args):
        raise RuntimeError("Cannot inspect signature")

    monkeypatch.setattr(logs, "_signature_wrapper", cannot_wrap)

    def original(checked):
        return checked

    assert logs.trace_action(original) is original


def test_failure_notice_is_bounded_and_cannot_fail(log_session, monkeypatch, capsys):
    logs.report_logging_failure("test sink", OSError("disk full"))
    logs.report_logging_failure("test sink", OSError("disk full"))
    assert capsys.readouterr().err.count("test sink") == 1

    class BrokenStderr:
        def write(self, text):
            raise OSError("stderr is also broken")

    monkeypatch.setattr(logs.sys, "stderr", BrokenStderr())
    logs.report_logging_failure("other sink", OSError("disk full"))


def test_resilient_logger_keeps_the_actual_call_site(log_session):
    path = logs.configure_logging(verbosity=2)
    logs.logger.info("direct call site")
    logs.safe_log(logging.INFO, "guarded call site")
    lines = [line for line in path.read_text().splitlines() if "call site" in line]
    assert len(lines) == 2
    assert all("test_logging_setup.py:" in line for line in lines)
