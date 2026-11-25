"""Compatibility defaults for tag output controls introduced in MCSV2_1."""

from .register_names import (
    ANALOG_REGISTER_ALIASES,
    TAG_REGISTER_ALIASES,
    normalize_register_names,
    resolve_register_name,
)

MCSV2_1_TAG_DEFAULTS = {
    "tag_y_clock_duration_cycles": 0,
    "tag_z_clock_duration_cycles": 0,
    "tag_x_clock_invert": False,
    "tag_y_clock_invert": False,
    "tag_z_clock_invert": False,
    "tag_exclude_first_x": False,
    "tag_exclude_first_y": False,
    "tag_exclude_first_y_for_x": False,
    "tag_exclude_last_x": False,
    "tag_exclude_last_y": False,
    "tag_exclude_last_y_for_x": False,
}

REMOVED_TAG_REGISTERS = frozenset(("tag_yz_xor_x", "tag_yz_xor_x_invert"))


def normalize_tag_registers(registers):
    """Use current register names; explicit canonical values take precedence."""
    return normalize_register_names({
        name: value for name, value in registers.items() if name not in REMOVED_TAG_REGISTERS
    })


def compatible_tag_registers(registers, available_registers):
    """Omit unsupported defaults; reject settings that need newer firmware."""
    result = normalize_tag_registers(registers)
    for name in ANALOG_REGISTER_ALIASES.values():
        if name in result:
            physical_name = resolve_register_name(name, available_registers)
            if physical_name != name:
                result[physical_name] = result.pop(name)
    for name, default in MCSV2_1_TAG_DEFAULTS.items():
        if name not in result or name in available_registers:
            continue
        alias = next((old for old, new in TAG_REGISTER_ALIASES.items()
                      if new == name and old in available_registers), None)
        if alias is not None:
            result[alias] = result.pop(name)
            continue
        if result[name] is not None and result[name] != default:
            raise ValueError(
                f"Register {name!r} requires MCSV2_1 with this register; "
                "the selected bitfile does not expose it."
            )
        del result[name]
    return result
