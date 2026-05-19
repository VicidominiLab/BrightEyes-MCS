import atexit
import os
import sys
from pathlib import Path
from time import localtime, strftime, time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Supported values: "stdout", "stderr", "file"
FLAG = "file"
# Supported values: "relative", "full"
PATH_MODE = "full"
SESSION_ENV_VAR = "BRIGHTEYES_PRINT_DEBUG_SESSION"

internal_debug = False
_file_stream = None


def _get_session_timestamp():
    session_timestamp = os.environ.get(SESSION_ENV_VAR)
    if session_timestamp:
        return session_timestamp

    session_timestamp = strftime("%y%m%d-%H%M%S", localtime())
    os.environ[SESSION_ENV_VAR] = session_timestamp
    return session_timestamp


SESSION_TIMESTAMP = _get_session_timestamp()
DEFAULT_LOG_PATH = PROJECT_ROOT / "log" / f"mcs-log-{SESSION_TIMESTAMP}.log"


def set_debug(debug=False):
    global internal_debug
    internal_debug = debug


def _shorten_path(path):
    abs_path = Path(path).resolve()

    if PATH_MODE == "full":
        return str(abs_path)

    if PATH_MODE != "relative":
        raise ValueError(f"Unsupported print_debug PATH_MODE: {PATH_MODE!r}")

    try:
        return abs_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(abs_path)


def _now_str():
    current_time = time()
    return strftime("%H:%M:%S", localtime(current_time)) + f".{int((current_time % 1) * 1e6):06d}"


def _get_output_stream():
    global _file_stream

    if FLAG == "stdout":
        return sys.stdout

    if FLAG == "stderr":
        return sys.stderr

    if FLAG == "file":
        if _file_stream is None or _file_stream.closed:
            DEFAULT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _file_stream = DEFAULT_LOG_PATH.open("a", encoding="utf-8")
        return _file_stream

    raise ValueError(f"Unsupported print_debug FLAG: {FLAG!r}")


def print_debug(*objects, sep=" ", end="\n"):
    if internal_debug:
        return

    frame = sys._getframe(1)
    filename = _shorten_path(frame.f_code.co_filename)
    lineno = frame.f_lineno

    location = f"{filename}:{lineno}:"
    location_padded = f"{location:65}"
    timestamp = _now_str()
    message = sep.join(str(obj) for obj in objects)

    stream = _get_output_stream()

    #stream.write(f"{location_padded}\t{timestamp:15}\t{message}{end}")
    stream.write(f"{location_padded} {timestamp:15}\t{message}{end}")
    stream.flush()


@atexit.register
def _close_output_stream():
    global _file_stream

    if _file_stream is not None and not _file_stream.closed:
        _file_stream.close()
        _file_stream = None
