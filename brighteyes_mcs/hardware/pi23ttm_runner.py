"""Console bridge with bounded graceful shutdown and forced-stop fallback.

On Windows this helper owns a hidden console, isolated from the GUI and other
acquisitions. A line on stdin (or parent pipe closure) requests a clean stop.
"""

import os
import signal
import subprocess
import sys
import threading


STOP_GRACE_SECONDS = 2.0
STOP_WATCHDOG_SECONDS = 5.0


def report(message):
    try:
        print(message, file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass  # A closed GUI log pipe must not prevent recorder termination.


def stop_child(child):
    if child.poll() is not None:
        return
    report("Requesting recorder stop (Ctrl+C)")
    try:
        if os.name == "nt":
            import ctypes

            if not ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0):
                report("Could not send Ctrl+C to the recorder")
        else:
            child.send_signal(signal.SIGINT)
    except OSError as error:
        report(f"Recorder interrupt failed: {error}")
    try:
        child.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        report("Recorder did not stop within 2 seconds; forcing termination. Output may be incomplete.")
        try:
            child.kill()
        except OSError as error:
            if child.poll() is None:
                report(f"Recorder termination failed: {error}")


def stop_watchdog(process, messages):
    """Target only this launch, independently of Qt timers or a broken stdin pipe."""
    try:
        process.wait(timeout=STOP_WATCHDOG_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    messages.put("Recorder launcher did not stop; forcing its process tree to exit. Output may be incomplete.\n")
    try:
        if os.name == "nt":
            process.recorder_job.terminate()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired) as error:
        messages.put(f"Recorder process-tree termination failed: {error}\n")


def main():
    arguments = sys.argv[1:]
    if os.name == "nt":
        import ctypes

        if arguments[:1] == ["--job-name"]:
            from pi23ttm_job import join_recorder_job

            join_recorder_job(arguments[1])
            arguments = arguments[2:]

        # GUI launchers may inherit the Windows ignore-Ctrl+C attribute.
        # Clear it before spawning so the Rust handler can receive the event.
        ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)
    # Install a Python handler rather than inheritable Windows Ctrl+C-ignore.
    signal.signal(signal.SIGINT, lambda *_: None)
    child = subprocess.Popen(arguments, stdin=subprocess.DEVNULL)

    def interrupt():
        try:
            sys.stdin.readline()
        finally:
            stop_child(child)

    threading.Thread(target=interrupt, daemon=True).start()
    return child.wait()


if __name__ == "__main__":
    sys.exit(main())
