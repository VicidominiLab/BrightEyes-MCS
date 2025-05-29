import sys
import os
import logging
import inspect
from datetime import datetime
# Determine root path once
project_folder = os.sep.join(os.getcwd().split(os.sep)[:-1])
internal_debug = False

# Setup logging (you can add a FileHandler here too)
logger = logging.getLogger("debug_logger")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def set_debug(debug=False):
    global internal_debug
    internal_debug = debug

def print_dec(*objects, sep=" ", end="\n"):
    if internal_debug:
        return

    # Use currentframe to avoid full stack inspection
    frame = inspect.currentframe()
    try:
        caller = frame.f_back
        filename = caller.f_globals.get("__file__", "<stdin>")
        filename = os.path.abspath(filename).replace(project_folder+os.sep, "")
        lineno = caller.f_lineno
    finally:
        del frame  # Prevent memory leak

    # Format location
    location = f"{filename}:{lineno}"
    location_padded = f"{location:65}"

    # Timestamp
    timestamp = datetime.now().strftime("%H:%M:%S.%f")

    # Construct the message
    msg = sep.join(str(obj) for obj in objects)
    full_message = f"{location_padded}\t{timestamp:15}\t{msg}"

    # Use logger (non-blocking compared to print)
    logger.debug(full_message)
