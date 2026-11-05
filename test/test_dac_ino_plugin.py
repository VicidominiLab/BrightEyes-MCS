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

    def __getattr__(self, name):
        if name.startswith("set"):
            return lambda *args: None
        raise AttributeError(name)

    def open(self, mode):
        self.opened = True
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
    assert port.writes == [b"PING\n"]
    port.reply(b"READY\r\n")
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
    widget.close()
    widget.deleteLater()
