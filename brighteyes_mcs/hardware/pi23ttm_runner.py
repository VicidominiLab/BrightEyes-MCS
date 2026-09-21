"""Console bridge: stop the recorder with Ctrl+C, allowing HDF5 to close.

On Windows this helper owns a hidden console, isolated from the GUI and other
acquisitions. A line on stdin (or parent pipe closure) requests a clean stop.
"""

import os
import signal
import subprocess
import sys
import threading


def main():
    if os.name == "nt":
        import ctypes

        # GUI launchers may inherit the Windows ignore-Ctrl+C attribute.
        # Clear it before spawning so the Rust handler can receive the event.
        ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)
    # Install a Python handler rather than inheritable Windows Ctrl+C-ignore.
    signal.signal(signal.SIGINT, lambda *_: None)
    child = subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL)

    def interrupt():
        sys.stdin.readline()
        if child.poll() is None:
            print("Requesting recorder stop (Ctrl+C)", file=sys.stderr, flush=True)
            if os.name == "nt":
                import ctypes

                if not ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0):
                    print("Could not send Ctrl+C to the recorder", file=sys.stderr, flush=True)
            else:
                child.send_signal(signal.SIGINT)

    threading.Thread(target=interrupt, daemon=True).start()
    return child.wait()


if __name__ == "__main__":
    sys.exit(main())
