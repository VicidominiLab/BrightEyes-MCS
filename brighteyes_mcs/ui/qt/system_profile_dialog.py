"""Editor for the per-user ``current_system`` microscope-profile pointer."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...application.firmware_download import (
    DEFAULT_FIRMWARE_BRANCH,
    FIRMWARE_LICENSE_URL,
    FIRMWARE_REPOSITORY,
    download_firmware,
    firmware_archive_url,
)
from ...application.paths import (
    SystemProfile,
    default_configuration_path,
    default_system_profile,
    generate_system_configuration,
    load_system_profile,
    profile_directory,
    system_root,
    validate_system_profile,
    write_system_profile,
)


class SystemProfileEditor(QWidget):
    """Edit a system profile while retaining environment-variable notation."""

    def __init__(
        self,
        parent=None,
        *,
        profile: SystemProfile | None = None,
        show_management_actions: bool = True,
    ):
        super().__init__(parent)
        self._fields: dict[str, QLineEdit] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        explanation = QLabel(
            "Select the folder containing this microscope's configurations and "
            "resources. Paths accept %NAME%, $NAME, and ${NAME} variables."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        layout.addLayout(form)
        self._add_directory_row(form, "System root", "root", self._browse_root)
        self._add_directory_row(
            form, "Configuration folder", "configuration_dir", self._browse_config_dir
        )
        self._add_file_row(
            form,
            "Default configuration",
            "default_configuration",
            self._browse_default_configuration,
        )
        self._add_directory_row(
            form, "Plug-in configuration folder", "plugins_dir", self._browse_plugins_dir
        )
        self._add_directory_row(form, "Scripts folder", "scripts_dir", self._browse_scripts_dir)
        self._add_directory_row(
            form, "Bitfiles / firmware folder", "bitfiles_dir", self._browse_bitfiles_dir
        )

        note = QLabel(
            "A profile may contain any number of .cfg files. The selected default is "
            "loaded at startup; other files remain available through Load Configuration."
        )
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(note)

        reset = QPushButton("Use per-user defaults")
        reset.clicked.connect(lambda: self.set_profile(default_system_profile()))
        actions = QHBoxLayout()
        actions.addWidget(reset)
        if show_management_actions:
            generate = QPushButton("Create folders and default configuration")
            generate.clicked.connect(self.generate_configuration)
            actions.addWidget(generate)
            firmware = QPushButton("Download firmware…")
            firmware.clicked.connect(self.download_firmware)
            actions.addWidget(firmware)
        actions.addStretch()
        layout.addLayout(actions)
        self.set_profile(load_system_profile() if profile is None else profile)

    def generate_configuration(self) -> None:
        """Create missing folders and packaged configuration files for the form."""

        profile = self.profile()
        if not profile.root or not profile.default_configuration:
            QMessageBox.warning(
                self,
                "Incomplete system profile",
                "System root and default configuration cannot be empty.",
            )
            return
        try:
            copied = generate_system_configuration(profile)
        except OSError as error:
            QMessageBox.critical(self, "Could not create system configuration", str(error))
            return
        root = system_root(profile)
        detail = (
            f"Created {len(copied)} default configuration file(s)."
            if copied
            else "The folders and default configuration files already exist."
        )
        QMessageBox.information(
            self,
            "System configuration ready",
            f"The profile is ready in:\n{root}\n\n{detail}\nExisting files were preserved.",
        )

    def download_firmware(self) -> None:
        """Download a selected BrightEyes-MCSLL branch into this profile."""

        dialog = FirmwareDownloadDialog(self, destination=profile_directory("bitfiles", self.profile()))
        dialog.exec()

    def _add_directory_row(self, form, label, name, callback):
        self._add_browse_row(form, label, name, callback)

    def _add_file_row(self, form, label, name, callback):
        self._add_browse_row(form, label, name, callback)

    def _add_browse_row(self, form, label, name, callback):
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit(container)
        field.setObjectName(f"system_profile_{name}")
        browse = QPushButton("…", container)
        browse.setFixedWidth(34)
        browse.clicked.connect(callback)
        row.addWidget(field)
        row.addWidget(browse)
        form.addRow(label, container)
        self._fields[name] = field

    def profile(self) -> SystemProfile:
        return SystemProfile(
            root=self._fields["root"].text().strip(),
            configuration_dir=self._fields["configuration_dir"].text().strip() or ".",
            default_configuration=self._fields["default_configuration"].text().strip(),
            plugins_dir=self._fields["plugins_dir"].text().strip() or "plugins_cfg",
            scripts_dir=self._fields["scripts_dir"].text().strip() or "scripts",
            bitfiles_dir=self._fields["bitfiles_dir"].text().strip() or "bitfiles",
        )

    def set_profile(self, profile: SystemProfile) -> None:
        for name in self._fields:
            self._fields[name].setText(getattr(profile, name))

    @staticmethod
    def _relative_setting(selected: str, base: Path) -> str:
        path = Path(selected)
        try:
            return os.path.relpath(path, base)
        except (OSError, ValueError):
            return str(path)

    def _select_directory(self, title: str, current: Path, *, base: Path | None = None):
        selected = QFileDialog.getExistingDirectory(self, title, str(current))
        if not selected:
            return None
        return self._relative_setting(selected, base) if base is not None else selected

    def _browse_root(self):
        profile = self.profile()
        selected = self._select_directory("Select microscope system root", system_root(profile))
        if selected:
            self._fields["root"].setText(selected)

    def _browse_config_dir(self):
        profile = self.profile()
        root = system_root(profile)
        selected = self._select_directory(
            "Select configuration folder", profile_directory("configuration", profile), base=root
        )
        if selected:
            self._fields["configuration_dir"].setText(selected)

    def _browse_plugins_dir(self):
        self._browse_profile_directory("Select plug-in configuration folder", "plugins", "plugins_dir")

    def _browse_scripts_dir(self):
        self._browse_profile_directory("Select scripts folder", "scripts", "scripts_dir")

    def _browse_bitfiles_dir(self):
        self._browse_profile_directory("Select bitfiles / firmware folder", "bitfiles", "bitfiles_dir")

    def _browse_profile_directory(self, title: str, kind: str, field: str):
        profile = self.profile()
        root = system_root(profile)
        selected = self._select_directory(title, profile_directory(kind, profile), base=root)
        if selected:
            self._fields[field].setText(selected)

    def _browse_default_configuration(self):
        profile = self.profile()
        config_dir = profile_directory("configuration", profile)
        selected = QFileDialog.getOpenFileName(
            self,
            "Select default configuration",
            str(default_configuration_path(profile)),
            "BrightEyes configuration (*.cfg);;All files (*)",
        )[0]
        if selected:
            self._fields["default_configuration"].setText(
                self._relative_setting(selected, config_dir)
            )


class SystemProfileDialog(QDialog):
    """Validate and save the user's active microscope profile."""

    def __init__(self, parent=None, *, profile: SystemProfile | None = None):
        super().__init__(parent)
        self.setWindowTitle("BrightEyes-MCS system profile")
        self.setMinimumWidth(680)
        layout = QVBoxLayout(self)
        self.editor = SystemProfileEditor(self, profile=profile)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self) -> bool:
        profile = self.editor.profile()
        if not profile.root or not profile.default_configuration:
            QMessageBox.warning(
                self,
                "Incomplete system profile",
                "System root and default configuration cannot be empty.",
            )
            return False
        errors = validate_system_profile(profile)
        if errors:
            QMessageBox.warning(self, "Invalid system profile", "\n".join(errors))
            return False
        try:
            write_system_profile(profile)
        except OSError as error:
            QMessageBox.critical(
                self, "Could not save system profile", str(error)
            )
            return False
        self.accept()
        return True


class _FirmwareDownloadWorker(QObject):
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
        except Exception as error:  # shown to the user in the GUI thread
            self.failed.emit(str(error))
        else:
            self.completed.emit(paths)


class FirmwareDownloadDialog(QDialog):
    """Select, download, and extract a BrightEyes-MCSLL branch."""

    def __init__(
        self,
        parent=None,
        *,
        destination: Path,
        branch: str = DEFAULT_FIRMWARE_BRANCH,
    ):
        super().__init__(parent)
        self.destination = destination
        self._thread: QThread | None = None
        self._worker: _FirmwareDownloadWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._outcome: tuple[str, object] | None = None
        self.setWindowTitle("Download BrightEyes-MCS firmware")
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        description = QLabel(
            f'Download a branch from <a href="{FIRMWARE_REPOSITORY}">BrightEyes-MCSLL</a> '
            "and extract it into the selected system profile. Existing files with the "
            "same names will be updated."
        )
        description.setOpenExternalLinks(True)
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self.branch = QLineEdit(branch, self)
        form.addRow("Repository branch", self.branch)
        destination_field = QLineEdit(str(destination), self)
        destination_field.setReadOnly(True)
        form.addRow("Firmware folder", destination_field)
        layout.addLayout(form)

        license_note = QLabel(
            f'The firmware has a separate closed-source license. Downloading and using it '
            f'signifies agreement to the <a href="{FIRMWARE_LICENSE_URL}">firmware license</a>.'
        )
        license_note.setOpenExternalLinks(True)
        license_note.setWordWrap(True)
        layout.addWidget(license_note)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.download_button = self.buttons.addButton(
            "Download and extract",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.download_button.clicked.connect(self.start_download)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def start_download(self) -> None:
        branch = self.branch.text().strip()
        try:
            firmware_archive_url(branch)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid firmware branch", str(error))
            return
        answer = QMessageBox.question(
            self,
            "Accept firmware license",
            "Downloading and using BrightEyes-MCSLL firmware signifies agreement to its "
            "separate firmware license. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.download_button.setEnabled(False)
        self.branch.setEnabled(False)
        self._outcome = None
        progress = QProgressDialog("Downloading firmware…", "", 0, 0, self)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        self._progress_dialog = progress

        thread = QThread(self)
        worker = _FirmwareDownloadWorker(branch, self.destination)
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
        if self._progress_dialog is None:
            return
        if total > 0:
            self._progress_dialog.setRange(0, total)
            self._progress_dialog.setValue(received)
        else:
            self._progress_dialog.setRange(0, 0)
        self._progress_dialog.setLabelText(
            f"Downloading firmware… {received / (1024 * 1024):.1f} MB"
        )

    @Slot(object)
    def _download_completed(self, paths: list[Path]) -> None:
        self._outcome = ("completed", paths)

    @Slot(str)
    def _download_failed(self, message: str) -> None:
        self._outcome = ("failed", message)

    @Slot()
    def _thread_finished(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        outcome = self._outcome
        self._thread = None
        self._worker = None
        if outcome and outcome[0] == "completed":
            paths = outcome[1]
            QMessageBox.information(
                self,
                "Firmware ready",
                f"Extracted {len(paths)} file(s) into:\n{self.destination}",
            )
            self.accept()
            return
        QMessageBox.critical(
            self,
            "Firmware download failed",
            str(outcome[1]) if outcome else "The firmware download ended unexpectedly.",
        )
        self.download_button.setEnabled(True)
        self.branch.setEnabled(True)

    def reject(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "Download in progress", "Please wait for the download to finish.")
            return
        super().reject()


__all__ = ["FirmwareDownloadDialog", "SystemProfileDialog", "SystemProfileEditor"]
