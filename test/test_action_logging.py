"""Exercise real Qt delivery so logging cannot change a slot's signature."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal, Slot
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from brighteyes_mcs import logging_setup as logs
from brighteyes_mcs.ui.qt.action_logging import UserActionFilter
from brighteyes_mcs.ui.qt.main_window import MainWindow


@pytest.fixture
def session(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    level = logs.logger.level
    monkeypatch.setenv(logs.VERBOSITY_ENV_VAR, "2")
    monkeypatch.setenv(logs.LOG_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv(logs.SESSION_ENV_VAR, "qt-test")
    path = logs.configure_logging()
    event_filter = UserActionFilter(app)
    app.installEventFilter(event_filter)
    yield app, path
    app.removeEventFilter(event_filter)
    logs.configure_logging(verbosity=0)
    logs.logger.setLevel(level)


def test_button_records_input_and_first_slot_without_changing_signature(session):
    app, path = session
    calls = []

    class Receiver(QObject):
        @logs.trace_action
        def click(self):
            calls.append("clicked")

    receiver = Receiver()
    button = QPushButton("Start")
    button.setObjectName("startButton")
    button.clicked.connect(receiver.click)
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert calls == ["clicked"]
    content = path.read_text()
    assert "UI_INPUT event=MouseButtonPress target=startButton" in content
    assert "first_call=" in content and "Receiver.click source=startButton" in content
    assert content.index("UI_INPUT") < content.index("ACTION_BEGIN") < content.index("ACTION_END")
    button.close()


def test_wheel_navigation_records_delta_and_target(session):
    app, path = session
    plot = QWidget()
    plot.setObjectName("imagePlot")
    event = QWheelEvent(QPointF(12, 15), QPointF(12, 15), QPoint(), QPoint(0, 120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    app.sendEvent(plot, event)
    content = path.read_text()
    assert "UI_INPUT event=Wheel target=imagePlot delta=(0, 120)" in content
    plot.close()


def test_open_log_folder_uses_configured_destination(session, monkeypatch):
    _, path = session
    urls = []
    monkeypatch.setattr("brighteyes_mcs.ui.qt.main_window.QDesktopServices.openUrl",
                        lambda url: urls.append(url.toLocalFile()) or True)
    MainWindow.openLogFolder(SimpleNamespace())
    assert urls == [str(path.parent).replace("\\", "/")]


@pytest.mark.parametrize("level", range(4))
def test_qt_signal_arguments_match_original_slot_arity(session, monkeypatch, level):
    import sys

    monkeypatch.setenv(logs.VERBOSITY_ENV_VAR, str(level))
    calls, errors = [], []
    monkeypatch.setattr(sys, "excepthook", lambda *error: errors.append(error))

    class Receiver(QObject):
        changed = Signal(str)
        range_changed = Signal(object, object)

        @Slot()
        @logs.trace_action
        def plot_settings(self):
            calls.append("settings")
            # Nested signal delivery takes the tracing fast path.
            self.range_changed.emit("view", [[0, 1], [0, 1]])

        @Slot()
        @logs.trace_action
        def axes_range(self, event=None):
            calls.append(("range", event))

        @logs.trace_action
        def all_args(self, *args):
            calls.append(args)

    receiver = Receiver()
    receiver.changed.connect(receiver.plot_settings)
    receiver.range_changed.connect(receiver.axes_range)
    receiver.range_changed.connect(receiver.all_args)
    receiver.changed.emit("10")
    receiver.range_changed.emit("other", "ranges")
    assert errors == []
    assert calls == ["settings", ("range", "view"), ("view", [[0, 1], [0, 1]]),
                     ("range", "other"), ("other", "ranges")]
    with pytest.raises(TypeError):
        receiver.plot_settings("extra argument in a direct Python call")


def test_type_error_inside_slot_is_not_retried(session, monkeypatch):
    import sys

    calls, errors = [], []
    monkeypatch.setattr(sys, "excepthook", lambda *error: errors.append(error))

    class Receiver(QObject):
        changed = Signal(str)

        @logs.trace_action
        def fail(self):
            calls.append("once")
            raise TypeError("failure inside handler")

    receiver = Receiver()
    receiver.changed.connect(receiver.fail)
    receiver.changed.emit("extra signal argument")
    assert calls == ["once"]
    assert len(errors) == 1
    assert str(errors[0][1]) == "failure inside handler"


@pytest.mark.parametrize("level", range(4))
def test_checkable_button_delivers_required_checked_value(session, monkeypatch, level):
    import sys

    monkeypatch.setenv(logs.VERBOSITY_ENV_VAR, str(level))
    calls, errors = [], []
    monkeypatch.setattr(sys, "excepthook", lambda *error: errors.append(error))

    class Receiver(QObject):
        @Slot(bool)
        @logs.trace_action
        def connect_button(self, checked):
            calls.append(checked)

    receiver = Receiver()
    button = QPushButton("Connect")
    button.setCheckable(True)
    button.clicked.connect(receiver.connect_button)
    button.click()
    button.click()
    assert errors == []
    assert calls == [True, False]
    button.close()


def test_broken_input_logger_still_dispatches_button_click(session, monkeypatch):
    import sys

    calls, errors = [], []
    monkeypatch.setattr(sys, "excepthook", lambda *error: errors.append(error))

    def broken(*args):
        raise ValueError("Cannot read input metadata")

    monkeypatch.setattr(UserActionFilter, "_record_event", broken)
    button = QPushButton("Run")
    button.clicked.connect(lambda: calls.append("clicked"))
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert calls == ["clicked"]
    assert errors == []
    button.close()
