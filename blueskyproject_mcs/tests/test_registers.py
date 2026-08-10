from brighteyes_bluesky.registers import REGISTER_ATTR_BY_NAME, REGISTER_SPECS, REGISTER_SPECS_BY_ATTR


def test_register_attrs_are_unique():
    assert len(REGISTER_SPECS) == len(REGISTER_SPECS_BY_ATTR)


def test_channel_families_are_expanded():
    for channel in range(8):
        assert f"analog_output_{channel}_volts" in REGISTER_ATTR_BY_NAME
        assert f"analog_output_{channel}_source_selector" in REGISTER_ATTR_BY_NAME
        assert f"analog_output_{channel}_dc_volts" in REGISTER_ATTR_BY_NAME
        assert f"analog_a_channel_{channel}_invert_enable" in REGISTER_ATTR_BY_NAME
        assert f"analog_a_channel_{channel}_integrate_enable" in REGISTER_ATTR_BY_NAME
        assert f"analog_input_{channel}_volts" in REGISTER_ATTR_BY_NAME


def test_documented_core_registers_are_present():
    assert REGISTER_ATTR_BY_NAME["start_command"] == "reg_start_command"
    assert (
        REGISTER_ATTR_BY_NAME["max_time_bins_per_pixel"]
        == "reg_max_time_bins_per_pixel"
    )
    assert (
        REGISTER_ATTR_BY_NAME["axis_start_offset_volts"]
        == "reg_axis_start_offset_volts"
    )
