"""DFD1/DFD2 acquisition adapter for the schema-4 Flare service."""

import numpy as np

from .dfd_format import Decoder, Layout, pack_sequence, pixel_cycles
from .dfd_scope_format import ScopeDecoder, ScopeLayout
from .v19 import scoped, record_count, supported, circular_counts
from ...lifetime import flim_parameters_from_3samples, flim_map_to_hcl


def is_dfd(configuration):
    return configuration.get("acquisition_mode") == "dfd"


REFERENCE_FACTOR = "dfd_reference_histogram_decimation_factor"
REFERENCE_METADATA = (REFERENCE_FACTOR, "excitation_calibration_decimation_factor", "reference_histogram_counting")
ALIGNMENT_METADATA = (
    "excitation_reference_source", "excitation_reference_requested_source",
    "excitation_reference_pending", "excitation_reference_status", "excitation_reference_ready",
    "excitation_reference_fault", "excitation_alignment_generation",
    "excitation_phase_offset_bins", "excitation_reference_span_bins",
    "excitation_phase_residual", "excitation_phase_residual_valid",
    "excitation_phase_registration", "excitation_phase_integer_correction_applied",
)


def reference_configuration(configuration, firmware):
    """Only send the optional factor to firmware advertising support."""
    result = dict(configuration)
    if firmware.get("board_capabilities", 0) & 0x400:
        result.setdefault(REFERENCE_FACTOR, 65535)
    else:
        result.pop(REFERENCE_FACTOR, None)
    return result


def sequence_from_gui(values, slots=6):
    """Legacy 0/off, 1..4/laser selections become four-bit slot masks."""
    selections = [int(values.get(f"laser_sequence_{i}", 0)) for i in range(1, 13)]
    if any(value not in range(5) for value in selections):
        raise ValueError("Laser sequence selections must be 0 (off) or L1..L4")
    if any(selections[slots:]):
        raise ValueError(f"Flare has {slots} sequence slots; clear slots {slots + 1}..12")
    masks = [0 if value == 0 else 1 << (value - 1) for value in selections[:slots]]
    pack_sequence(masks, slots)
    return masks


def layout_for(configuration):
    if scoped(configuration):
        if "stream_format" in configuration:
            return ScopeLayout.from_metadata(configuration)
        return ScopeLayout(configuration["channels"], record_count(configuration))
    if "stream_format" in configuration:
        return Layout.from_metadata(configuration)
    return Layout(configuration["channels"], **{
        key: configuration[key] for key in ("pixels", "lines", "frames", "repetitions")
    })


def dfd_configuration(normal, values, *, firmware=None):
    c = dict(normal)
    if not supported(firmware or {}) and any(float(values.get(key, 0)) for key in ("range_z", "offset_z_um", "offsetExtra_z")):
        raise ValueError("Flare DFD configuration currently requires Z range and offsets at zero")
    c.update(
        acquisition_mode="dfd", packet_records=c.pop("packet_bins"),
        dfd_trigger="pixel_end", dfd_clock_profile="40MHz_91",
        dfd_dwell_time_cycles_120mhz=0,
        dfd_reference_enable=int(bool(values.get("DFD_laser_debug", False))),
        laser_excitation_sequence=sequence_from_gui(values),
        laser_enable_mask=sum(1 << i for i in range(4) if values.get(f"laser_{i + 1}_enable")),
    )
    c[REFERENCE_FACTOR] = values.get(REFERENCE_FACTOR, 65535)
    validate_dfd_request(c)
    return c


def validate_dfd_request(c):
    from .config import validate_configuration

    normal = {key: c[key] for key in (
        "pixels", "lines", "frames", "repetitions", "bins_per_pixel", "dwell", "channels",
        "dummy", "x_start", "x_step", "y_start", "y_step",
    )}
    normal["packet_bins"] = c["packet_records"]
    normal["bins_per_pixel"] = 1  # DFD emits one record per pixel, not per scan bin.
    validate_configuration(normal)
    layout = layout_for(c)
    if c["packet_records"] > layout.max_packet_records:
        raise ValueError(f"DFD permits at most {layout.max_packet_records} records per packet")
    pack_sequence(c["laser_excitation_sequence"], 6)
    pixel_cycles(c["dwell"], c["bins_per_pixel"])
    if c["dfd_trigger"] != "pixel_end" or c["dfd_clock_profile"] != "40MHz_91":
        raise ValueError("The current Flare GUI uses pixel-end timing and the 40MHz_91 profile")
    for key, high in (("dfd_reference_enable", 1), ("laser_enable_mask", 15)):
        if type(c[key]) is not int or not 0 <= c[key] <= high:
            raise ValueError(f"Invalid {key}")
    if REFERENCE_FACTOR in c:
        factor = c[REFERENCE_FACTOR]
        if type(factor) is not int or not 1 <= factor <= 65535:
            raise ValueError("Reference decimation must be an integer in 1..65535")
    return dict(c)


def validate_accepted(requested, accepted, clock_hz):
    layout = Layout.from_metadata(accepted)
    requested_layout = layout_for(requested)
    if (layout.detector_channels != requested_layout.detector_channels or
        layout.total_records != requested_layout.total_records) or any(
        accepted.get("holdoff_cycles" if k == "detector_fpga_holdoff_cycles" else k) != v
        for k, v in requested.items()
    ):
        raise ValueError("Accepted Flare DFD configuration differs from the request")
    expected = dict(
        sys_hz=clock_hz, dma_hz=100000000, fast_exc_hz=240000000,
        laser_hz=40000000, histogram_bins=91, laser_slots=6, record_unit="pixel",
        holdoff_clock="clk_sampling", reference_enabled=bool(requested["dfd_reference_enable"]),
        pixel_sys_cycles=pixel_cycles(requested["dwell"], requested["bins_per_pixel"]),
    )
    if any(accepted.get(key) != value for key, value in expected.items()):
        raise ValueError("Flare DFD timing/profile disagrees with the requested acquisition")
    if accepted.get("sampling_hz_num") != 3640000000 or accepted.get("sampling_hz_den") != 9:
        raise ValueError("Unsupported DFD sampling clock")
    result = dict(accepted)
    if REFERENCE_FACTOR in accepted:
        factor = accepted[REFERENCE_FACTOR]
        if type(factor) is not int or not 1 <= factor <= 65535:
            raise ValueError("Invalid accepted reference decimation")
        if (type(accepted.get("excitation_calibration_decimation_factor")) is not int or
            accepted["excitation_calibration_decimation_factor"] != 1 or
            accepted.get("reference_histogram_counting") not in (
                "first_then_every_nth_raw_reference_edge", "legacy_shared_detector_holdoff")):
            raise ValueError("Invalid reference counting metadata")
        if accepted["reference_histogram_counting"] == "legacy_shared_detector_holdoff" and factor != 1:
            raise ValueError("Legacy reference counting requires factor 1")
    else:
        result.update({REFERENCE_FACTOR: 1, "excitation_calibration_decimation_factor": 1,
                       "reference_histogram_counting": "legacy_shared_detector_holdoff"})
    return result


class FlareDfdDecoder:
    def __init__(self, configuration, run_id):
        self.configuration = configuration
        self.scoped = scoped(configuration)
        self.layout = layout_for(configuration)
        self.decoder = (ScopeDecoder(self.layout, run_id, configuration.get("trajectory_id", 0))
                        if self.scoped else Decoder(self.layout, run_id))
        self.expected_bins = self.layout.total_records
        self.bin_bytes = self.layout.record_bytes
        self.channels = self.layout.stream_channels
        self.partial_records = []
        self.windows = []

    @property
    def index(self):
        return self.decoder.records

    def feed(self, chunk):
        counts = []
        self.windows = []
        for record in self.decoder.feed(chunk):
            if self.scoped:
                self._validate_window(record)
                self.windows.append(record)
            if record.partial:
                self.partial_records.append(record.ordinal if self.scoped else record.pixel_index)
            counts.append(record.counts(self.layout))
        if not counts:
            return np.empty((0, 91, self.channels), dtype=np.uint32 if self.scoped else np.uint16)
        return np.stack(counts)

    def _validate_window(self, record):
        c = self.configuration
        if (record.scope != c["dfd_scope"] or record.requested_boundaries != c["dfd_trigger_group_count"]):
            raise ValueError("DFD3 scope/group differs from accepted metadata")
        # The UI requests point scope/group one, preserving every circular visit.
        if record.scope != "circular_point" or record.requested_boundaries != 1:
            raise ValueError("This acquisition requires ungrouped point-resolved DFD3")
        n = record.ordinal
        points, circles = circular_counts(c)
        coordinates = []
        for count in (points, circles, c["pixels"], c["lines"], c["frames"], c["repetitions"]):
            coordinates.append(n % count)
            n //= count
        point, circle, x, y, z, rep = coordinates
        first = (x, y, z, rep, point, circle, 0)
        last = (*first[:-1], c["bins_per_pixel"] - 1)
        ticks = c["dwell"] * c["bins_per_pixel"]
        if (record.stopped or record.partial or record.completed_boundaries != 1 or
                record.first_coordinates != first or record.last_coordinates != last or
                record.first_tick != record.ordinal * ticks or record.last_tick != (record.ordinal + 1) * ticks):
            raise ValueError("DFD3 point exposure or coordinates differ from accepted geometry")

    def finish(self, *, cancelled=False):
        return self.decoder.finish(cancelled=cancelled)


class DfdPreview:
    def __init__(self, configuration, image):
        self.configuration = configuration
        self.image = image
        self.hcl = np.zeros((*image.shape, 3), dtype=float)
        self.rgb = np.zeros((*image.shape, 3), dtype=np.uint64)
        self.hist_live = np.zeros(91, dtype=np.uint64)
        self.hist_sum = np.zeros(91, dtype=np.uint64)
        self.selection = None
        self.live_records = self.hist_records = 0
        self.live_seconds = self.hist_seconds = 0.0

    def update(self, counts, index, selection, *, windows=None):
        channels = self.configuration["channels"]
        if selection != self.selection:
            self.image.fill(0)
            self.hcl.fill(0)
            self.rgb.fill(0)
            self.hist_sum.fill(0)
            self.hist_records = 0
            self.hist_seconds = 0.0
            self.selection = selection
        selected = tuple(range(channels)) if selection is None else tuple(selection)
        if any(type(i) is not int or not 0 <= i < self.configuration["stream_channels"] for i in selected):
            raise ValueError("Selected channel is outside the negotiated DFD layout")
        histogram = counts[:, :, selected].sum(axis=2, dtype=np.uint64)
        self.hist_live = histogram.sum(axis=0, dtype=np.uint64)
        self.hist_sum += self.hist_live
        self.live_records = len(counts)
        self.hist_records += len(counts)
        if windows is not None:
            self.live_seconds = sum(w.last_tick - w.first_tick for w in windows) / self.configuration["sys_hz"]
            self.hist_seconds += self.live_seconds
        rgb = np.stack([part.sum(axis=1, dtype=np.uint64) for part in (
            histogram[:, :30], histogram[:, 30:60], histogram[:, 60:],
        )], axis=-1)
        tau, brightness, quality, valid = flim_parameters_from_3samples(
            *rgb.T, T_cycle=1 / self.configuration["laser_hz"],
            sample_idx=np.array([14.5, 44.5, 75.0]),
            peak_idx=int(self.hist_sum.argmax()), total_bins=91,
        )
        hcl = np.stack(flim_map_to_hcl(tau, brightness, quality, valid, 0, 1), axis=-1)
        sums = histogram.sum(axis=1, dtype=np.uint64)
        # Keep only the last visit to each pixel when a batch crosses frames.
        # Unique indices make the final-write behavior explicit without a
        # Python loop over every pixel in the incoming batch.
        visits = int(np.prod(circular_counts(self.configuration))) if scoped(self.configuration) else 1
        if visits > 1:
            # Accumulate circular point visits into the displayed raster pixel.
            from ...flare import _update_preview_image
            _update_preview_image(self.image, sums, index, visits)
            for channel in range(3):
                _update_preview_image(self.rgb[:, :, channel], rgb[:, channel], index, visits)
            pixels = np.unique((index + np.arange(len(counts))) // visits % self.image.size)
            y, x = np.divmod(pixels, self.image.shape[1])
            tau, brightness, quality, valid = flim_parameters_from_3samples(
                *self.rgb[y, x].T, T_cycle=1 / self.configuration["laser_hz"],
                sample_idx=np.array([14.5, 44.5, 75.0]),
                peak_idx=int(self.hist_sum.argmax()), total_bins=91,
            )
            self.hcl[y, x] = np.stack(flim_map_to_hcl(tau, brightness, quality, valid, 0, 1), axis=-1)
            return sums
        first = max(0, len(counts) - self.image.size)
        pixel = (index + np.arange(first, len(counts))) % self.image.size
        y, x = np.divmod(pixel, self.image.shape[1])
        self.image[y, x] = sums[first:]
        self.rgb[y, x] = rgb[first:]
        self.hcl[y, x] = hcl[first:]
        return sums

    def snapshot(self):
        return dict(
            dfd_hist_live=self.hist_live.copy(), dfd_hist_sum=self.hist_sum.copy(),
            hcl_image=self.hcl.copy(), rgb_image=self.rgb.copy(),
            dfd_laser_hz=self.configuration["laser_hz"], dfd_bins=91,
            dfd_live_records=self.live_records, dfd_hist_records=self.hist_records,
            **(dict(dfd_live_seconds=self.live_seconds, dfd_hist_seconds=self.hist_seconds)
               if scoped(self.configuration) else {}),
            dfd_layout={key: self.configuration[key] for key in (
                "stream_format", "stream_format_version", "detector_channels", "stream_channels",
                "reference_channel_index", "extra_channel_index", "extra_channel_physical_io",
                *REFERENCE_METADATA, *ALIGNMENT_METADATA,
            ) if key in self.configuration},
        )
