import sys
import os
from time import time, strftime, localtime

# Base project folder (strip from filenames)
project_folder = os.sep.join(os.getcwd().split(os.sep)[:-1])
project_prefix = project_folder + os.sep
prefix_len = len(project_prefix)

internal_debug = False

def set_debug(debug=False):
    global internal_debug
    internal_debug = debug

def _shorten_path(path):
    abs_path = os.path.abspath(path)
    if abs_path.startswith(project_prefix):
        return abs_path[prefix_len:]
    return abs_path

def _now_str():
    t = time()
    return strftime("%H:%M:%S", localtime(t)) + f".{int((t % 1)*1e6):06d}"

def print_dec(*objects, sep=" ", end="\n"):
    if internal_debug:
        return

    frame = sys._getframe(1)  # faster than inspect.currentframe()
    filename = _shorten_path(frame.f_code.co_filename)
    lineno = frame.f_lineno

    # Format location
    location = f"{filename}:{lineno}"
    location_padded = f"{location:65}"

    # Timestamp
    timestamp = _now_str()

    # Build message
    msg = sep.join(str(obj) for obj in objects)

    # Direct write (faster than logging.debug)
    sys.stdout.write(f"{location_padded}\t{timestamp:15}\t{msg}{end}")
    sys.stdout.flush()
