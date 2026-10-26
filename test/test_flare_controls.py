"""Flare live writes: ordering, error propagation and concurrent GUI changes."""

import threading
from unittest.mock import Mock

import pytest

from brighteyes_mcs.acquisition.detectors.flare.config import axis_registers_from_gui
from brighteyes_mcs.acquisition.detectors.flare.controls import FlareLiveControls
from brighteyes_mcs.hardware.flare import FlareError


def client():
    instance = Mock()
    instance.write_register.side_effect = lambda name, value: {"name": name, "value": value}
    return instance


def test_geometry_conversion_and_commit_use_native_counts_for_all_axes():
    controls, device = FlareLiveControls(), client()
    values = dict(nx=4, ny=2, nframe=2, calib_x=2, calib_y=-1, calib_z=4,
                  range_x=4, range_y=2, range_z=4, offset_x_um=2, offset_y_um=-1,
                  offset_z_um=4, offsetExtra_x=0.25)
    registers = axis_registers_from_gui(values)
    assert registers == {
        "axis_start_offset_volts": [819, 6554, 1638],
        "axis_calibration_volts_per_step": [1638, -3277, 1638],
    }
    controls.request(registers, geometry=values)
    controls.apply(device)
    assert [call.args for call in device.write_register.call_args_list] == [
        *registers.items(), ("command", 1),
    ]
    assert controls.geometry() == values
    assert not controls.has_pending()
    assert all("requested_at" in event and "finished_at" in event for event in controls.events())


def test_gui_edits_coalesce_and_new_edits_during_io_remain_pending():
    controls, device = FlareLiveControls(), client()
    controls.request({"laser_1_enable": 1})
    controls.request({"laser_1_enable": 0})

    def write(name, value):
        controls.request({"laser_1_enable": 1})
        return {"name": name, "value": value}

    device.write_register.side_effect = write
    controls.apply(device)
    device.write_register.assert_called_once_with("laser_1_enable", 0)
    assert controls.has_pending()
    device.write_register.side_effect = lambda name, value: {"name": name, "value": value}
    controls.apply(device)
    assert device.write_register.call_args.args == ("laser_1_enable", 1)
    assert not controls.has_pending()


def test_live_writer_waits_for_configuration_without_blocking_new_gui_requests():
    controls, device = FlareLiveControls(), client()
    entered = threading.Event()

    def apply():
        entered.set()
        controls.apply(device)

    with controls.io_lock:
        controls.request({"laser_1_enable": 1})
        thread = threading.Thread(target=apply)
        thread.start()
        assert entered.wait(2)
        device.write_register.assert_not_called()
        controls.request({"laser_1_enable": 0})
    thread.join(2)
    assert not thread.is_alive()
    device.write_register.assert_called_once_with("laser_1_enable", 0)


def test_failed_axis_write_reports_server_error_without_commit_or_retry():
    controls, device = FlareLiveControls(), client()
    controls.request({"axis_start_offset_volts": [1, 2, 3], "axis_calibration_volts_per_step": [4, 5, 6]})
    device.write_register.side_effect = FlareError("HTTP 409, errno=16: busy")
    with pytest.raises(FlareError, match="HTTP 409"):
        controls.apply(device)
    device.write_register.assert_called_once_with("axis_start_offset_volts", [1, 2, 3])
    assert controls.geometry() is None
    assert not controls.has_pending()
    assert controls.events()[0]["error"] == "HTTP 409, errno=16: busy"
    controls.apply(device)
    assert device.write_register.call_count == 1


def test_requested_laser_states_are_reapplied_after_each_configuration_reset():
    controls, device = FlareLiveControls(), client()
    controls.request({"laser_1_enable": 1, "laser_2_enable": 0})
    controls.apply(device)
    assert not controls.has_pending()
    device.reset_mock()
    controls.apply(device, restore=True)
    assert [call.args for call in device.write_register.call_args_list] == [
        ("laser_1_enable", 1), ("laser_2_enable", 0),
    ]
    assert len(controls.events()) == 4
    controls.begin_run()
    assert controls.events() == []
