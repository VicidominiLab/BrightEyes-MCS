"""Test classification and safe ordering for Qt on Windows.

PySide widgets must be collected after multiprocessing-heavy tests on the
supported Python 3.13 Windows runtime.  Otherwise Qt finalizers can race with
creation of Windows synchronization primitives and terminate the interpreter.
Real Jupyter console lifetimes also require a dedicated interpreter.
"""

from pathlib import Path


QT_MODULES = {
    "test_action_logging.py",
    "test_pi23_timetagging.py",
    "test_h5_metadata_compatibility.py",
    "test_first_run_wizard.py",
    "test_mainwindow.py",
    "test_restapi.py",
    "test_scispinbox.py",
}


def pytest_collection_modifyitems(items):
    def category(item):
        filename = Path(str(item.fspath)).name
        if filename in {"test_channel_delay_skew_plugin.py", "test_console_widget.py"}:
            item.add_marker("qt")
            item.add_marker("qt_isolated")
            return 3
        if filename in QT_MODULES:
            item.add_marker("qt")
            return 2
        if "raw_stream" in filename or "acquisition_loop" in filename:
            item.add_marker("integration")
            return 1
        return 0

    items.sort(key=category)
