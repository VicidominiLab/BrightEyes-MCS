"""First-run system profile, firmware, and Windows shortcut wizard."""

from __future__ import annotations

import os
from pathlib import Path

from ... import __version__
from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from ...application.firmware_download import (
    DEFAULT_FIRMWARE_BRANCH,
    FIRMWARE_LICENSE_URL,
    download_firmware,
)
from ...application.paths import (
    SystemProfile,
    default_configuration_path,
    ensure_user_configuration,
    generate_system_configuration,
    profile_directory,
    system_root,
    validate_system_profile,
    write_system_profile,
)
from ...application.windows_integration import (
    create_desktop_shortcuts,
    mark_setup_handled,
    setup_was_handled,
)
from .system_profile_dialog import SystemProfileEditor


class _WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to BrightEyes-MCS")
        self.setSubTitle(
            "Microscope control software for image-scanning microscopy."
        )
        layout = QVBoxLayout(self)
        introduction = QLabel(
            f"<p><b>BrightEyes-MCS {__version__}</b> controls multichannel "
            "image-scanning microscopes and their acquisition hardware.</p>"
            "<p>It is installed in the current Python environment; no application "
            "executable is created.</p>"
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        license_heading = QLabel("<h3>License and warranty</h3>")
        layout.addWidget(license_heading)
        license_notice = QLabel(
            "<p>Copyright © 2023 Istituto Italiano di Tecnologia.</p>"
            "<p>BrightEyes-MCS is free software licensed under the "
            "<b>GNU General Public License, version 3 or later (GPLv3+)</b>. "
            "You may redistribute and/or modify it under those terms.</p>"
            "<p><b>This program comes with ABSOLUTELY NO WARRANTY</b>, including "
            "no implied warranty of merchantability or fitness for a particular "
            "purpose. See the GNU General Public License for details.</p>"
            '<p><a href="https://github.com/VicidominiLab/BrightEyes-MCS/blob/main/LICENSE.md">'
            "Read the full BrightEyes-MCS license</a> &middot; "
            '<a href="https://github.com/VicidominiLab/BrightEyes-MCS">Project source</a></p>'
        )
        license_notice.setWordWrap(True)
        license_notice.setOpenExternalLinks(True)
        license_notice.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        layout.addWidget(license_notice)

        setup_note = QLabel(
            "The next pages configure the microscope profile, folder structure, "
            "optional firmware, and Desktop shortcuts. Run this wizard again with "
            "python -m brighteyes_mcs --setup."
        )
        setup_note.setWordWrap(True)
        setup_note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(setup_note)
        layout.addStretch()


class _ProfilePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Microscope system profile")
        self.setSubTitle(
            "Select a private per-user folder or a shared laboratory folder."
        )
        layout = QVBoxLayout(self)
        self.editor = SystemProfileEditor(
            self,
            show_management_actions=False,
        )
        layout.addWidget(self.editor)

    def validatePage(self) -> bool:
        profile = self.editor.profile()
        if profile.root and profile.default_configuration:
            return True
        QMessageBox.warning(
            self,
            "Incomplete system profile",
            "System root and default configuration cannot be empty.",
        )
        return False


def _profile_structure_paths(profile: SystemProfile) -> list[tuple[str, Path, bool]]:
    """Return expected profile paths and whether each is required at startup."""

    return [
        ("System root", system_root(profile), True),
        ("Configuration folder", profile_directory("configuration", profile), True),
        ("Default configuration", default_configuration_path(profile), True),
        ("Plug-in configuration folder", profile_directory("plugins", profile), False),
        ("Plug-ins folder", profile_directory("plugin_packages", profile), False),
        ("Scripts folder", profile_directory("scripts", profile), False),
        ("Bitfiles / firmware folder", profile_directory("bitfiles", profile), False),
    ]


class _StructurePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Folder and configuration structure")
        self.setSubTitle(
            "The selected profile is inspected before anything is written."
        )
        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.create_missing = QCheckBox(
            "Create missing folders and copy the default configuration files"
        )
        self.create_missing.setChecked(True)
        layout.addWidget(self.create_missing)
        note = QLabel("Existing files are preserved; this option does not overwrite them.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

    def _profile(self) -> SystemProfile:
        return self.wizard().profile_page.editor.profile()

    def _missing(self) -> list[tuple[str, Path, bool]]:
        return [
            item
            for item in _profile_structure_paths(self._profile())
            if not item[1].exists()
        ]

    def initializePage(self) -> None:
        missing = self._missing()
        if missing:
            details = "\n".join(f"• {label}: {path}" for label, path, _ in missing)
            self.status.setText(
                "The selected folder does not yet contain the complete "
                f"BrightEyes-MCS structure:\n\n{details}"
            )
            self.create_missing.setChecked(True)
            self.create_missing.setEnabled(True)
        else:
            self.status.setText(
                f"The selected profile structure is ready:\n{system_root(self._profile())}"
            )
            self.create_missing.setChecked(False)
            self.create_missing.setEnabled(False)

    def validatePage(self) -> bool:
        profile = self._profile()
        missing = self._missing()
        if missing and self.create_missing.isChecked():
            try:
                copied = generate_system_configuration(profile)
            except OSError as error:
                QMessageBox.critical(self, "Could not create profile structure", str(error))
                return False
            self.wizard().created_configuration_files = copied

        errors = validate_system_profile(profile)
        if errors:
            QMessageBox.warning(
                self,
                "Profile structure is required",
                "Create the default structure, or go Back and select an existing "
                "profile.\n\n" + "\n".join(errors),
            )
            return False
        return True


class _FirmwareWorker(QObject):
    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, branch: str, destination: Path):
        super().__init__()
        self.branch = branch
        self.destination = destination

    @Slot()
    def run(self) -> None:
        try:
            paths = download_firmware(
                self.branch,
                self.destination,
                progress=lambda received, total: self.progress.emit(received, total or 0),
            )
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.completed.emit(paths)


class _FirmwarePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("FPGA firmware")
        self.setSubTitle(
            "Firmware is separate from the Python package and has its own license."
        )
        layout = QVBoxLayout(self)
        self.download_checkbox = QCheckBox(
            "Download and extract BrightEyes-MCSLL firmware now"
        )
        self.download_checkbox.setChecked(False)
        layout.addWidget(self.download_checkbox)
        branch_label = QLabel("Repository branch:")
        layout.addWidget(branch_label)
        self.branch = QLineEdit(DEFAULT_FIRMWARE_BRANCH)
        layout.addWidget(self.branch)
        self.branch.setEnabled(False)
        self.license_checkbox = QCheckBox(
            "I have read and accept the separate BrightEyes-MCSLL firmware license"
        )
        self.license_checkbox.setEnabled(False)
        layout.addWidget(self.license_checkbox)
        license_link = QLabel(
            f'<a href="{FIRMWARE_LICENSE_URL}">Open the BrightEyes-MCSLL firmware license</a>'
        )
        license_link.setOpenExternalLinks(True)
        layout.addWidget(license_link)
        note = QLabel(
            "Click Next to download inside this wizard. You can also download firmware "
            "later from System…."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.download_button = QPushButton("Download firmware")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status = QLabel("Firmware download is optional.")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        layout.addStretch()
        self._downloaded_selection: tuple[str, Path] | None = None
        self._thread: QThread | None = None
        self._worker: _FirmwareWorker | None = None
        self._download_succeeded = False
        self._advance_when_complete = False
        self.download_checkbox.toggled.connect(self._download_toggled)
        self.branch.textChanged.connect(self._selection_changed)

    @property
    def is_downloading(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _download_toggled(self, enabled: bool) -> None:
        self.branch.setEnabled(enabled and not self.is_downloading)
        self.license_checkbox.setEnabled(enabled and not self.is_downloading)
        self.download_button.setEnabled(enabled and not self.is_downloading)
        if not enabled:
            self.status.setText("Firmware download is optional.")

    def _selection_changed(self) -> None:
        profile = self.wizard().profile_page.editor.profile()
        destination = profile_directory("bitfiles", profile)
        if self._downloaded_selection != (self.branch.text().strip(), destination):
            self._download_succeeded = False

    def _set_wizard_navigation_enabled(self, enabled: bool) -> None:
        wizard = self.wizard()
        for which in (
            QWizard.WizardButton.BackButton,
            QWizard.WizardButton.NextButton,
            QWizard.WizardButton.CancelButton,
        ):
            wizard.button(which).setEnabled(enabled)

    def start_download(self, *, advance_when_complete: bool = False) -> None:
        if self.is_downloading:
            return
        if not self.download_checkbox.isChecked():
            return
        if not self.license_checkbox.isChecked():
            self.status.setText(
                "Accept the separate BrightEyes-MCSLL firmware license before downloading."
            )
            self.status.setStyleSheet("color: #d89b00;")
            return
        branch = self.branch.text().strip()
        profile = self.wizard().profile_page.editor.profile()
        destination = profile_directory("bitfiles", profile)
        if self._downloaded_selection == (branch, destination) and self._download_succeeded:
            if advance_when_complete:
                QTimer.singleShot(0, self.wizard().next)
            return

        self._advance_when_complete = advance_when_complete
        self._download_succeeded = False
        self.status.setStyleSheet("")
        self.status.setText(f"Downloading branch {branch!r} into:\n{destination}")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.branch.setEnabled(False)
        self.license_checkbox.setEnabled(False)
        self.download_button.setEnabled(False)
        self.download_checkbox.setEnabled(False)
        self._set_wizard_navigation_enabled(False)

        thread = QThread(self)
        worker = _FirmwareWorker(branch, destination)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._update_progress)
        worker.completed.connect(self._download_completed)
        worker.failed.connect(self._download_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(int, int)
    def _update_progress(self, received: int, total: int) -> None:
        if total > 0:
            maximum = min(total, 2_147_483_647)
            self.progress.setRange(0, maximum)
            self.progress.setValue(min(received, maximum))
        else:
            self.progress.setRange(0, 0)
        self.status.setText(f"Downloading firmware… {received / (1024 * 1024):.1f} MB")

    @Slot(object)
    def _download_completed(self, paths: list[Path]) -> None:
        profile = self.wizard().profile_page.editor.profile()
        destination = profile_directory("bitfiles", profile)
        self._downloaded_selection = (self.branch.text().strip(), destination)
        self._download_succeeded = True
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.status.setStyleSheet("color: #3da35d;")
        self.status.setText(f"Firmware ready: extracted {len(paths)} file(s) into:\n{destination}")

    @Slot(str)
    def _download_failed(self, message: str) -> None:
        self._download_succeeded = False
        self.status.setStyleSheet("color: #d9534f;")
        self.status.setText(f"Firmware download failed:\n{message}")

    @Slot()
    def _thread_finished(self) -> None:
        succeeded = self._download_succeeded
        advance = self._advance_when_complete and succeeded
        self._advance_when_complete = False
        self._thread = None
        self._worker = None
        self.download_checkbox.setEnabled(True)
        self.branch.setEnabled(self.download_checkbox.isChecked())
        self.license_checkbox.setEnabled(self.download_checkbox.isChecked())
        self.download_button.setEnabled(self.download_checkbox.isChecked())
        self._set_wizard_navigation_enabled(True)
        if advance:
            QTimer.singleShot(0, self.wizard().next)

    def validatePage(self) -> bool:
        if not self.download_checkbox.isChecked():
            return True
        branch = self.branch.text().strip()
        profile = self.wizard().profile_page.editor.profile()
        destination = profile_directory("bitfiles", profile)
        if self._downloaded_selection == (branch, destination) and self._download_succeeded:
            return True
        self.start_download(advance_when_complete=True)
        return False


class _ShortcutsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Desktop shortcuts")
        self.setSubTitle("Choose the shortcuts to create for this Python environment.")
        layout = QVBoxLayout(self)
        self.application = QCheckBox("BrightEyes-MCS application")
        self.python_prompt = QCheckBox("BrightEyes-MCS Python command prompt")
        self.system_root = QCheckBox("BrightEyes-MCS system folder")
        for checkbox in (self.application, self.python_prompt, self.system_root):
            checkbox.setChecked(os.name == "nt")
            checkbox.setEnabled(os.name == "nt")
            layout.addWidget(checkbox)
        if os.name != "nt":
            note_text = "Desktop shortcut creation is available only on Windows."
        else:
            note_text = (
                "The application uses pythonw.exe; the Python shortcut opens an "
                "activated Command Prompt; the system shortcut opens the selected root."
            )
        note = QLabel(note_text)
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()


class _FinishPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Ready to finish")
        self.setSubTitle("Review the selected profile and actions, then click Finish.")
        layout = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.summary)
        layout.addStretch()

    def initializePage(self) -> None:
        wizard = self.wizard()
        profile = wizard.profile_page.editor.profile()
        choices = []
        if wizard.shortcuts_page.application.isChecked():
            choices.append("application")
        if wizard.shortcuts_page.python_prompt.isChecked():
            choices.append("Python command prompt")
        if wizard.shortcuts_page.system_root.isChecked():
            choices.append("system folder")
        shortcuts = ", ".join(choices) if choices else "none"
        firmware = (
            f"downloaded from branch {wizard.firmware_page.branch.text().strip()}"
            if wizard.firmware_page.download_checkbox.isChecked()
            else "not downloaded"
        )
        self.summary.setText(
            f"System root:\n{system_root(profile)}\n\n"
            f"Default configuration:\n{default_configuration_path(profile)}\n\n"
            f"Plug-ins folder:\n{profile_directory('plugin_packages', profile)}\n\n"
            f"Firmware: {firmware}\nDesktop shortcuts: {shortcuts}"
        )


class ShortcutSetupDialog(QWizard):
    """Windows-style first-run wizard retained under its historical class name."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BrightEyes-MCS setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.setMinimumSize(760, 560)
        self.created_configuration_files: list[Path] = []

        self.welcome_page = _WelcomePage(self)
        self.profile_page = _ProfilePage(self)
        self.structure_page = _StructurePage(self)
        self.firmware_page = _FirmwarePage(self)
        self.shortcuts_page = _ShortcutsPage(self)
        self.finish_page = _FinishPage(self)
        for page in (
            self.welcome_page,
            self.profile_page,
            self.structure_page,
            self.firmware_page,
            self.shortcuts_page,
            self.finish_page,
        ):
            self.addPage(page)

    def accept(self) -> None:
        profile = self.profile_page.editor.profile()
        errors = validate_system_profile(profile)
        if errors:
            QMessageBox.warning(self, "Invalid system profile", "\n".join(errors))
            return
        try:
            write_system_profile(profile)
            create_shortcuts = os.name == "nt" and any(
                (
                    self.shortcuts_page.application.isChecked(),
                    self.shortcuts_page.python_prompt.isChecked(),
                    self.shortcuts_page.system_root.isChecked(),
                )
            )
            if create_shortcuts:
                create_desktop_shortcuts(
                    include_application=self.shortcuts_page.application.isChecked(),
                    include_python_prompt=self.shortcuts_page.python_prompt.isChecked(),
                    include_system_root=self.shortcuts_page.system_root.isChecked(),
                    system_root_path=system_root(profile),
                )
        except Exception as error:
            QMessageBox.critical(self, "Could not finish setup", str(error))
            return

        mark_setup_handled(
            desktop=self.shortcuts_page.application.isChecked(),
            python_prompt=self.shortcuts_page.python_prompt.isChecked(),
            system_root_shortcut=self.shortcuts_page.system_root.isChecked(),
        )
        super().accept()

    def reject(self) -> None:
        if self.firmware_page.is_downloading:
            return
        super().reject()


def maybe_run_shortcut_setup(parent=None, *, force: bool = False) -> bool:
    """Show the setup wizard once for each Python environment."""

    if os.environ.get("BRIGHTEYES_MCS_SKIP_FIRST_RUN") == "1" and not force:
        return False
    if setup_was_handled() and not force:
        return False
    ensure_user_configuration()
    ShortcutSetupDialog(parent).exec()
    return True


maybe_run_first_run_setup = maybe_run_shortcut_setup


__all__ = [
    "ShortcutSetupDialog",
    "maybe_run_first_run_setup",
    "maybe_run_shortcut_setup",
]
