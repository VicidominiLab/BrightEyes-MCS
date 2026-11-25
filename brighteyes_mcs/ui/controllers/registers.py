"""Apply register-browser edits through the application's live configuration."""

from copy import deepcopy
from contextlib import contextmanager
import re

import nifpga
import numpy as np
from PySide6.QtWidgets import (
    QAbstractButton, QComboBox, QDoubleSpinBox, QLineEdit, QPlainTextEdit,
    QSpinBox, QTextEdit,
)

from ...application.paths import resolve_legacy_path
from ...hardware.register_names import REGISTER_ALIASES, resolve_register_name


class RegisterEditor:
    def __init__(self, window):
        self.window = window
        self._metadata_key = None
        self._registers = {}
        self._refresh_registers = None

    @contextmanager
    def refresh_snapshot(self):
        """Resolve firmware metadata once for a batch of view updates."""
        self._refresh_registers = self.metadata()
        try:
            yield
        finally:
            self._refresh_registers = None

    def metadata(self):
        """Use the active bitfile when connected, the selected file otherwise."""
        window = self.window
        if window.mcs_manager.is_connected:
            filename = window.mcs_manager.fpga_handle.configuration.get("bitfile", "")
        else:
            filename = window.ui.lineEdit_fpgabitfile.text()
        path = resolve_legacy_path(filename) if filename else None
        key = (str(path), path.stat().st_mtime_ns) if path and path.is_file() else None
        if key != self._metadata_key:
            self._metadata_key = key
            self._registers = {}
            if key is not None:
                try:
                    self._registers = dict(nifpga.Bitfile(str(path)).registers)
                except Exception:
                    # An unavailable bitfile leaves values inspectable, read-only.
                    pass
        return self._registers

    def _locked(self):
        trigger = getattr(self.window, "software_trigger", None)
        flare = getattr(self.window, "flare", None)
        return (trigger is not None and trigger.active) or (
            flare is not None and flare.selected and (
                flare.run_job is not None and flare.run_job.isRunning() or flare._repeat.isActive()
            )
        )

    def access(self, tree, path, value):
        window = self.window
        if self._locked():
            return False, "Acquisition armed"
        if tree is window.ui.treeView_3:
            if len(path) != 1 or path[0] in ("plugins", "offset_x", "offset_y", "offset_z"):
                return False, "Read only"
            entry = window.configuration_helper.get(path[0])
            if entry is None:
                return False, "Read only"
            widget = entry[2]
            supported = isinstance(widget, (QAbstractButton, QComboBox, QSpinBox, QDoubleSpinBox,
                                            QLineEdit, QTextEdit, QPlainTextEdit))
            writable = supported and widget.isEnabled()
            if isinstance(widget, QAbstractButton):
                writable = writable and widget.isCheckable()
            if isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit)):
                writable = writable and not widget.isReadOnly()
            return writable, "GUI control" if writable else "Read only"
        flare = getattr(window, "flare", None)
        if flare is not None and flare.selected:
            return False, "Different backend"
        registers = self.metadata() if self._refresh_registers is None else self._refresh_registers
        name = path[0] if tree is window.ui.treeView else resolve_register_name(path[0], registers)
        register = registers.get(name)
        if register is None:
            return False, "Unknown register"
        if register.is_indicator:
            return False, "Read only (status)"
        if tree is window.ui.treeView and not window.mcs_manager.is_connected:
            return False, "Disconnected"
        return True, "Live FPGA" if window.mcs_manager.is_connected else "Staged FPGA"

    @staticmethod
    def _replace(value, path, replacement):
        if not path:
            return replacement
        result = list(value) if isinstance(value, tuple) else deepcopy(value)
        result[path[0]] = RegisterEditor._replace(result[path[0]], path[1:], replacement)
        return tuple(result) if isinstance(value, tuple) else result

    @staticmethod
    def _validate_register(register, value):
        # NI's ctypes conversions can wrap overflowing integers without an error.
        integer = re.fullmatch(r"([UI])(8|16|32|64)", str(register.datatype))
        if integer:
            signed, bits = integer.group(1) == "I", int(integer.group(2))
            lower = -(1 << (bits - 1)) if signed else 0
            upper = (1 << (bits - int(signed))) - 1
            values = value if isinstance(value, (list, tuple, np.ndarray)) else (value,)
            if any(not lower <= element <= upper for element in values):
                raise ValueError(f"{register.datatype} requires a value between {lower} and {upper}.")

    def write(self, tree, path, value):
        window = self.window
        writable, reason = self.access(tree, path, value)
        if not writable:
            raise ValueError(reason)
        if tree is window.ui.treeView_3:
            accepted = self._write_gui(path[0], value)
            window.configurationGUI_dict.update(window.getGUI_data())
            return accepted

        registers = self.metadata()
        name = path[0] if tree is window.ui.treeView else resolve_register_name(path[0], registers)
        register = registers[name]
        self._validate_register(register, value)
        source = window._status_tree_source(tree)[1]
        updated = self._replace(source[path[0]], path[1:], value)
        self._validate_register(register, updated)
        if tree is window.ui.treeView:
            # This tab displays native FPGA units; avoid detector dimension scaling.
            handle = window.mcs_manager.fpga_handle
            handle.register_write_checked(path[0], updated)
            source[path[0]] = updated
        else:
            # The manager handles detector-specific dimension conversions.
            window.mcs_manager.setRegistersDict({path[0]: updated})
            settings = window.mcs_manager.get_registers_configuration()
            updated = settings[REGISTER_ALIASES.get(path[0], path[0])]
            window.configurationFPGA_dict[path[0]] = updated
            for key in path[1:]:
                updated = updated[key]
            return updated
        return value

    def _write_gui(self, name, value):
        window = self.window
        widget = window.configuration_helper[name][2]
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            if not widget.minimum() <= value <= widget.maximum():
                raise ValueError(f"Enter a value between {widget.minimum()} and {widget.maximum()}.")
            widget.setValue(value)
            return widget.value()
        if isinstance(widget, QComboBox):
            index = widget.findText(value)
            if index < 0 and not widget.isEditable():
                raise ValueError("Choose one of: " + ", ".join(widget.itemText(i) for i in range(widget.count())))
            widget.setCurrentText(value)
            return widget.currentText()
        if isinstance(widget, QAbstractButton):
            if widget.isChecked() != value:
                # Some existing controls apply hardware changes on clicked(),
                # others on toggled()/stateChanged(). A click covers both.
                widget.click()
            return widget.isChecked()
        if isinstance(widget, QLineEdit):
            widget.setText(value)
            widget.editingFinished.emit()
            return widget.text()
        widget.setPlainText(value)
        return widget.toPlainText()
