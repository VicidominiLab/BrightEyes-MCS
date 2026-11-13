"""Test classification and safe ordering for Qt on Windows.

PySide widgets must be collected after multiprocessing-heavy tests on the
supported Python 3.13 Windows runtime.  Otherwise Qt finalizers can race with
creation of Windows synchronization primitives and terminate the interpreter.
Real Jupyter console lifetimes also require a dedicated interpreter.
"""

from pathlib import Path

import pytest


@pytest.fixture
def h5_writer():
    """The same dedicated writer service allocated by the acquisition manager."""
    from types import SimpleNamespace
    from brighteyes_mcs.acquisition.storage import AcquisitionStorage

    storage = AcquisitionStorage()
    commands, responses, process = storage.start(None)
    yield SimpleNamespace(process=process, shared_objects={
        "h5_command_queue": commands, "h5_response_queue": responses})
    storage.stop()


@pytest.fixture(autouse=True)
def forbid_flare_activation_in_existing_workflows(request, monkeypatch):
    """The existing suite must pass with Flare acquisition/control unavailable."""
    if Path(str(request.node.fspath)).name.startswith("test_flare"):
        return
    if request.node.get_closest_marker("qt_isolated"):
        # Keep multiprocessing/h5py imports out of the isolated Qt/Jupyter lifetime.
        return
    from brighteyes_mcs.hardware.flare import FlareClient
    from brighteyes_mcs.acquisition.flare import FlareAcquisition

    def unexpected_flare(*args, **kwargs):
        raise AssertionError("Existing detector workflow attempted to activate Flare")

    monkeypatch.setattr(FlareClient, "__init__", unexpected_flare)
    monkeypatch.setattr(FlareAcquisition, "__init__", unexpected_flare)


QT_MODULES = {
    "test_workspace_layout.py",
    "test_flim_image_view.py",
    "test_flare_ui.py",
    "test_action_logging.py",
    "test_pispad23_timetagging.py",
    "test_pispad23_library_gui.py",
    "test_tdc_conversion_gui.py",
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
