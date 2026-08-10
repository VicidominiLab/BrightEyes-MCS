import pytest

ophyd = pytest.importorskip("ophyd")

from brighteyes_bluesky import BrightEyesMCSLLDevice, MappingRegisterIO


def test_device_roundtrip_with_mapping_io():
    io = MappingRegisterIO({"start_command": False, "max_pixel": 512})
    device = BrightEyesMCSLLDevice(name="mcs", register_io=io)

    device.reg_start_command.put(True)
    device.reg_max_pixel.put(300)

    assert io.values["start_command"] is True
    assert io.values["max_pixel"] == 300
    assert device.read_registers("start_command", "max_pixel") == {"start_command": True, "max_pixel": 300}


def test_read_only_register_rejects_put():
    device = BrightEyesMCSLLDevice(name="mcs", register_io=MappingRegisterIO())

    with pytest.raises(PermissionError):
        device.reg_debug_scan_fsm_status.put(1)
