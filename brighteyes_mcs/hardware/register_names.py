"""Canonical register names and aliases for earlier firmware interfaces."""


TAG_REGISTER_ALIASES = {
    "tag_clock_invert": "tag_x_clock_invert",
    "tag_exclude_last_for_x": "tag_exclude_last_y_for_x",
}
ANALOG_REGISTER_ALIASES = {
    f"analog_a_channel_{channel}_{option}_enable":
    f"analog_channel_{channel}_{option}_enable"
    for channel in range(8)
    for option in ("integrate", "invert")
}
REGISTER_ALIASES = {**TAG_REGISTER_ALIASES, **ANALOG_REGISTER_ALIASES}


def normalize_register_names(registers):
    """Migrate aliases; explicit canonical values take precedence."""
    result = dict(registers)
    for old, new in REGISTER_ALIASES.items():
        if old in result:
            value = result.pop(old)
            result.setdefault(new, value)
    return result


def resolve_register_name(name, available_registers):
    """Use an exact FPGA name first; resolve aliases only when it is absent."""
    if name in available_registers:
        return name
    name = REGISTER_ALIASES.get(name, name)
    if name in available_registers:
        return name
    return next(
        (old for old, new in REGISTER_ALIASES.items()
         if new == name and old in available_registers),
        name,
    )
