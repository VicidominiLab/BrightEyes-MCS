"""Settings and finite scan validation for the Flare REST protocol."""

from dataclasses import asdict, dataclass
import logging
import math


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FlareSettings:
    host: str = "mmskria3"
    port: int = 8081
    mode: str = "master"
    bind_host: str = "0.0.0.0"
    receiver_host: str = ""
    receiver_port: int = 9000
    packet_bins: int = 0  # Zero selects automatic sizing; positive values are manual.
    buffer_seconds: float = 0.25
    timeout_seconds: float = 2.0
    http_timeout_seconds: float = 5.0

    def validate(self):
        if not self.host.strip() or any(c in self.host for c in "/?#@"):
            raise ValueError("Flare host must be a hostname or IP address")
        for name, low, high in (
            ("port", 1, 65535),
            ("receiver_port", 0, 65535),
            ("packet_bins", 0, 4096),
        ):
            _integer(name, getattr(self, name), low, high)
        if self.mode not in ("master", "slave"):
            raise ValueError("Flare mode must be master or slave")
        for name in ("buffer_seconds", "timeout_seconds", "http_timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or not 0.001 <= value <= 3600:
                raise ValueError(f"{name} must be finite and between 0.001 and 3600")
        return self

    def legacy_values(self):
        return {f"flare_{key}": value for key, value in asdict(self).items()}

    @classmethod
    def from_legacy(cls, values):
        # Call only for Flare. Invalid dormant settings must not affect NI/PI.
        return cls(
            **{
                key: values[f"flare_{key}"]
                for key in cls.__dataclass_fields__
                if f"flare_{key}" in values
            }
        )


def _integer(name, value, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")


def validate_configuration(config):
    if "dma1_stream_enable" in config:
        from .v19 import validate_request
        return validate_request(config)
    if config.get("acquisition_mode") == "dfd":
        from .dfd import validate_dfd_request
        return validate_dfd_request(config)
    required = {
        "pixels",
        "lines",
        "frames",
        "repetitions",
        "bins_per_pixel",
        "dwell",
        "packet_bins",
        "channels",
        "dummy",
        "x_start",
        "x_step",
        "y_start",
        "y_step",
    }
    if set(config) != required:
        raise ValueError("Flare requires a complete supported scan configuration")
    for name in ("pixels", "lines", "frames", "repetitions", "bins_per_pixel"):
        _integer(name, config[name], 1, 2**31 - 1)
    _integer("dwell", config["dwell"], 32, 2**31 - 1)
    _integer("packet_bins", config["packet_bins"], 1, 4096)
    _integer("dummy", config["dummy"], 0, 1)
    _integer("channels", config["channels"], 25, 49)
    if config["channels"] not in (25, 49):
        raise ValueError("Flare supports exactly 25 or 49 channels")
    for axis, count in (("x", "pixels"), ("y", "lines")):
        for field in ("start", "step"):
            _integer(f"{axis}_{field}", config[f"{axis}_{field}"], -(2**31), 2**31 - 1)
        end = config[f"{axis}_start"] + (config[count] - 1) * config[f"{axis}_step"]
        if not -32768 <= config[f"{axis}_start"] <= 32767 or not -32768 <= end <= 32767:
            raise ValueError(f"{axis.upper()} scan exceeds the physical signed 16-bit DAC range")
    if total_bins(config) > 2**32 - 1:
        raise ValueError("Flare scan exceeds 4294967295 bins")
    return dict(config)


def total_bins(config):
    if "dma1_stream_enable" in config or config.get("stream_format") == "DFD3":
        from .v19 import record_count
        return record_count(config)
    return math.prod(
        config[k] for k in (("pixels", "lines", "frames", "repetitions") if config.get("acquisition_mode") == "dfd"
                           else ("pixels", "lines", "frames", "repetitions", "bins_per_pixel"))
    )


def stream_parameters(config):
    if config.get("acquisition_mode") == "dfd":
        from .dfd import layout_for
        return layout_for(config).record_bytes, config["dwell"] * config["bins_per_pixel"], config["packet_records"]
    return bin_bytes(config["channels"]), config["dwell"], config["packet_bins"]


def bin_bytes(channels):
    if channels not in (25, 49):
        raise ValueError("Unsupported Flare channel count")
    return 120 if channels == 25 else 216


def check_transport(config, clock_hz, settings):
    size, dwell, packet = stream_parameters(config)
    if "dma1_stream_enable" in config:
        if settings.buffer_seconds > 0.25:
            raise ValueError("FLARE 1.9 supports at most 0.25 seconds of buffering")
        # Firmware 1.9 negotiates its ring and permits one complete long window.
        return max(1, int(settings.buffer_seconds * clock_hz / (dwell * packet))) * packet * size
    slots = int(settings.buffer_seconds * clock_hz / (dwell * packet))
    capacity = slots * packet * size
    if slots < 1 or capacity > 256 * 1024 * 1024:
        raise ValueError("Flare buffer must fit at least one packet and at most 256 MiB")
    if slots < min(32, math.ceil(total_bins(config) / packet)):
        raise ValueError(
            "Flare buffer is too small for a DMA completion burst; reduce packet bins or increase buffer seconds"
        )
    return capacity


def automatic_packet_bins(config, clock_hz, settings):
    """Balance DMA overhead with latency and space for 32-descriptor bursts.

    Target 16 KiB per packet, or at least eight histogram records for DFD,
    capped at 2 ms of exposure (one record for slower scans). Reserve half
    the time-derived ring for scheduling jitter.
    This estimates batching, not the maximum sustainable hardware data rate.
    """
    size, dwell, _ = stream_parameters(config)
    target = max(8 if config.get("acquisition_mode") == "dfd" else 1,
                 math.ceil(16384 / size))
    latency_limit = max(1, int(0.002 * clock_hz / dwell))
    burst_limit = max(1, int(settings.buffer_seconds * clock_hz / (64 * dwell)))
    packet = min(target, latency_limit, burst_limit, total_bins(config), 4096, 8388607 // size)
    result = dict(config)
    result["packet_records" if config.get("acquisition_mode") == "dfd" else "packet_bins"] = packet
    check_transport(result, clock_hz, settings)
    log.info(
        "Flare automatic DMA packet: %d %s, %d bytes, %.3f ms exposure per packet",
        packet, "DFD records" if config.get("acquisition_mode") == "dfd" else "bins",
        packet * size, 1000 * packet * dwell / clock_hz,
    )
    return packet


def axis_registers_from_gui(values):
    """Convert position and range to the native signed DAC-count arrays."""
    starts, steps = [], []
    for axis, count_key in zip("xyz", ("nx", "ny", "nframe"), strict=True):
        calibration = float(values.get(f"calib_{axis}", 1))
        if not math.isfinite(calibration) or calibration == 0:
            raise ValueError(f"Invalid {axis.upper()} calibration in micrometres per volt")
        count = int(values[count_key])
        if count < 1:
            raise ValueError(f"Invalid {axis.upper()} pixel count")
        span = float(values.get(f"range_{axis}", 0)) / calibration
        start = (
            float(values.get(f"offset_{axis}_um", 0)) / calibration
            - 0.5 * span + float(values.get(f"offsetExtra_{axis}", 0))
        )
        step = span / count
        end = start + step * (count - 1)
        if not all(math.isfinite(v) for v in (start, step, end)):
            raise ValueError(f"{axis.upper()} scan contains non-finite coordinates")
        minimum = float(values.get(f"min_{axis}_V", -10))
        maximum = float(values.get(f"max_{axis}_V", 10))
        if min(start, end) < minimum or max(start, end) > maximum:
            log.warning(
                "%s scan exceeds the configured voltage limits "
                "(scan %.6g..%.6g V, configured %.6g..%.6g V); continuing with the requested scan",
                axis.upper(), min(start, end), max(start, end), minimum, maximum,
            )
        starts.append(round(start * 32768 / 10))
        steps.append(round(step * 32768 / 10))
    return {"axis_start_offset_volts": starts, "axis_calibration_volts_per_step": steps}


def configuration_from_gui(values, clock_hz, settings, *, preview=False, dummy=False, firmware=None):
    """Translate UI physical units without inheriting NI register encodings."""
    unsupported = [
        name
        for name in (
            "lissajous_active",
            "slave_mode_enable",
            "sw_trigger_enable",
        )
        if values.get(name)
    ]
    if unsupported:
        raise ValueError("Flare does not support: " + ", ".join(unsupported))
    c = {
        "pixels": int(values["nx"]),
        "lines": int(values["ny"]),
        "frames": int(values["nframe"]),
        "repetitions": 1 if preview else int(values["nrep"]),
        "bins_per_pixel": int(values["timebin_per_pixel"]),
        "dwell": round(float(values["time_resolution"]) * 1e-6 * clock_hz),
        "packet_bins": settings.packet_bins or 1,
        "channels": int(values["spad_channels"]),
        "dummy": int(dummy),
    }
    registers = axis_registers_from_gui(values)
    for index, axis in enumerate("xy"):
        c[f"{axis}_start"] = registers["axis_start_offset_volts"][index]
        c[f"{axis}_step"] = registers["axis_calibration_volts_per_step"][index]
    if values.get("DFD", values.get("dfd_enable", False)):
        from .dfd import dfd_configuration
        c = dfd_configuration(c, values, firmware=firmware)
    from .v19 import configure, supported
    c = configure(c, values, firmware or {})
    if supported(firmware or {}):
        c.update(z_start=registers["axis_start_offset_volts"][2], z_step=registers["axis_calibration_volts_per_step"][2])
    c = validate_configuration(c)
    if settings.packet_bins == 0:
        key = "packet_records" if c.get("acquisition_mode") == "dfd" else "packet_bins"
        c[key] = automatic_packet_bins(c, clock_hz, settings)
    return c
