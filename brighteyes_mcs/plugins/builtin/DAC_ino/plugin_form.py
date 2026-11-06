"""Qt controls and USB converter identification for the DAC tab."""

from PySide6.QtCore import QDateTime, QSettings
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .controller import DACController


DEFAULT_SERIAL_NUMBER = "3C8427C3B50C"


class myForm:
    def setupUi(self, Form):
        self.settings = QSettings("BrightEyes-MCS", "DAC_ino")
        self.controller = DACController(Form)
        layout = QVBoxLayout(Form)
        connection = QGroupBox("USB-to-TTL connection (9600 baud)", Form)
        grid = QGridLayout(connection)
        self.ports = QComboBox(connection)
        self.refresh = QPushButton("Refresh ports", connection)
        self.serial_number = QLineEdit(connection)
        self.serial_number.setPlaceholderText("USB converter S/N from driver (optional)")
        self.serial_number.setText(
            str(self.settings.value("serial_number", "") or DEFAULT_SERIAL_NUMBER)
        )
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
        layout.addWidget(connection)

        outputs = QGroupBox("DAC outputs — 0 to 5 V", Form)
        output_grid = QGridLayout(outputs)
        self.voltages, self.set_buttons, self.applied = [], [], []
        for column, title in enumerate(("Channel", "Requested voltage", "", "Last confirmed / read")):
            output_grid.addWidget(QLabel(title), 0, column)
        for channel in range(4):
            voltage = QDoubleSpinBox(outputs)
            voltage.setRange(0, 5)
            voltage.setDecimals(3)
            voltage.setSingleStep(0.01)
            voltage.setSuffix(" V")
            button = QPushButton("Set", outputs)
            button.clicked.connect(lambda checked=False, ch=channel: self._set_voltage(ch))
            applied = QLabel("Unknown", outputs)
            self.voltages.append(voltage)
            self.set_buttons.append(button)
            self.applied.append(applied)
            output_grid.addWidget(QLabel(f"DAC {channel}"), channel + 1, 0)
            output_grid.addWidget(voltage, channel + 1, 1)
            output_grid.addWidget(button, channel + 1, 2)
            output_grid.addWidget(applied, channel + 1, 3)
        layout.addWidget(outputs)
        note = QLabel(
            "Press Set to apply a voltage. 12-bit codes: 0–4095, assuming 5 V full scale.\n"
            "GET reads DAC codes, not measured voltages. Opening the port may reset the Arduino "
            "and zero its outputs.", Form
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
        self.settings.setValue("serial_number", target)
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
        self.controller.set_voltage(channel, self.voltages[channel].value())

    def _acknowledged(self, channel, code):
        self.applied[channel].setText(f"{code * 5 / 4095:.3f} V (code {code})")

    def _update_state(self):
        opened = self.controller.port.isOpen()
        self.ports.setEnabled(not opened)
        self.refresh.setEnabled(not opened)
        self.serial_number.setEnabled(not opened)
        self.auto_connect_button.setEnabled(not opened)
        self.connect_button.setText("Disconnect" if opened else "Connect")
        self.connect_button.setEnabled(opened or self.ports.currentData() is not None)
        for button in self.set_buttons:
            button.setEnabled(self.controller.connected and not self.controller.busy)
        if not self.controller.connected:
            for label in self.applied:
                label.setText("Unknown")
