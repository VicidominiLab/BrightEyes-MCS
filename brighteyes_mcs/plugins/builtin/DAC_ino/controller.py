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
    debug = Signal(str)
    acknowledged = Signal(int, int)
    readback = Signal(int, int)

    def __init__(self, parent=None, port=None):
        super().__init__(parent)
        self.port = port if port is not None else QSerialPort(self)
        self.connected = False
        self.pending = None
        self.buffer = bytearray()
        self.port_name = None
        self.ping_attempts = 0
        self.boot_timer = QTimer(self)
        self.boot_timer.setSingleShot(True)
        self.boot_timer.timeout.connect(self._handshake)
        self.sync_timer = QTimer(self)
        self.sync_timer.setSingleShot(True)
        self.sync_timer.timeout.connect(self._ping)
        self.reply_timer = QTimer(self)
        self.reply_timer.setSingleShot(True)
        self.reply_timer.timeout.connect(self._timeout)
        self.get_timer = QTimer(self)
        self.get_timer.setInterval(10000)
        self.get_timer.timeout.connect(self.read_outputs)
        self.port.readyRead.connect(self._read)
        self.port.errorOccurred.connect(self._serial_error)
        self.message.connect(lambda text: self.debug.emit(f"INFO {text}"))

    @property
    def busy(self):
        return (self.boot_timer.isActive() or self.sync_timer.isActive()
                or self.pending is not None)

    def connect_port(self, name):
        self.disconnect_port()
        self.port_name = name
        self.ping_attempts = 0
        self.debug.emit(f"OPEN {name} (9600 baud, 8N1, no flow control)")
        self.port.setPortName(name)
        self.port.setBaudRate(9600)
        self.port.setDataBits(QSerialPort.DataBits.Data8)
        self.port.setParity(QSerialPort.Parity.NoParity)
        self.port.setStopBits(QSerialPort.StopBits.OneStop)
        self.port.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
        if not self.port.open(QIODevice.OpenModeFlag.ReadWrite):
            self.message.emit(f"Cannot open {name}: {self.port.errorString()}")
            return
        # Native USB CDC needs the host's terminal-ready control signals.
        # Assert DTR before RTS; avoid the ESP32 bootloader's RTS-first sequence.
        if not self.port.setDataTerminalReady(True):
            self._fail(f"Cannot assert serial DTR: {self.port.errorString()}")
            return
        if not self.port.setRequestToSend(True):
            self._fail(f"Cannot assert serial RTS: {self.port.errorString()}")
            return
        self.debug.emit("USB CDC control lines: DTR=1, RTS=1")
        # Opening a USB serial port can reset the Arduino. Do not send SET on connect.
        self.boot_timer.start(1800)
        self.message.emit(f"Opened {name}; waiting for Arduino startup…")
        self.state_changed.emit()

    def disconnect_port(self):
        self.boot_timer.stop()
        self.sync_timer.stop()
        self.reply_timer.stop()
        self.get_timer.stop()
        self.pending = None
        self.connected = False
        self.buffer.clear()
        if self.port.isOpen():
            self.port.close()
            self.debug.emit("CLOSE serial port")
        self.state_changed.emit()

    def reset_serial_link(self, name=None):
        name = name or self.port_name
        if not name:
            self.message.emit("Select a serial port before resetting the link.")
            return
        self.debug.emit("RESET serial link: cancel pending command, reopen, drain, PING, GET")
        # Never replay a SET: it may have reached the DAC before its reply was lost.
        self.connect_port(name)

    def _handshake(self):
        self.port.clear()
        self.buffer.clear()
        # Terminate any partial command still held by the Arduino, then drain its
        # reply before PING. Closing the PC port alone does not reset that parser.
        self.debug.emit("SYNC: send newline and drain stale replies for 300 ms")
        self.sync_timer.start(300)
        if self.port.write(b"\n") != 1:
            self._fail("Failed to clear the Arduino's partial command.")
            return
        self.state_changed.emit()

    def _ping(self):
        self.port.clear()
        self.buffer.clear()
        self.ping_attempts += 1
        self.debug.emit(f"SYNC: PING attempt {self.ping_attempts}/3")
        self._send("PING", "READY")

    def set_voltage(self, channel, voltage):
        if not isinstance(channel, int) or not 0 <= channel <= 3:
            raise ValueError("Channel must be between 0 and 3")
        code = voltage_to_code(voltage)
        if not self.connected or self.busy:
            raise RuntimeError("DAC is disconnected or waiting for a reply")
        self._send(f"SET,{channel},{code}", f"OK,{channel},{code}", (channel, code))

    def read_outputs(self):
        # Defer polling while a command is awaiting its acknowledgment.
        if self.connected and not self.busy:
            self._send("GET", "GET")

    def _send(self, command, expected, output=None):
        self.pending = (expected, output)
        data = (command + "\n").encode("ascii")
        self.debug.emit(f"TX {data!r}")
        written = self.port.write(data)
        if self.pending is None:  # A synchronous serial error already closed the link.
            return
        if written != len(data):
            self._fail("Serial write failed; output state is unknown.")
            return
        self.reply_timer.start(1500)
        self.state_changed.emit()

    def _read(self):
        data = bytes(self.port.readAll())
        self.debug.emit(f"RX {data!r}")
        self.buffer.extend(data)
        if len(self.buffer) > 4096:
            self._fail("Serial receive buffer overflow.")
            return
        while b"\n" in self.buffer:
            raw, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            line = raw.rstrip(b"\r").decode("ascii", errors="replace")
            if (not line or self.boot_timer.isActive() or self.sync_timer.isActive()
                    or self.pending is None):
                continue
            expected, output = self.pending
            if expected == "READY" and line != "READY":
                self.debug.emit(f"SYNC: discarded stale reply {line!r}; waiting for READY")
                continue
            # The startup READY may arrive immediately before a SET acknowledgment.
            if line == "READY" and output is not None:
                continue
            codes = None
            if expected == "GET" and line.startswith("VALS,"):
                values = line.split(",")[1:]
                if (len(values) != 4 or
                        any(not v.isascii() or not v.isdigit() for v in values) or
                        any(not 0 <= int(v) <= 4095 for v in values)):
                    self._fail(f"Invalid GET reply: {line}")
                    return
                codes = [int(v) for v in values]
            if codes is None and (expected == "GET" or line != expected):
                errors = {
                    "ERR,FMT": "Malformed command",
                    "ERR,CH": "Invalid DAC channel",
                    "ERR,VAL": "Invalid DAC value",
                    "ERR,I2C": "I2C / multiplexer communication error",
                }
                if expected == "GET" and line == "ERR,FMT":
                    self._fail("Firmware does not support GET; upload the bundled DAC_ino sketch.")
                else:
                    self._fail(errors.get(line, f"Unexpected reply: {line}"))
                return
            self.reply_timer.stop()
            self.pending = None
            if expected == "READY":
                self.buffer.clear()
                self.message.emit("Arduino replied READY; reading all DAC channels…")
                self._send("GET", "GET")
                continue
            if expected == "GET":
                self.connected = True
                self.get_timer.start()
                for channel, code in enumerate(codes):
                    self.readback.emit(channel, code)
                self.message.emit(f"GET: {codes} (all channels; refresh every 10 s while idle).")
            else:
                self.acknowledged.emit(*output)
                self.message.emit(f"DAC {output[0]} acknowledged code {output[1]}.")
            self.state_changed.emit()

    def _timeout(self):
        if self.pending == ("READY", None) and not self.connected and self.ping_attempts < 3:
            self.debug.emit("SYNC: no READY yet; drain and retry startup PING")
            self.pending = None
            self._handshake()
            return
        self._fail("Reply timed out; output state is unknown. Reconnect before sending again.")

    def _serial_error(self, error):
        if error != QSerialPort.SerialPortError.NoError:
            self._fail(f"Serial error: {self.port.errorString()}")

    def _fail(self, message):
        self.disconnect_port()
        self.message.emit(message)
