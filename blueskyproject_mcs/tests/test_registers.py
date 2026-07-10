from brighteyes_bluesky.registers import REGISTER_ATTR_BY_NAME, REGISTER_SPECS, REGISTER_SPECS_BY_ATTR


def test_register_attrs_are_unique():
    assert len(REGISTER_SPECS) == len(REGISTER_SPECS_BY_ATTR)


def test_channel_families_are_expanded():
    for channel in range(8):
        assert f"AnalogOUT{channel}" in REGISTER_ATTR_BY_NAME
        assert f"AnalogSelector_{channel}" in REGISTER_ATTR_BY_NAME
        assert f"AnalogOutDC_{channel}" in REGISTER_ATTR_BY_NAME
        assert f"AnalogA{channel} invert" in REGISTER_ATTR_BY_NAME
        assert f"AnalogA{channel} integrate" in REGISTER_ATTR_BY_NAME
        assert f"AnalogIN{channel}" in REGISTER_ATTR_BY_NAME


def test_documented_core_registers_are_present():
    assert REGISTER_ATTR_BY_NAME["Run"] == "reg_run"
    assert REGISTER_ATTR_BY_NAME["#timebinsPerPixel"] == "reg_number_timebins_per_pixel"
    assert REGISTER_ATTR_BY_NAME["Offset/StartValue (V)"] == "reg_offset_start_value_v"
