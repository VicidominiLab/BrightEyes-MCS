"""DAC protocol and UI checks without opening real serial hardware."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

from brighteyes_mcs.plugins.api import PluginContext
from brighteyes_mcs.plugins.builtin.DAC_ino.controller import DACController, voltage_to_code
from brighteyes_mcs.plugins.builtin.DAC_ino import plugin, plugin_form


pytestmark = [pytest.mark.qt, pytest.mark.qt_isolated]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakePort(QObject):
    readyRead = Signal()
    errorOccurred = Signal(object)

    def __init__(self):
        super().__init__()
        self.opened = False
        self.received = b""
        self.writes = []
        self.control_lines = []

    def __getattr__(self, name):
        if name.startswith("set"):
            return lambda *args: None
        raise AttributeError(name)

    def open(self, mode):
        self.opened = True
        return True

    def setDataTerminalReady(self, value):
        self.control_lines.append(("DTR", value))
        return True

    def setRequestToSend(self, value):
        self.control_lines.append(("RTS", value))
        return True

    def close(self):
        self.opened = False

    def isOpen(self):
        return self.opened

    def clear(self):
        self.received = b""

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def readAll(self):
        result, self.received = self.received, b""
        return result

    def reply(self, data):
        self.received += data
        self.readyRead.emit()


@pytest.fixture
def controller(app):
    port = FakePort()
    ctl = DACController(port=port)
    ctl.connect_port("COM42")
    assert not port.writes  # Never send output commands on connect.
    ctl.boot_timer.stop()
    ctl._handshake()
    assert port.writes == [b"\n"]
    port.reply(b"ERR,FMT\r\n")  # Reply to the delimiter is drained, not treated as failure.
    ctl.sync_timer.stop()
    ctl._ping()
    assert port.writes == [b"\n", b"PING\n"]
    port.reply(b"READY\r\n")
    assert not ctl.connected
    assert port.writes[-1] == b"GET\n"
    port.reply(b"VALS,0,1024,2048,4095\r\n")
    assert ctl.connected
    yield ctl, port
    ctl.disconnect_port()


@pytest.mark.parametrize("voltage,code", [(0, 0), (2.5, 2048), (5, 4095)])
def test_voltage_conversion(voltage, code):
    assert voltage_to_code(voltage) == code


@pytest.mark.parametrize("voltage", [-0.01, 5.01, float("nan"), float("inf")])
def test_voltage_out_of_range(voltage):
    with pytest.raises(ValueError):
        voltage_to_code(voltage)


def test_set_waits_for_complete_matching_ack(controller):
    ctl, port = controller
    ack = MagicMock()
    ctl.acknowledged.connect(ack)
    ctl.set_voltage(3, 2.5)
    assert port.writes[-1] == b"SET,3,2048\n"
    with pytest.raises(RuntimeError):
        ctl.set_voltage(0, 1)
    port.reply(b"READY\r\nOK,3,20")
    ack.assert_not_called()
    port.reply(b"48\r\n")
    ack.assert_called_once_with(3, 2048)
    assert not ctl.busy


@pytest.mark.parametrize("reply", [b"ERR,I2C\n", b"OK,1,4095\n"])
def test_errors_and_wrong_ack_disconnect(controller, reply):
    ctl, port = controller
    ack = MagicMock()
    ctl.acknowledged.connect(ack)
    ctl.set_voltage(0, 5)
    port.reply(reply)
    assert not ctl.connected and not port.isOpen()
    ack.assert_not_called()


def test_timeout_closes_port_without_retry(controller):
    ctl, port = controller
    ctl.set_voltage(0, 1)
    writes = list(port.writes)
    ctl._timeout()
    assert not ctl.connected and not port.isOpen()
    assert port.writes == writes
    assert not ctl.get_timer.isActive()


def test_native_usb_control_lines(controller):
    ctl, port = controller
    assert port.control_lines == [("DTR", True), ("RTS", True)]
    assert ctl.connected and not ctl.busy


def test_control_line_failure_stops_connection(app):
    port = FakePort()
    port.setDataTerminalReady = lambda value: False
    port.errorString = lambda: "DTR failed"
    ctl = DACController(port=port)
    ctl.connect_port("COM42")
    assert not ctl.connected and not port.isOpen()
    assert not ctl.boot_timer.isActive()
    assert not port.writes


def test_startup_ping_retries_are_bounded(app):
    port = FakePort()
    ctl = DACController(port=port)
    ctl.connect_port("COM42")
    ctl.boot_timer.stop()
    ctl._handshake()
    for attempt in range(1, 4):
        ctl.sync_timer.stop()
        ctl._ping()
        assert ctl.ping_attempts == attempt
        ctl.reply_timer.stop()
        ctl._timeout()
        if attempt < 3:
            assert port.isOpen() and ctl.sync_timer.isActive()
    assert not port.isOpen() and not ctl.connected
    assert not ctl.sync_timer.isActive()
    assert port.writes.count(b"PING\n") == 3
    assert not any(data.startswith(b"SET") for data in port.writes)


def test_periodic_get_defers_during_set(controller):
    ctl, port = controller
    assert ctl.get_timer.isActive()
    assert ctl.get_timer.interval() == 10000
    readback = MagicMock()
    ctl.readback.connect(readback)
    ctl.set_voltage(0, 5)
    writes = list(port.writes)
    ctl.read_outputs()
    assert port.writes == writes
    port.reply(b"OK,0,4095\n")
    ctl.read_outputs()
    assert port.writes[-1] == b"GET\n"
    port.reply(b"VALS,0,1024,2048,")
    readback.assert_not_called()
    port.reply(b"4095\r\n")
    assert readback.call_args_list == [((0, 0),), ((1, 1024),), ((2, 2048),), ((3, 4095),)]
    assert ctl.connected and not ctl.busy


def test_initial_get_timeout_does_not_enable_outputs(app):
    port = FakePort()
    ctl = DACController(port=port)
    ctl.connect_port("COM42")
    ctl.boot_timer.stop()
    ctl._handshake()
    ctl.sync_timer.stop()
    ctl._ping()
    port.reply(b"READY\n")
    assert port.writes[-1] == b"GET\n"
    assert not ctl.connected
    ctl._timeout()
    assert not port.isOpen() and not ctl.get_timer.isActive()


def test_reset_discards_partial_reply_and_never_replays_set(controller):
    ctl, port = controller
    ctl.set_voltage(0, 5)
    port.reply(b"OK,0,40")
    assert ctl.buffer
    previous_writes = list(port.writes)
    ctl.reset_serial_link()
    assert port.isOpen() and not ctl.connected
    assert ctl.pending is None and not ctl.buffer
    assert not ctl.get_timer.isActive() and not ctl.reply_timer.isActive()
    assert port.writes == previous_writes
    ctl.boot_timer.stop()
    ctl._handshake()
    port.reply(b"95\nERR,FMT\n")
    ctl.sync_timer.stop()
    ctl._ping()
    port.reply(b"OK,0,4095\nREADY\n")
    assert port.writes[-1] == b"GET\n"
    port.reply(b"VALS,0,1024,2048,4095\n")
    assert ctl.connected and not ctl.busy
    assert port.writes[len(previous_writes):] == [b"\n", b"PING\n", b"GET\n"]


def test_disconnect_cancels_resynchronization(controller):
    ctl, port = controller
    ctl.reset_serial_link()
    ctl.boot_timer.stop()
    ctl._handshake()
    assert ctl.sync_timer.isActive()
    ctl.disconnect_port()
    assert not ctl.sync_timer.isActive() and not ctl.busy
    assert not port.isOpen()


@pytest.mark.parametrize("reply", [
    b"VALS\n", b"VALS,0,1,2\n", b"VALS,0,1,2,4096\n",
    b"VALS,0,-1,2,3\n", b"VALS,0,1,x,3\n", b"ERR,FMT\n", b"ERR,I2C\n",
])
def test_invalid_get_does_not_publish_partial_values(controller, reply):
    ctl, port = controller
    readback = MagicMock()
    ctl.readback.connect(readback)
    ctl.read_outputs()
    port.reply(reply)
    readback.assert_not_called()
    assert not ctl.connected and not port.isOpen()


def test_get_vals_maps_all_four_channels(controller):
    ctl, port = controller
    readback = MagicMock()
    ctl.readback.connect(readback)
    ctl.read_outputs()
    assert port.writes[-1] == b"GET\n"
    port.reply(b"VALS,1000,0,0,0\r\n")
    assert readback.call_args_list == [((0, 1000),), ((1, 0),), ((2, 0),), ((3, 0),)]
    assert ctl.connected and not ctl.busy


def test_plugin_setup_and_converter_serial_matching(app, monkeypatch, tmp_path):
    settings = QSettings(str(tmp_path / "dac.ini"), QSettings.Format.IniFormat)
    settings.setValue("serial_number", "TTL-123")
    monkeypatch.setattr(plugin_form, "QSettings", lambda *args: settings)
    ports = [
        SimpleNamespace(portName=lambda: "COM3", description=lambda: "Other",
                        serialNumber=lambda: "OTHER"),
        SimpleNamespace(portName=lambda: "COM12", description=lambda: "USB TTL",
                        serialNumber=lambda: "TTL-123"),
    ]
    monkeypatch.setattr(plugin_form, "QSerialPortInfo", SimpleNamespace(availablePorts=lambda: ports))
    manager = SimpleNamespace(add_tab=MagicMock())
    context = PluginContext(manager)
    widget = plugin.setup(context)
    form = context["form"]
    manager.add_tab.assert_called_once_with(widget, "DAC_ino")
    assert form.ports.currentData() == "COM12"
    assert len(form.voltages) == 4
    assert all(not button.isEnabled() for button in form.set_buttons)
    ports[1].portName = lambda: "COM24"
    form.refresh_ports()
    assert form.ports.currentData() == "COM24"
    ports.pop()
    form.refresh_ports()
    assert form.ports.currentData() is None
    assert not form.connect_button.isEnabled()
    form.serial_number.clear()
    form.refresh_ports()
    assert form.ports.currentData() == "COM3"
    # The one-click action uses the default S/N when the field is empty.
    ports[0].serialNumber = lambda: plugin_form.DEFAULT_SERIAL_NUMBER
    connect = MagicMock()
    monkeypatch.setattr(form.controller, "connect_port", connect)
    form.auto_connect_button.click()
    assert form.serial_number.text() == "3C8427C3B50C"
    connect.assert_called_once_with("COM3")
    widget.close()
    widget.deleteLater()
