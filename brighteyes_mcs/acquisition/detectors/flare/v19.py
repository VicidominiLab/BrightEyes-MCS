"""Capability-gated firmware 1.9 single-output scans with PL circular arrays."""

import math

from .dfd_scope_format import ScopeLayout


CIRCULAR_FIELDS = {
    "circular_scan_enable", "max_circular_point", "max_circular_repetition",
    "circular_scan_coordinate_units", *(f"circular_scan_{axis}_volts" for axis in "xyz"),
}
FIELDS = CIRCULAR_FIELDS | {
    "acquisition_mode", "dma1_stream_enable", "dma2_stream_enable", "scan_position_source",
    "dfd_scope", "dfd_trigger_group_count", "dfd_count_bits", "z_start", "z_step",
}
COUNTING_FIELDS = {"physical_mask", "detector_fpga_holdoff_cycles", "laser_enable_mask", "laser_excitation_sequence"}


def supported(firmware):
    return firmware.get("multi_dma_supported") is True and firmware.get("multi_dma_abi_version") == 3


def scoped(configuration):
    # Common accepted intensity metadata also carries the inactive DFD settings.
    if "stream_format" in configuration:
        return configuration["stream_format"] == "DFD3"
    return configuration.get("acquisition_mode") == "dfd" and configuration.get("dfd_count_bits") == 32


def circular_counts(c):
    if not c.get("circular_scan_enable"):
        return 1, 1
    return c["max_circular_point"], c["max_circular_repetition"]


def ordinary_bins(c):
    return c.get("max_time_bins_per_pixel", c["bins_per_pixel"])


def expanded_bins(c):
    return ordinary_bins(c) * math.prod(circular_counts(c))


def record_count(c):
    if "total_records" in c:
        return c["total_records"]
    visits = math.prod(c[k] for k in ("pixels", "lines", "frames", "repetitions"))
    return visits * (math.prod(circular_counts(c)) if scoped(c) else expanded_bins(c))


def configure(c, values, firmware):
    """Send no new keys to older services, including false capability flags."""
    if not supported(firmware):
        if values.get("circular_active"):
            raise ValueError("PL circular scanning requires FLARE multi-DMA ABI 3")
        return c
    dfd = c.get("acquisition_mode") == "dfd"
    mode = "dfd" if dfd else "normal"
    if mode not in firmware.get("supported_acquisition_modes", []):
        raise ValueError(f"Firmware does not advertise {mode} acquisition")
    c = dict(c, acquisition_mode=mode, dma1_stream_enable=int(not dfd),
             dma2_stream_enable=int(dfd), scan_position_source="PL_SCAN")
    enabled = bool(values.get("circular_active"))
    points = int(values.get("circular_points", 1)) if enabled else 1
    circles = int(values.get("circular_repetition", 1)) if enabled else 1
    if enabled:
        if (firmware.get("circular_scan_array_capacity", 0) < points or
                firmware.get("circular_scan_coordinate_units") != "dac_counts"):
            raise ValueError("Firmware does not advertise the requested native circular arrays")
    c.update(circular_scan_enable=int(enabled), max_circular_point=points,
             max_circular_repetition=circles, circular_scan_coordinate_units="dac_counts")
    for axis in "xyz":
        volts = values.get(f"circular_scan_{axis}_volts", [0.0] * points)
        if len(volts) != points or any(not math.isfinite(float(v)) for v in volts):
            raise ValueError(f"Circular {axis.upper()} requires one finite voltage per point")
        c[f"circular_scan_{axis}_volts"] = [round(float(v) * 32768 / 10) for v in volts]
    if dfd:
        if ("DFD3" not in firmware.get("supported_dfd_formats", []) or
                32 not in firmware.get("dfd_count_bits", []) or
                "circular_point" not in firmware.get("dfd_scopes", [])):
            raise ValueError("DFD requires advertised DFD3 uint32 circular-point scope")
        c.update(dfd_scope="circular_point", dfd_trigger_group_count=1, dfd_count_bits=32)
        # The V3 service accepts old trigger aliases but does not echo them.
        c.pop("dfd_trigger", None)
        c.pop("dfd_dwell_time_cycles_120mhz", None)
    elif any(f"laser_{i + 1}_enable" in values for i in range(4)):
        c["laser_enable_mask"] = sum(1 << i for i in range(4) if values.get(f"laser_{i + 1}_enable"))
    return c


def validate_request(c):
    from .config import _integer, validate_configuration
    from .dfd import validate_dfd_request

    dfd = c.get("acquisition_mode") == "dfd"
    if c.get("acquisition_mode") not in ("normal", "dfd"):
        raise ValueError("FLARE currently supports normal or DFD single-output acquisition")
    if (c.get("dma1_stream_enable"), c.get("dma2_stream_enable")) != ((0, 1) if dfd else (1, 0)):
        raise ValueError("Normal requires DMA1 only; DFD requires DMA2 only")
    if c.get("scan_position_source") != "PL_SCAN":
        raise ValueError("Only PL_SCAN position arrays are supported")
    _integer("circular_scan_enable", c["circular_scan_enable"], 0, 1)
    _integer("max_circular_point", c["max_circular_point"], 1, 32)
    _integer("max_circular_repetition", c["max_circular_repetition"], 1, 2**31 - 1)
    if c["circular_scan_coordinate_units"] != "dac_counts":
        raise ValueError("Circular array units must be native dac_counts")
    for axis in "xyz":
        array = c[f"circular_scan_{axis}_volts"]
        if not isinstance(array, list) or len(array) != c["max_circular_point"]:
            raise ValueError("Circular arrays must contain max_circular_point entries")
        for value in array:
            _integer("circular coordinate", value, -(2**19), 2**19 - 1)
        if math.prod(circular_counts(c)) != 1:
            start, step = c.get(f"{axis}_start", 0), c.get(f"{axis}_step", 0)
            end = start + (c[{"x": "pixels", "y": "lines", "z": "frames"}[axis]] - 1) * step
            if min(start, end) + min(array) < -32768 or max(start, end) + max(array) > 32767:
                raise ValueError(f"Circular {axis.upper()} scan exceeds physical DAC range")
    base = {k: v for k, v in c.items() if k not in FIELDS}
    if dfd:
        if (c.get("dfd_scope"), c.get("dfd_trigger_group_count"), c.get("dfd_count_bits")) != ("circular_point", 1, 32):
            raise ValueError("The current GUI requires ungrouped circular-point DFD3 windows")
        base["acquisition_mode"] = "dfd"
        base.setdefault("dfd_trigger", "pixel_end")
        base.setdefault("dfd_dwell_time_cycles_120mhz", 0)
        validate_dfd_request(base)
        if c["packet_records"] > ScopeLayout(c["channels"], record_count(c)).max_packet_records:
            raise ValueError("DFD3 packet exceeds the DMA byte limit")
    else:
        validate_configuration({k: v for k, v in base.items() if k not in COUNTING_FIELDS})
    if "physical_mask" in c:
        mask = c["physical_mask"]
        if not isinstance(mask, list) or len(mask) != 2:
            raise ValueError("Physical mask requires two words")
        for value, high in zip(mask, (0x1ffffff, 0) if c["channels"] == 25 else (0xffffffff, 0x1ffff), strict=True):
            _integer("physical mask", value, 0, high)
    if "detector_fpga_holdoff_cycles" in c:
        _integer("detector holdoff", c["detector_fpga_holdoff_cycles"], 0, 65535)
    if "laser_enable_mask" in c:
        _integer("laser enable mask", c["laser_enable_mask"], 0, 15)
    for key in ("z_start", "z_step"):
        if key in c:
            _integer(key, c[key], -(2**31), 2**31 - 1)
    if record_count(c) > 2**32 - 1 or expanded_bins(c) > 2**31 - 1:
        raise ValueError("Circular scan exceeds the firmware record/count limits")
    return dict(c)


def validate_accepted(requested, accepted, clock_hz=None):
    """Retain the accepted layout while verifying the selected DMA and geometry."""
    validate_request(requested)
    for key, value in requested.items():
        actual = accepted.get(key)
        if key == "bins_per_pixel" and requested["acquisition_mode"] == "normal":
            actual = accepted.get("max_time_bins_per_pixel")
        if actual != value:
            raise ValueError(f"Accepted FLARE configuration differs at {key}")
    if not accepted.get("configuration_id"):
        raise ValueError("Missing accepted FLARE configuration identity")
    for key, value in zip(("effective_max_circular_point", "effective_max_circular_repetition"), circular_counts(requested), strict=True):
        if accepted.get(key) != value:
            raise ValueError("Accepted circular dimensions differ from request")
    count = record_count(requested)
    dfd = requested["acquisition_mode"] == "dfd"
    size = ScopeLayout(requested["channels"], count).record_bytes if dfd else (120 if requested["channels"] == 25 else 216)
    if (accepted.get("dma"), accepted.get("active_stream_mask"), accepted.get("total_records"), accepted.get("total_bytes"), accepted.get("record_bytes")) != (2 if dfd else 1, 2 if dfd else 1, count, count * size, size):
        raise ValueError("Accepted FLARE DMA or stream lengths disagree with requested scan")
    if not dfd and accepted.get("bins_per_pixel") != expanded_bins(requested):
        raise ValueError("Accepted intensity expansion disagrees with circular geometry")
    if dfd:
        ScopeLayout.from_metadata(accepted)
        if accepted.get("laser_hz") != 40000000 or (clock_hz is not None and accepted.get("sys_hz") != clock_hz):
            raise ValueError("Unsupported DFD3 clock profile")
        if accepted.get("excitation_reference_ready") is False or accepted.get("excitation_reference_fault", 0):
            raise ValueError("DFD3 reference is not ready; reset and reconfigure")
        if accepted.get("reference_channel_index") != requested["channels"] + 1 or accepted.get("channel_roles") != ["detector"] * requested["channels"] + ["extra", "laser_reference"]:
            raise ValueError("Invalid DFD3 channel roles")
    return dict(accepted)


def validate_stream(run, accepted):
    name = "dfd" if scoped(accepted) else "intensity"
    streams = run.get("streams", {})
    if set(streams) != {name}:
        raise ValueError("FLARE started an unexpected set of DMA streams")
    acquisition = streams[name].get("acquisition", {})
    for key, value in accepted.items():
        if acquisition.get(key) != value:
            raise ValueError(f"Started FLARE stream differs at {key}")


def validate_completion(status, run_id, accepted):
    run = status.get("stream") or {}
    validate_stream(run, accepted)
    name = "dfd" if scoped(accepted) else "intensity"
    stream = run["streams"][name]
    channel = status.get("channels", {}).get(name, {})
    if (run.get("run_id") != run_id or run.get("complete") is not True or
            stream.get("complete") is not True or
            stream.get("bytes_sent") != accepted["total_bytes"] or
            any(stream.get(k, 0) for k in ("stream_error", "acquisition_error")) or
            channel.get("error", 0) or status.get("positions", {}).get("error", 0)):
        raise ValueError("FLARE scan/DMA completion was not confirmed")
