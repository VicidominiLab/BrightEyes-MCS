"""Exercise the embedded console with its real in-process kernel."""

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from brighteyes_mcs.ui.qt.console_widget import ConsoleWidget


@pytest.fixture
def console(tmp_path, monkeypatch):
    monkeypatch.setenv("IPYTHONDIR", str(tmp_path / "ipython"))
    app = QApplication.instance() or QApplication([])
    shared = []
    widget = ConsoleWidget(namespace={"shared": shared}, customBanner="MCS test console")
    for _ in range(10):
        app.processEvents()
    yield widget, shared, app
    widget.shutdown_kernel()
    widget.close()
    app.processEvents()


def drain(app):
    for _ in range(10):
        app.processEvents()


def test_namespace_commands_output_and_plotting(console):
    widget, shared, app = console
    assert widget.banner == "MCS test console"
    assert widget.font_size == 16
    widget.push_vars({"increment": 7})
    widget.execute_command("shared.append(increment); print('visible-result')")
    drain(app)
    assert shared == [7]
    assert "visible-result" in widget._control.toPlainText()
    widget.execute_command("shared.append(8); print('hidden-result')", hidden=True)
    drain(app)
    assert shared == [7, 8]
    assert "hidden-result" not in widget._control.toPlainText()
    shell = widget.kernel_manager.kernel.shell
    assert "inline" in shell.user_ns["plt"].get_backend().lower()
    assert shell.user_ns["plt"].rcParams["axes.facecolor"] == "black"
    widget.execute_command("plt.figure(); plt.plot([0, 1]); plt.show()", hidden=True)
    drain(app)


def test_clear_preserves_namespace_and_console_remains_usable(console):
    widget, shared, app = console
    widget.print_text("removable-output\n")
    drain(app)
    assert "removable-output" in widget._control.toPlainText()
    widget.clear()
    drain(app)
    assert "removable-output" not in widget._control.toPlainText()
    widget.execute_command("shared.append('after-clear')")
    drain(app)
    assert shared == ["after-clear"]


def test_script_encoding_errors_and_recovery(console, tmp_path):
    widget, shared, app = console
    script = tmp_path / "analysis.py"
    script.write_bytes(b"# coding: latin-1\nshared.append('caf\xe9')\n")
    widget.run_script(script)
    drain(app)
    assert shared == ["caf\u00e9"]
    script.unlink()  # The reader must have released the file on Windows.
    widget.execute_command("raise ValueError('expected-console-error')")
    drain(app)
    assert "expected-console-error" in widget._control.toPlainText()
    widget.execute_command("shared.append('recovered')")
    drain(app)
    assert shared[-1] == "recovered"


def test_exit_and_repeated_shutdown(console):
    widget, _shared, _app = console
    manager = widget.kernel_manager
    client = widget.kernel_client
    with patch.object(QApplication, "quit") as quit_app:
        widget.exit_requested.emit(widget)
        quit_app.assert_called_once()
    widget.shutdown_kernel()
    assert manager.kernel is None
    assert not client.channels_running


def test_close_stops_kernel(console):
    widget, _shared, _app = console
    manager = widget.kernel_manager
    widget.close()
    assert manager.kernel is None
