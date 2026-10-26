"""DFD1 acquisition adapter for the schema-4 Flare service (fc5f8a9)."""

import numpy as np

from .dfd_format import Decoder, Layout, pack_sequence, pixel_cycles
from ...lifetime import flim_parameters_from_3samples, flim_map_to_hcl


def is_dfd(configuration):
    return configuration.get("acquisition_mode") == "dfd"


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
    return Layout(configuration["channels"], **{
        key: configuration[key] for key in ("pixels", "lines", "frames", "repetitions")
    })


def dfd_configuration(normal, values):
    c = dict(normal)
    if any(float(values.get(key, 0)) for key in ("range_z", "offset_z_um", "offsetExtra_z")):
        raise ValueError("Flare DFD configuration currently requires Z range and offsets at zero")
    c.update(
        acquisition_mode="dfd", packet_records=c.pop("packet_bins"),
        dfd_trigger="pixel_end", dfd_clock_profile="40MHz_91",
        dfd_dwell_time_cycles_120mhz=0,
        dfd_reference_enable=int(bool(values.get("DFD_laser_debug", False))),
        laser_excitation_sequence=sequence_from_gui(values),
        laser_enable_mask=sum(1 << i for i in range(4) if values.get(f"laser_{i + 1}_enable")),
    )
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
    return dict(c)


def validate_accepted(requested, accepted, clock_hz):
    layout = Layout.from_metadata(accepted)
    if layout != layout_for(requested) or any(
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
    return dict(accepted)


class FlareDfdDecoder:
    def __init__(self, configuration, run_id):
        self.layout = Layout.from_metadata(configuration)
        self.decoder = Decoder(self.layout, run_id)
        self.expected_bins = self.layout.total_records
        self.bin_bytes = self.layout.record_bytes
        self.channels = self.layout.stream_channels
        self.partial_records = []

    @property
    def index(self):
        return self.decoder.records

    def feed(self, chunk):
        counts = []
        for record in self.decoder.feed(chunk):
            if record.partial:
                self.partial_records.append(record.pixel_index)
            counts.append(record.counts(self.layout))
        if not counts:
            return np.empty((0, 91, self.channels), dtype=np.uint16)
        return np.stack(counts)

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

    def update(self, counts, index, selection):
        channels = self.configuration["channels"]
        if selection != self.selection:
            self.image.fill(0)
            self.hcl.fill(0)
            self.rgb.fill(0)
            self.hist_sum.fill(0)
            self.hist_records = 0
            self.selection = selection
        detector = counts[:, :, :channels]
        histogram = (detector if selection is None else detector[:, :, selection]).sum(axis=2, dtype=np.uint64)
        self.hist_live = histogram.sum(axis=0, dtype=np.uint64)
        self.hist_sum += self.hist_live
        self.live_records = len(counts)
        self.hist_records += len(counts)
        rgb = np.stack([part.sum(axis=1, dtype=np.uint64) for part in (
            histogram[:, :30], histogram[:, 30:60], histogram[:, 60:],
        )], axis=-1)
        tau, brightness, quality, valid = flim_parameters_from_3samples(
            *rgb.T, T_cycle=1 / self.configuration["laser_hz"],
            sample_idx=np.array([14.5, 44.5, 75.0]),
            peak_idx=int(self.hist_sum.argmax()), total_bins=91,
        )
        hcl = np.stack(flim_map_to_hcl(tau, brightness, quality, valid, 0, 1), axis=-1)
        for offset in range(len(counts)):
            pixel = (index + offset) % self.image.size
            y, x = divmod(pixel, self.image.shape[1])
            self.image[y, x] = histogram[offset].sum(dtype=np.uint64)
            self.rgb[y, x] = rgb[offset]
            self.hcl[y, x] = hcl[offset]
        return histogram.sum(axis=1, dtype=np.uint64)

    def snapshot(self):
        return dict(
            dfd_hist_live=self.hist_live.copy(), dfd_hist_sum=self.hist_sum.copy(),
            hcl_image=self.hcl.copy(), rgb_image=self.rgb.copy(),
            dfd_laser_hz=self.configuration["laser_hz"], dfd_bins=91,
            dfd_live_records=self.live_records, dfd_hist_records=self.hist_records,
        )
