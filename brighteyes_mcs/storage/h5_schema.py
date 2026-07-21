"""Constants and inspection helpers for the stable HDF5 0.0.1 contract."""

from __future__ import annotations

from typing import Any


DATA_FORMAT_VERSION = "0.0.1"
H5_METADATA_GROUPS = (
    "configurationSpadFCSmanager", "configurationFPGA",
    "configurationGUI", "configurationGUI_beforeStart",
)
RAW_METADATA_GROUP = "rawStreamAcquisition"


def legacy_gui_metadata(configuration, *, spad_array_model="SPAD Array"):
    """Map internal GUI names to the immutable public HDF5 attribute names."""

    payload = dict(configuration or {})
    for internal, public in {
        "spad_channels": "spad_number_of_channels",
        "spad_cmd_length": "spadCmdLength",
        "spad_cmd_data": "spadCmdData",
        "spad_cmd_invert": "spadCmdInvert",
    }.items():
        if internal in payload:
            payload[public] = payload.pop(internal)
    if payload.get("detector_model") == spad_array_model:
        payload.pop("detector_model")
    return payload


def legacy_raw_stream_metadata(
    acquisition,
    *,
    spad_channels,
    clock_base_mhz,
    raw_files,
    include_pi23=False,
):
    """Build the immutable ``rawStreamAcquisition`` attribute mapping.

    Keeping this mapping at the storage boundary prevents Qt code from owning
    details consumed by offline converters and older analysis software.
    """

    registers = acquisition.registers_configuration
    runtime = acquisition.shared_dict
    payload = {
        "enabled": True,
        "digital_fifo_present": "FIFO" in acquisition.activated_fifos_list,
        "analog_fifo_present": "FIFOAnalog" in acquisition.activated_fifos_list,
        "digital_channels": spad_channels,
        "digital_words_per_sample": 2 if spad_channels == 25 else 8,
        "analog_words_per_sample": 1,
        "effective_timebins_per_pixel": (
            registers.get("#timebinsPerPixel", 1)
            * registers.get("#circular_rep", 1)
            * registers.get("#circular_points", 1)
        ),
        "clock_base_mhz": clock_base_mhz,
        "clk_multiplier": acquisition.clk_multiplier,
        "dfd_shift": acquisition.dfd_shift,
        "snake_walk_xy": acquisition.snake_walk_xy,
        "snake_walk_z": acquisition.snake_walk_z,
        "dfd_activate": acquisition.DFD_Activate,
        "digital_raw_file": raw_files.get("FIFO", ""),
        "analog_raw_file": raw_files.get("FIFOAnalog", ""),
        "digital_raw_bytes": runtime.get("FIFO_bytes_written", 0),
        "analog_raw_bytes": runtime.get("FIFOAnalog_bytes_written", 0),
        "digital_expected_words": runtime.get("FIFO_expected_words", 0),
        "analog_expected_words": runtime.get("FIFOAnalog_expected_words", 0),
        "digital_expected_bytes": runtime.get("FIFO_expected_bytes", 0),
        "analog_expected_bytes": runtime.get("FIFOAnalog_expected_bytes", 0),
        "digital_actual_bytes_on_disk": runtime.get(
            "FIFO_actual_bytes_on_disk", 0
        ),
        "analog_actual_bytes_on_disk": runtime.get(
            "FIFOAnalog_actual_bytes_on_disk", 0
        ),
        "raw_writer_stop_reason": runtime.get("raw_writer_stop_reason", ""),
        "raw_writer_error": runtime.get("raw_writer_error", ""),
    }
    if include_pi23:
        payload.update(
            {
                "detector_model": acquisition.detector_model,
                "pi23_raw_stream_format": runtime.get(
                    "pi23_raw_stream_format", ""
                ),
            }
        )
    return payload


def describe_h5(h5file) -> dict[str, Any]:
    description: dict[str, Any] = {
        "root_attributes": {key: h5file.attrs[key] for key in sorted(h5file.attrs)},
        "objects": {},
    }
    for name in sorted(h5file.keys()):
        item = h5file[name]
        entry = {
            "attributes": {key: item.attrs[key] for key in sorted(item.attrs)},
            "kind": "dataset" if hasattr(item, "dtype") else "group",
        }
        if hasattr(item, "dtype"):
            entry.update({"shape": tuple(item.shape), "dtype": str(item.dtype)})
        description["objects"][name] = entry
    return description
