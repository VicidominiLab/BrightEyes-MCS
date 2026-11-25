"""Firmware 2.1 analog names across hardware access and stored metadata."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from brighteyes_mcs.hardware.fpga import FpgaHandle
from brighteyes_mcs.hardware.register_names import ANALOG_REGISTER_ALIASES, REGISTER_ALIASES
from brighteyes_mcs.hardware.tag_clock import compatible_tag_registers, normalize_tag_registers
from brighteyes_mcs.storage.h5 import H5Manager
from brighteyes_mcs.storage.legacy_names import LEGACY_H5_REGISTER_NAME_MAP


@pytest.mark.parametrize("old,new", ANALOG_REGISTER_ALIASES.items())
def test_analog_names_migrate_and_explicit_current_value_wins(old, new):
    assert normalize_tag_registers({old: True}) == {new: True}
    assert normalize_tag_registers({old: True, new: False}) == {new: False}
    assert normalize_tag_registers({new: False, old: True}) == {new: False}


@pytest.mark.parametrize("old,new", ANALOG_REGISTER_ALIASES.items())
@pytest.mark.parametrize("old_firmware", [False, True])
def test_initial_and_live_register_access_uses_the_exposed_name(old, new, old_firmware):
    physical = old if old_firmware else new
    register = MagicMock()
    register.read.return_value = True
    available = {physical: register}
    # This is also the dictionary used by the FPGA worker's startup writes.
    assert compatible_tag_registers({old: True, new: False}, available) == {physical: False}
    handle = FpgaHandle.__new__(FpgaHandle)
    handle.configuration = {"detector_model": "SPAD Array"}
    handle.nifpga_obj = SimpleNamespace(registers=available)
    for requested in (old, new):
        handle.register_write_checked(requested, False)
        register.write.assert_called_with(False)
        assert handle.register_read([requested]) == {requested: True}


@pytest.mark.parametrize("old,new", ANALOG_REGISTER_ALIASES.items())
def test_current_register_wins_when_both_firmware_names_exist(old, new):
    assert compatible_tag_registers({old: True}, {old, new}) == {new: True}


@pytest.mark.parametrize("old,new", REGISTER_ALIASES.items())
@pytest.mark.parametrize("names", ["old", "new", "both"])
def test_read_all_preserves_actual_names_and_values_and_exact_access(old, new, names):
    actual = {name: MagicMock() for name in (
        (old,) if names == "old" else (new,) if names == "new" else (old, new)
    )}
    expected = {name: index for index, name in enumerate(actual)}
    for name, register in actual.items():
        register.read.return_value = expected[name]
    handle = FpgaHandle.__new__(FpgaHandle)
    handle.configuration = {"detector_model": "SPAD Array"}
    handle.nifpga_obj = SimpleNamespace(registers=actual)
    assert handle.register_read_all() == expected
    for name, value in expected.items():
        assert handle.register_read([name]) == {name: value}
        for register in actual.values():
            register.reset_mock()
        handle.register_write_checked(name, True)
        actual[name].write.assert_called_once_with(True)
        for other in actual.keys() - {name}:
            actual[other].write.assert_not_called()


@pytest.mark.parametrize("old,new", ANALOG_REGISTER_ALIASES.items())
def test_metadata_names_remain_compatible(tmp_path, old, new):
    import h5py

    path = tmp_path / "analog.h5"
    manager = H5Manager(str(path), new_file=True)
    try:
        manager.metadata_add_dict("old", {old: True}, legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP)
        manager.metadata_add_dict("current", {new: True}, legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP)
    finally:
        manager.close()
    with h5py.File(path) as metadata:
        assert dict(metadata["old"].attrs) == dict(metadata["current"].attrs)
        assert bool(metadata["current"].attrs[LEGACY_H5_REGISTER_NAME_MAP[new]])
