"""DAC protocol and UI checks without opening real serial hardware."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QTimer, Signal
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
    ports = [
        SimpleNamespace(portName=lambda: "COM3", description=lambda: "Other",
                        serialNumber=lambda: "OTHER"),
        SimpleNamespace(portName=lambda: "COM12", description=lambda: "USB TTL",
                        serialNumber=lambda: "TTL-123"),
    ]
    monkeypatch.setattr(plugin_form, "QSerialPortInfo", SimpleNamespace(availablePorts=lambda: ports))
    window = SimpleNamespace(
        plugin_configuration={"DAC_ino": {"serial_number": "TTL-123"}},
        plugin_configuration_files={},
        _load_plugin_config_file=MagicMock(),
        SavePluginConfiguration=MagicMock(),
    )
    manager = SimpleNamespace(main_window=window, add_tab=MagicMock(), on_run=MagicMock(), on=MagicMock())
    context = PluginContext(manager)
    widget = plugin.setup(context)
    form = context["form"]
    manager.on_run.assert_called_once_with(form.before_run, form.after_run)
    manager.add_tab.assert_called_once_with(widget, "DAC_ino")
    assert form.ports.currentData() == "COM12"
    assert len(form.voltages) == 4
    assert all(not voltage.isEnabled() for voltage in form.voltages)
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


def test_confirmed_voltage_waits_for_ack(controller):
    ctl, port = controller
    QTimer.singleShot(10, lambda: port.reply(b"OK,0,4095\n"))
    ctl.set_voltage_confirmed(0, 5)
    assert not ctl.busy
    assert port.writes[-1] == b"SET,0,4095\n"


def test_confirmed_voltage_rejects_failed_ack(controller):
    ctl, port = controller
    QTimer.singleShot(10, lambda: port.reply(b"ERR,I2C\n"))
    with pytest.raises(RuntimeError, match="did not confirm"):
        ctl.set_voltage_confirmed(0, 5)


def test_automatic_channels_snapshot_and_restore_idle_voltage(app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QWidget
    widget = QWidget()
    form = plugin_form.myForm()
    form.setupUi(widget)
    apply = MagicMock()
    monkeypatch.setattr(form.controller, "set_voltage_confirmed", apply)
    form.run_enabled[1].setChecked(True)
    form.run_voltages[1].setValue(3.2)
    form.voltages[1].setValue(1.25)
    form.before_run("preview")
    apply.assert_called_once_with(1, 3.2)
    assert not form.run_enabled[1].isEnabled()
    assert not form.voltages[1].isEnabled()
    form.after_run("preview")
    assert apply.call_args_list == [((1, 3.2),), ((1, 1.25),)]
    assert form.run_enabled[1].isEnabled()
    widget.deleteLater()


def test_idle_voltage_applies_only_when_editing_finishes(app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QWidget, QPushButton

    widget = QWidget()
    form = plugin_form.myForm()
    form.setupUi(widget)
    form.controller.connected = True
    form._update_state()
    apply = MagicMock()
    monkeypatch.setattr(form.controller, "set_voltage_confirmed", apply)
    assert not any(button.text() == "Set" for button in widget.findChildren(QPushButton))
    form.voltages[2].setValue(2.4)
    apply.assert_not_called()
    form.voltages[2].editingFinished.emit()
    apply.assert_called_once_with(2, 2.4)
    assert form.voltages[2].isEnabled()
    widget.deleteLater()


@pytest.mark.parametrize("auto_connect", [False, True])
def test_cfg_applied_before_optional_auto_connect(app, monkeypatch, auto_connect):
    from PySide6.QtWidgets import QWidget

    port = SimpleNamespace(portName=lambda: "COM7", description=lambda: "DAC",
                           serialNumber=lambda: "CFG-123")
    monkeypatch.setattr(plugin_form, "QSerialPortInfo", SimpleNamespace(availablePorts=lambda: [port]))
    widget = QWidget()
    form = plugin_form.myForm()
    form.setupUi(widget)
    configuration = {
        "serial_number": "CFG-123", "auto_connect": auto_connect,
        "idle_voltages": [1, 2, 3, 4], "run_voltages": [5, 4, 3, 2],
        "enabled": [True, False, True, False],
    }
    window = SimpleNamespace(plugin_configuration={"DAC_ino": configuration},
                             SavePluginConfiguration=MagicMock())
    seen = []

    def connect(name):
        seen.append((name, [v.value() for v in form.voltages],
                     [v.value() for v in form.run_voltages],
                     [c.isChecked() for c in form.run_enabled]))

    monkeypatch.setattr(form.controller, "connect_port", connect)
    form.bind_configuration(window)
    assert seen == ([("COM7", [1, 2, 3, 4], [5, 4, 3, 2], [True, False, True, False])]
                    if auto_connect else [])
    # Editing updates the payload consumed by the normal plugin CFG saver.
    form.run_voltages[0].setValue(4.5)
    form.save_configuration.click()
    window.SavePluginConfiguration.assert_called_once_with("DAC_ino")
    assert window.plugin_configuration["DAC_ino"]["run_voltages"][0] == 4.5
    assert window.plugin_configuration["DAC_ino"]["auto_connect"] is auto_connect
    # Applying a CFG while already connected must not disconnect or reopen.
    seen.clear()
    monkeypatch.setattr(form.controller.port, "isOpen", lambda: True)
    form.apply_configuration()
    assert seen == []
    widget.deleteLater()
