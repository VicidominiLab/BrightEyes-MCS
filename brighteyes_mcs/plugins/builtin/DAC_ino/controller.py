"""Non-blocking, acknowledged transport for sketch_mar19a.ino."""

import math

from PySide6.QtCore import QIODevice, QObject, QTimer, Signal
from PySide6.QtSerialPort import QSerialPort


def voltage_to_code(voltage):
    voltage = float(voltage)
    if not math.isfinite(voltage) or not 0 <= voltage <= 5:
        raise ValueError("Voltage must be between 0 and 5 V")
    return int(voltage * 4095 / 5 + 0.5)


class DACController(QObject):
    state_changed = Signal()
    message = Signal(str)
    acknowledged = Signal(int, int)

    def __init__(self, parent=None, port=None):
        super().__init__(parent)
        self.port = port if port is not None else QSerialPort(self)
        self.connected = False
        self.pending = None
        self.buffer = bytearray()
        self.boot_timer = QTimer(self)
        self.boot_timer.setSingleShot(True)
        self.boot_timer.timeout.connect(self._handshake)
        self.reply_timer = QTimer(self)
        self.reply_timer.setSingleShot(True)
        self.reply_timer.timeout.connect(self._timeout)
        self.port.readyRead.connect(self._read)
        self.port.errorOccurred.connect(self._serial_error)

    @property
    def busy(self):
        return self.boot_timer.isActive() or self.pending is not None

    def connect_port(self, name):
        self.disconnect_port()
        self.port.setPortName(name)
        self.port.setBaudRate(9600)
        self.port.setDataBits(QSerialPort.DataBits.Data8)
        self.port.setParity(QSerialPort.Parity.NoParity)
        self.port.setStopBits(QSerialPort.StopBits.OneStop)
        self.port.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
        if not self.port.open(QIODevice.OpenModeFlag.ReadWrite):
            self.message.emit(f"Cannot open {name}: {self.port.errorString()}")
            return
        # Opening a USB serial port can reset the Arduino. Do not send SET on connect.
        self.boot_timer.start(1800)
        self.message.emit(f"Opened {name}; waiting for Arduino startup…")
        self.state_changed.emit()

    def disconnect_port(self):
        self.boot_timer.stop()
        self.reply_timer.stop()
        self.pending = None
        self.connected = False
        self.buffer.clear()
        if self.port.isOpen():
            self.port.close()
        self.state_changed.emit()

    def _handshake(self):
        self.port.clear()
        self.buffer.clear()
        self._send("PING", "READY")

    def set_voltage(self, channel, voltage):
        if not isinstance(channel, int) or not 0 <= channel <= 3:
            raise ValueError("Channel must be between 0 and 3")
        code = voltage_to_code(voltage)
        if not self.connected or self.busy:
            raise RuntimeError("DAC is disconnected or waiting for a reply")
        self._send(f"SET,{channel},{code}", f"OK,{channel},{code}", (channel, code))

    def _send(self, command, expected, output=None):
        self.pending = (expected, output)
        data = (command + "\n").encode("ascii")
        if self.port.write(data) != len(data):
            self._fail("Serial write failed; output state is unknown.")
            return
        self.reply_timer.start(1500)
        self.state_changed.emit()

    def _read(self):
        self.buffer.extend(bytes(self.port.readAll()))
        if len(self.buffer) > 4096:
            self._fail("Serial receive buffer overflow.")
            return
        while b"\n" in self.buffer:
            raw, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            line = raw.rstrip(b"\r").decode("ascii", errors="replace")
            if not line or self.boot_timer.isActive() or self.pending is None:
                continue
            expected, output = self.pending
            # The startup READY may arrive immediately before a SET acknowledgment.
            if line == "READY" and output is not None:
                continue
            if line != expected:
                errors = {
                    "ERR,FMT": "Malformed command",
                    "ERR,CH": "Invalid DAC channel",
                    "ERR,VAL": "Invalid DAC value",
                    "ERR,I2C": "I2C / multiplexer communication error",
                }
                self._fail(errors.get(line, f"Unexpected reply: {line}"))
                return
            self.reply_timer.stop()
            self.pending = None
            if output is None:
                self.connected = True
                self.message.emit("Connected: Arduino replied READY.")
            else:
                self.acknowledged.emit(*output)
                self.message.emit(f"DAC {output[0]} acknowledged code {output[1]}.")
            self.state_changed.emit()

    def _timeout(self):
        self._fail("Reply timed out; output state is unknown. Reconnect before sending again.")

    def _serial_error(self, error):
        if error != QSerialPort.SerialPortError.NoError:
            self._fail(f"Serial error: {self.port.errorString()}")

    def _fail(self, message):
        self.disconnect_port()
        self.message.emit(message)
