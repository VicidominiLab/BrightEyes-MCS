"""Input breadcrumbs, including plugin controls and plot navigation."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget

from ...logging_setup import ACTION_LEVEL, safe_log, report_logging_failure, verbosity


class UserActionFilter(QObject):
    """Record discrete input before Qt dispatches it; never log mouse moves."""

    def eventFilter(self, watched, event):
        try:
            self._record_event(watched, event)
        except Exception as error:
            report_logging_failure("UI input tracing", error)
        # Logging must never consume an event or prevent Qt from dispatching it.
        return False

    def _record_event(self, watched, event):
        if verbosity() < 2 or not isinstance(watched, QWidget):
            return False
        kind = event.type()
        if kind not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                        QEvent.Type.MouseButtonDblClick, QEvent.Type.Wheel,
                        QEvent.Type.KeyPress, QEvent.Type.Close):
            return False
        name = watched.objectName() or type(watched).__name__
        parent = watched.parentWidget()
        if parent is not None:
            name = f"{parent.objectName() or type(parent).__name__}/{name}"
        detail = ""
        if kind == QEvent.Type.Wheel:
            detail = f"delta={event.angleDelta().toTuple()}"
        elif kind == QEvent.Type.KeyPress:
            # Key codes suffice to diagnose shortcuts; do not capture typed text.
            detail = f"key={event.key()} modifiers={event.modifiers().value}"
        elif kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                      QEvent.Type.MouseButtonDblClick):
            detail = (f"button={event.button().name} pos={event.position().toTuple()} "
                      f"modifiers={event.modifiers().value}")
        safe_log(ACTION_LEVEL, "UI_INPUT event=%s target=%s %s", kind.name, name, detail)
        return False
