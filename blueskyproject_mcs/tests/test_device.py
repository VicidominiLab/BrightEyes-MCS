import pytest

ophyd = pytest.importorskip("ophyd")

from brighteyes_bluesky import BrightEyesMCSLLDevice, MappingRegisterIO


def test_device_roundtrip_with_mapping_io():
    io = MappingRegisterIO({"Run": False, "#pixels": 512})
    device = BrightEyesMCSLLDevice(name="mcs", register_io=io)

    device.reg_run.put(True)
    device.reg_number_pixels.put(300)

    assert io.values["Run"] is True
    assert io.values["#pixels"] == 300
    assert device.read_registers("Run", "#pixels") == {"Run": True, "#pixels": 300}


def test_read_only_register_rejects_put():
    device = BrightEyesMCSLLDevice(name="mcs", register_io=MappingRegisterIO())

    with pytest.raises(PermissionError):
        device.reg_fsm_status.put(1)
