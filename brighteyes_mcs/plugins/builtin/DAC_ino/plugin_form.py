"""Qt controls and USB converter identification for the DAC tab."""

from PySide6.QtCore import QDateTime
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .controller import DACController, voltage_to_code


DEFAULT_SERIAL_NUMBER = "3C8427C3B50C"


class myForm:
    def setupUi(self, Form):
        self._configuration_window = None
        self._loading_configuration = False
        self.controller = DACController(Form)
        self._run_channels = None
        self._applying_idle = False
        layout = QVBoxLayout(Form)
        connection = QGroupBox("USB-to-TTL connection (9600 baud)", Form)
        grid = QGridLayout(connection)
        self.ports = QComboBox(connection)
        self.refresh = QPushButton("Refresh ports", connection)
        self.serial_number = QLineEdit(connection)
        self.serial_number.setPlaceholderText("USB converter S/N from driver (optional)")
        self.serial_number.setText(DEFAULT_SERIAL_NUMBER)
        self.serial_number.setToolTip(
            "Matches the USB-to-TTL converter serial number reported by the driver. "
            "Leave empty to select a port manually."
        )
        self.connect_button = QPushButton("Connect", connection)
        self.auto_connect_button = QPushButton("Auto-connect by S/N", connection)
        self.reset_serial_button = QPushButton("Reset serial link", connection)
        self.reset_serial_button.setToolTip(
            "Cancel the pending command, reopen the port, clear partial serial data, "
            "and repeat PING / GET. Reopening may reset the Arduino and zero outputs."
        )
        grid.addWidget(QLabel("Serial port"), 0, 0)
        grid.addWidget(self.ports, 0, 1)
        grid.addWidget(self.refresh, 0, 2)
        grid.addWidget(QLabel("Converter S/N"), 1, 0)
        grid.addWidget(self.serial_number, 1, 1, 1, 2)
        grid.addWidget(self.connect_button, 2, 2)
        grid.addWidget(self.auto_connect_button, 2, 1)
        grid.addWidget(self.reset_serial_button, 3, 1, 1, 2)
        self.auto_connect = QCheckBox("Auto-connect", connection)
        self.auto_connect.setToolTip("Connect after applying the DAC configuration, including when the plug-in loads.")
        self.save_configuration = QPushButton("Save configuration", connection)
        grid.addWidget(self.auto_connect, 4, 1)
        grid.addWidget(self.save_configuration, 4, 2)
        layout.addWidget(connection)

        outputs = QGroupBox("DAC outputs — 0 to 5 V", Form)
        output_grid = QGridLayout(outputs)
        self.voltages, self.applied = [], []
        self.run_enabled, self.run_voltages = [], []
        for column, title in enumerate((
            "Channel", "Idle voltage", "Enable", "Preview / Acquisition voltage", "Confirmed voltage",
        )):
            output_grid.addWidget(QLabel(title), 0, column)
        for channel in range(4):
            voltage = QDoubleSpinBox(outputs)
            voltage.setRange(0, 5)
            voltage.setDecimals(3)
            voltage.setSingleStep(0.01)
            voltage.setSuffix(" V")
            voltage.setKeyboardTracking(False)
            voltage.setToolTip("Applied when editing finishes; restored after a run if enabled.")
            voltage.editingFinished.connect(lambda ch=channel: self._set_voltage(ch))
            applied = QLabel("Unknown", outputs)
            self.voltages.append(voltage)
            self.applied.append(applied)
            output_grid.addWidget(QLabel(f"DAC {channel}"), channel + 1, 0)
            output_grid.addWidget(voltage, channel + 1, 1)
            output_grid.addWidget(applied, channel + 1, 4)
            enabled = QCheckBox(outputs)
            enabled.setToolTip("Use the Preview / Acquisition voltage during a run, then restore idle voltage.")
            run_voltage = QDoubleSpinBox(outputs)
            run_voltage.setRange(0, 5)
            run_voltage.setDecimals(3)
            run_voltage.setSingleStep(0.01)
            run_voltage.setSuffix(" V")
            run_voltage.setValue(5)
            self.run_enabled.append(enabled)
            self.run_voltages.append(run_voltage)
            output_grid.addWidget(enabled, channel + 1, 2)
            output_grid.addWidget(run_voltage, channel + 1, 3)
        layout.addWidget(outputs)
        note = QLabel(
            "Idle voltage applies when you finish editing (Enter or leave the field). "
            "Enable a channel to use its Preview / Acquisition voltage during a run "
            "and restore its idle voltage afterward. Connect the DAC before starting.\n"
            "Confirmed voltage is calculated from DAC codes, not measured. "
            "Opening the port may reset the Arduino and zero its outputs.", Form
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.status = QLabel("Disconnected", Form)
        self.status.setWordWrap(True)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status)
        layout.addLayout(status_row)
        debug_group = QGroupBox("Debug output", Form)
        debug_layout = QVBoxLayout(debug_group)
        self.debug_output = QPlainTextEdit(debug_group)
        self.debug_output.setReadOnly(True)
        self.debug_output.setMaximumBlockCount(1000)
        self.debug_output.setMinimumHeight(120)
        self.debug_output.setPlaceholderText("Serial commands, replies, and connection events")
        self.clear_debug = QPushButton("Clear log", debug_group)
        self.clear_debug.clicked.connect(self.debug_output.clear)
        debug_layout.addWidget(self.debug_output)
        debug_layout.addWidget(self.clear_debug)
        layout.addWidget(debug_group, 1)

        self.refresh.clicked.connect(self.refresh_ports)
        self.serial_number.editingFinished.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self._toggle_connection)
        self.auto_connect_button.clicked.connect(self._auto_connect)
        self.reset_serial_button.clicked.connect(self._reset_serial_link)
        self.save_configuration.clicked.connect(self._save_configuration)
        self.serial_number.editingFinished.connect(self._store_configuration)
        self.ports.currentIndexChanged.connect(self._store_configuration)
        self.auto_connect.toggled.connect(self._store_configuration)
        for control in self.run_enabled:
            control.toggled.connect(self._store_configuration)
        for control in self.run_voltages:
            control.valueChanged.connect(self._store_configuration)
        for control in self.voltages:
            control.editingFinished.connect(self._store_configuration)
        self.controller.message.connect(self.status.setText)
        self.controller.debug.connect(self._debug)
        self.controller.state_changed.connect(self._update_state)
        self.controller.acknowledged.connect(self._acknowledged)
        self.controller.readback.connect(self._acknowledged)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.controller.disconnect_port)
        self.refresh_ports()
        self._update_state()

    def refresh_ports(self):
        previous = self.ports.currentData()
        target = self.serial_number.text().strip()
        self.ports.clear()
        matches = []
        for port in sorted(QSerialPortInfo.availablePorts(), key=lambda p: p.portName()):
            serial = port.serialNumber()
            self.ports.addItem(
                f"{port.portName()} — {port.description()} — S/N: {serial or 'unavailable'}",
                port.portName(),
            )
            self._debug(
                f"PORT {port.portName()} | {port.description()} | "
                f"converter S/N: {serial or 'unavailable'}"
            )
            if target and serial == target:
                matches.append(self.ports.count() - 1)
        if target:
            self.ports.setCurrentIndex(matches[0] if len(matches) == 1 else -1)
            if len(matches) != 1:
                self.status.setText("Converter S/N not found or not unique; check S/N and refresh.")
            self._debug(f"S/N {target!r}: {len(matches)} matching port(s)")
        elif previous:
            index = self.ports.findData(previous)
            if index >= 0:
                self.ports.setCurrentIndex(index)
        self._update_state()

    def bind_configuration(self, window):
        self._configuration_window = window
        self.apply_configuration()

    def apply_configuration(self):
        if self._run_channels is not None or self._applying_idle:
            self.status.setText("Stop the run before applying DAC configuration.")
            return
        window = self._configuration_window
        configuration = window.plugin_configuration.get("DAC_ino", {})
        idle = configuration.get("idle_voltages", [0] * 4)
        run = configuration.get("run_voltages", [5] * 4)
        enabled = configuration.get("enabled", [False] * 4)
        if any(len(values) != 4 for values in (idle, run, enabled)):
            raise ValueError("DAC configuration must contain four channels")
        for value in (*idle, *run):
            voltage_to_code(value)
        self._loading_configuration = True
        try:
            self.serial_number.setText(str(configuration.get("serial_number", DEFAULT_SERIAL_NUMBER)))
            self.auto_connect.setChecked(configuration.get("auto_connect", False) is True)
            for ch in range(4):
                self.voltages[ch].setValue(float(idle[ch]))
                self.run_voltages[ch].setValue(float(run[ch]))
                self.run_enabled[ch].setChecked(enabled[ch] is True)
            self.refresh_ports()
            port = self.ports.findData(configuration.get("port", ""))
            if not self.serial_number.text().strip() and port >= 0:
                self.ports.setCurrentIndex(port)
        finally:
            self._loading_configuration = False
        self._store_configuration()
        # Never toggle an existing connection off when a CFG is reloaded.
        if self.auto_connect.isChecked() and not self.controller.port.isOpen():
            name = self.ports.currentData()
            if name:
                self.controller.connect_port(name)
            else:
                self.status.setText("Auto-connect: converter not found; check S/N or select a port.")

    def _store_configuration(self, *_):
        if self._configuration_window is None or self._loading_configuration:
            return
        configuration = self._configuration_window.plugin_configuration.setdefault("DAC_ino", {})
        configuration.update(
            serial_number=self.serial_number.text().strip(),
            port=self.ports.currentData() or "",
            auto_connect=self.auto_connect.isChecked(),
            idle_voltages=[voltage.value() for voltage in self.voltages],
            run_voltages=[voltage.value() for voltage in self.run_voltages],
            enabled=[enabled.isChecked() for enabled in self.run_enabled],
        )

    def _save_configuration(self):
        if self._configuration_window is not None:
            self._store_configuration()
            self._configuration_window.SavePluginConfiguration("DAC_ino")

    def _debug(self, text):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
        self.debug_output.appendPlainText(f"[{timestamp}] {text}")

    def _toggle_connection(self):
        if self.controller.port.isOpen():
            self.controller.disconnect_port()
            self.status.setText("Disconnected")
        else:
            # Re-enumerate just before opening so a remembered S/N follows COM changes.
            self.refresh_ports()
            name = self.ports.currentData()
            if name:
                self.controller.connect_port(name)

    def _auto_connect(self):
        if not self.serial_number.text().strip():
            self.serial_number.setText(DEFAULT_SERIAL_NUMBER)
        self._toggle_connection()

    def _reset_serial_link(self):
        self.controller.disconnect_port()
        self.refresh_ports()
        name = self.ports.currentData()
        if name:
            self.controller.reset_serial_link(name)
        else:
            self.status.setText("Cannot reset: converter not found. Check its connection and S/N.")
            self._debug(self.status.text())

    def _set_voltage(self, channel):
        if self._applying_idle or not self.voltages[channel].isEnabled():
            return
        self._applying_idle = True
        self._update_state()
        try:
            self.controller.set_voltage_confirmed(channel, self.voltages[channel].value())
        except (RuntimeError, ValueError) as error:
            self.controller.message.emit(str(error))
        finally:
            self._applying_idle = False
            self._update_state()

    def _acknowledged(self, channel, code):
        self.applied[channel].setText(f"{code * 5 / 4095:.3f} V (code {code})")

    def before_run(self, mode):
        self._run_channels = [
            (ch, voltage.value(), self.voltages[ch].value()) for ch, (enabled, voltage) in
            enumerate(zip(self.run_enabled, self.run_voltages, strict=True)) if enabled.isChecked()
        ]
        self._update_state()
        for channel, voltage, _ in self._run_channels:
            self.controller.set_voltage_confirmed(channel, voltage)

    def after_run(self, mode):
        channels = self._run_channels or []
        try:
            for channel, _, idle_voltage in channels:
                self.controller.set_voltage_confirmed(channel, idle_voltage)
        finally:
            self._run_channels = None
            self._update_state()

    def _update_state(self):
        opened = self.controller.port.isOpen()
        self.ports.setEnabled(not opened)
        self.refresh.setEnabled(not opened)
        self.serial_number.setEnabled(not opened)
        self.auto_connect_button.setEnabled(not opened)
        self.connect_button.setText("Disconnect" if opened else "Connect")
        self.connect_button.setEnabled(opened or self.ports.currentData() is not None)
        selected = {ch for ch, _, _ in self._run_channels or []}
        for channel, voltage in enumerate(self.voltages):
            voltage.setEnabled(self.controller.connected and not self._applying_idle
                               and channel not in selected)
        automatic = bool(self._run_channels)
        for control in (*self.run_enabled, *self.run_voltages):
            control.setEnabled(self._run_channels is None)
        if automatic:
            self.connect_button.setEnabled(False)
            self.reset_serial_button.setEnabled(False)
        else:
            self.reset_serial_button.setEnabled(True)
        if not self.controller.connected:
            for label in self.applied:
                label.setText("Unknown")
