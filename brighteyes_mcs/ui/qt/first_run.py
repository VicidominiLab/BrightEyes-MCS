"""First-run Windows shortcut setup dialog."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...application.windows_integration import (
    create_desktop_shortcut,
    mark_setup_handled,
    setup_was_handled,
)


class ShortcutSetupDialog(QDialog):
    """Offer a shortcut without installing or modifying the Python environment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BrightEyes-MCS first-run setup")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        heading = QLabel("BrightEyes-MCS is ready to use.")
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(heading)

        explanation = QLabel(
            "Would you like a Desktop shortcut for this Python environment? "
            "No software or drivers will be installed."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        detail = QLabel(
            "The shortcut launches this environment with "
            "pythonw.exe -m brighteyes_mcs. You can reopen this setup with "
            "python -m brighteyes_mcs --setup."
        )
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(detail)

        buttons = QDialogButtonBox(self)
        self.create_button = QPushButton("Create Desktop shortcut")
        self.skip_button = QPushButton("Skip")
        buttons.addButton(self.create_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.skip_button, QDialogButtonBox.ButtonRole.RejectRole)
        self.create_button.clicked.connect(self._create)
        self.skip_button.clicked.connect(self._skip)
        layout.addWidget(buttons)

    def _create(self) -> None:
        try:
            create_desktop_shortcut()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Could not create shortcut",
                f"BrightEyes-MCS could not create the Desktop shortcut.\n\n{error}",
            )
            return
        mark_setup_handled(desktop=True)
        self.accept()

    def _skip(self) -> None:
        mark_setup_handled(desktop=False)
        self.reject()


def maybe_run_shortcut_setup(parent=None, *, force: bool = False) -> bool:
    """Show setup once for each Windows Python environment."""

    if os.name != "nt":
        return False
    if os.environ.get("BRIGHTEYES_MCS_SKIP_FIRST_RUN") == "1" and not force:
        return False
    if setup_was_handled() and not force:
        return False
    ShortcutSetupDialog(parent).exec()
    return True


__all__ = ["ShortcutSetupDialog", "maybe_run_shortcut_setup"]
