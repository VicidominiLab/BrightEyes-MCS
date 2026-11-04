"""Firmware 1.9 wire, DMA selection, circular storage and failure acceptance."""

import copy
import struct
import threading
import socket

import h5py
import numpy as np
import pytest

from brighteyes_mcs.acquisition.detectors.flare.config import (
    FlareSettings, configuration_from_gui, total_bins,
)
from brighteyes_mcs.acquisition.detectors.flare import v19
from brighteyes_mcs.acquisition.detectors.flare.dfd import FlareDfdDecoder, layout_for
from brighteyes_mcs.acquisition.detectors.flare.decoder import FlareDecoder
from brighteyes_mcs.acquisition.detectors.flare.controls import FlareLiveControls
from brighteyes_mcs.acquisition.flare import FlareAcquisition
from brighteyes_mcs.storage.raw import convert_raw_acquisition
from test.test_flare import raw_fixture


FIRMWARE = dict(
    board_id=0x464c5234, schema_version=0x40000, clock_hz=100000000,
    multi_dma_supported=True, multi_dma_abi_version=3,
    supported_acquisition_modes=["normal", "dfd", "multi"],
    supported_dfd_formats=["DFD3"], dfd_count_bits=[32], dfd_scopes=["circular_point"],
    circular_scan_array_capacity=32, circular_scan_coordinate_units="dac_counts",
)


def request(dfd=True, channels=25, points=3, circles=2, **changes):
    values = dict(nx=2, ny=2, nframe=1, nrep=1, timebin_per_pixel=2,
                  time_resolution=50, spad_channels=str(channels), dfd_enable=dfd,
                  circular_active=True, circular_points=points, circular_repetition=circles,
                  circular_scan_x_volts=[0.01] * points,
                  circular_scan_y_volts=[-0.01] * points)
    values.update(changes)
    return configuration_from_gui(values, 100000000, FlareSettings(), firmware=FIRMWARE)


def accepted(c):
    dfd = c["acquisition_mode"] == "dfd"
    count = v19.record_count(c)
    points, circles = v19.circular_counts(c)
    result = dict(c, configuration_id="configuration-19", trajectory_id=0,
                  effective_max_circular_point=points, effective_max_circular_repetition=circles,
                  active_stream_mask=2 if dfd else 1, dma=2 if dfd else 1,
                  total_records=count, stream_format="DFD3" if dfd else "FLR4")
    if dfd:
        layout = layout_for(c)
        result.update(stream_format_version=3, count_bits=32, histogram_bins=91,
                      scope_header_words=16, stream_channels=channels_count(c) + 2,
                      detector_channels=channels_count(c), record_bytes=layout.record_bytes,
                      padded_channels=layout.padded_channels, reference_channel_index=channels_count(c) + 1,
                      extra_channel_index=channels_count(c), extra_channel_count=1, extra_channel_physical_io=False,
                      padding_channel_indices=list(range(layout.stream_channels, layout.padded_channels)),
                      channel_roles=["detector"] * channels_count(c) + ["extra", "laser_reference"],
                      laser_hz=40000000, pixel_sys_cycles=c["dwell"] * c["bins_per_pixel"],
                      sys_hz=100000000)
    else:
        result.update(record_bytes=120 if channels_count(c) == 25 else 216,
                      max_time_bins_per_pixel=c["bins_per_pixel"], bins_per_pixel=v19.expanded_bins(c),
                      dfd_count_bits=32, dfd_scope="circular_point", dfd_trigger_group_count=1)
    result["total_bytes"] = result["record_bytes"] * count
    return result


def channels_count(c):
    return c["channels"]


def record(c, ordinal=0, run_id=0x12345678):
    """Build SCP1/DFD3 directly from the documented wire words."""
    layout = layout_for(c)
    n = ordinal
    coords = []
    points, circles = v19.circular_counts(c)
    for count in (points, circles, c["pixels"], c["lines"], c["frames"], c["repetitions"]):
        coords.append(n % count)
        n //= count
    point, circle, x, y, z, rep = coords
    first = (x, y, z, rep, point, circle, 0)
    last = (*first[:-1], c["bins_per_pixel"] - 1)
    ticks = c["dwell"] * c["bins_per_pixel"]
    envelope = [0x53435031 << 32 | 16, run_id << 32 | ordinal, 5 << 32, 1 << 32 | 1,
                ordinal * ticks, (ordinal + 1) * ticks]
    envelope.extend(a << 32 | b for a, b in zip(first, last, strict=True))
    envelope.extend([0x44464433, 32 << 32 | 91, layout.payload_words << 32 | c["channels"]])
    inner = [0x44464433 << 32 | layout.stream_channels << 16 | 91, run_id << 32 | ordinal,
             x << 32 | y, z << 32 | rep, layout.payload_words << 32]
    data = np.full((91, layout.padded_channels), 70000 + ordinal, dtype="<u4")
    data[:, layout.stream_channels:] = 0
    return (struct.pack("<16Q", *envelope) + struct.pack("<5Q", *inner) + data.tobytes()
            + struct.pack("<Q", 0x4446445f454e4421)), data[:, :layout.stream_channels]


@pytest.mark.parametrize("dfd", [False, True])
def test_single_dma_mapping_native_arrays_and_no_position_stream(dfd):
    c = request(dfd)
    assert (c["dma1_stream_enable"], c["dma2_stream_enable"]) == ((0, 1) if dfd else (1, 0))
    assert c["scan_position_source"] == "PL_SCAN"
    assert c["circular_scan_x_volts"] == [33] * 3
    assert c["circular_scan_y_volts"] == [-33] * 3
    assert c["circular_scan_z_volts"] == [0] * 3
    assert total_bins(c) == (24 if dfd else 48)
    v19.validate_accepted(c, accepted(c))


def test_invalid_or_unadvertised_circular_geometry_is_rejected():
    for changes in (dict(points=33), dict(circles=0),
                    dict(circular_scan_x_volts=[float("nan")] * 3),
                    dict(circular_scan_x_volts=[11.0] * 3)):
        with pytest.raises(ValueError):
            request(**changes)
    c = request()
    for changes in (dict(dma1_stream_enable=1), dict(scan_position_source="PS_STREAM")):
        with pytest.raises(ValueError):
            v19.validate_request(dict(c, **changes))
    for field in ("multi_dma_supported", "multi_dma_abi_version", "dfd_count_bits", "dfd_scopes"):
        firmware = dict(FIRMWARE)
        firmware.pop(field)
        with pytest.raises(ValueError):
            configuration_from_gui(dict(nx=1, ny=1, nframe=1, nrep=1, timebin_per_pixel=2,
                                        time_resolution=50, spad_channels="25", circular_active=True,
                                        dfd_enable=True), 100000000, FlareSettings(), firmware=firmware)


@pytest.mark.parametrize("dfd", [False, True])
@pytest.mark.parametrize("points,circles,enabled,visits", [(1, 1, True, 1), (1, 4, True, 4), (3, 2, False, 1)])
def test_single_point_repetitions_and_disabled_bypass(dfd, points, circles, enabled, visits):
    c = request(dfd, points=points, circles=circles, circular_active=enabled,
                circular_scan_x_volts=[0.01] * (points if enabled else 1),
                circular_scan_y_volts=[0.01] * (points if enabled else 1))
    assert total_bins(c) == 4 * visits * (1 if dfd else 2)
    a = v19.validate_accepted(c, accepted(c))
    if dfd:
        decoder = FlareDfdDecoder(a, 0x12345678)
        decoder.feed(b"".join(record(a, i)[0] for i in range(a["total_records"])))
    else:
        decoder = FlareDecoder(a, 0x12345678)
        decoder.feed(raw_fixture(a, 0x12345678)[0])
    decoder.finish()


def test_circular_intensity_expanded_header_wraps_and_storage_keeps_ordinary_bins(tmp_path):
    from brighteyes_mcs.storage.flare import FlareRecording

    c = accepted(request(False, points=32, circles=3, timebin_per_pixel=3, nx=1, ny=1))
    assert c["bins_per_pixel"] == 288 and c["max_time_bins_per_pixel"] == 3
    raw, expected = raw_fixture(c, 0x12345678)
    decoder = FlareDecoder(c, 0x12345678)
    writer = FlareRecording(tmp_path / "wrap.h5", c)
    for offset in range(0, len(raw), 1013):
        index = decoder.index
        writer.append(index, decoder.feed(raw[offset:offset + 1013]))
    decoder.finish()
    writer.finish(dict(complete=True, validated_bins=decoder.index))
    with h5py.File(tmp_path / "wrap.h5") as output:
        assert output["data"].shape == (1, 1, 1, 1, 3, 32, 3, 25)
        np.testing.assert_array_equal(output["data"][:].reshape(expected.shape), expected)


@pytest.mark.parametrize("channels,size", [(25, 10368), (49, 19104)])
@pytest.mark.parametrize("fragment", [1, 127, 1703, 262144])
def test_dfd3_fragmented_counts_and_exposure_coordinates(channels, size, fragment):
    c = accepted(request(channels=channels, nx=1, ny=1))
    fixtures = [record(c, i) for i in range(c["total_records"])]
    raw = b"".join(r for r, _ in fixtures)
    decoder = FlareDfdDecoder(c, 0x12345678)
    batches = [decoder.feed(raw[i:i + fragment]) for i in range(0, len(raw), fragment)]
    decoder.finish()
    assert decoder.bin_bytes == size
    assert np.concatenate(batches).dtype == np.uint32
    np.testing.assert_array_equal(np.concatenate(batches), np.stack([counts for _, counts in fixtures]))


@pytest.mark.parametrize("offset", [0, 8, 12, 16, 24, 32, 40, 48, 104, 112, 120, 128, 136, 160, 10360])
def test_dfd3_rejects_corrupt_identity_layout_scope_exposure_padding_tail(offset):
    c = accepted(request(nx=1, ny=1, points=1, circles=1))
    raw = bytearray(record(c)[0])
    raw[offset] ^= 1
    with pytest.raises(ValueError):
        FlareDfdDecoder(c, 0x12345678).feed(raw)


class Service:
    def __init__(self, c, *, truncate=False, bad_stream=False, service_error=False):
        self.firmware = dict(FIRMWARE)
        self.c = c
        self.stream = None
        self.done = threading.Event()
        self.calls = []
        self.truncate, self.bad_stream, self.service_error = truncate, bad_stream, service_error

    def discover(self):
        return {"firmware": self.firmware}

    check_acquisition_support = require_idle = close = lambda self, **kw: None

    def read_all(self):
        return {}

    def read_register(self, name):
        assert name == "dfd_fault_flags"  # Run identity comes from common START.
        return {"value": 0}

    def configure(self, c):
        self.calls.append("configure")
        self.effective = accepted(c)
        return self.effective

    def stream_settings(self, destination, *, stream):
        self.calls.append(stream)
        assert stream == ("dfd" if self.c["acquisition_mode"] == "dfd" else "intensity")
        self.destination = destination
        return destination

    def command(self, name):
        self.calls.append(name)
        if name != "start":
            return {"command": name}
        dfd = self.c["acquisition_mode"] == "dfd"
        self.stream = dict(id="common-run", run_id=0x12345678, streams={
            "dfd" if dfd else "intensity": dict(acquisition=self.effective)
        })

        def send():
            if dfd:
                self.raw = b"".join(record(self.effective, i)[0] for i in range(self.effective["total_records"]))
            else:
                self.raw = raw_fixture(self.effective, 0x12345678)[0]
            if self.truncate:
                self.raw = self.raw[:-1]
            try:
                with socket.create_connection((self.destination["host"], self.destination["port"])) as connection:
                    for i in range(0, len(self.raw), 1703):
                        connection.sendall(self.raw[i:i + 1703])
            except OSError:
                pass  # Expected when an error aborts the receiver.
            finally:
                self.done.set()

        sender = threading.Thread(target=send)
        sender.start()
        sender.join(5)  # Exercise data arriving before START returns.
        assert not sender.is_alive()
        result = copy.deepcopy(self.stream)
        if self.bad_stream:
            result["streams"]["unexpected"] = {}
        return result

    def status(self):
        stream = copy.deepcopy(self.stream)
        if stream:
            stream.update(complete=self.done.is_set() and not self.service_error,
                          stream_error=int(self.service_error), acquisition_error=0)
            for child in stream["streams"].values():
                child.update(complete=self.done.is_set(), bytes_sent=len(self.raw),
                             stream_error=0, acquisition_error=0)
        return dict(dma=dict(state=4 if self.done.is_set() else 2, error=0, pl_error=0), stream=stream)


@pytest.mark.parametrize("dfd", [False, True])
@pytest.mark.parametrize("channels", [25, 49])
def test_single_stream_capture_circular_preview_and_lossless_conversion(tmp_path, dfd, channels):
    c = request(dfd, channels)
    service = Service(c)
    settings = FlareSettings(host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0)
    snapshots = []
    filename = tmp_path / "scan.h5"
    result = FlareAcquisition(settings, c, filename=filename, on_snapshot=snapshots.append,
                              client_factory=lambda _: service).run()
    assert result.get("error") is None, result
    assert result["complete"]
    assert service.calls == ["configure", "dfd" if dfd else "intensity", "start"]
    assert snapshots[-1]["bins"] == total_bins(c)
    converted = tmp_path / "converted.h5"
    convert_raw_acquisition(filename.with_suffix(".flare.json"), converted)
    with h5py.File(filename) as original, h5py.File(converted) as offline:
        assert original.attrs["complete"] and offline.attrs["complete"]
        assert original.attrs["data_format_version"] == ("brighteyes-flare-dfd-3" if dfd else "brighteyes-flare-circular-1")
        assert original["data"].dtype == np.uint32
        np.testing.assert_array_equal(original["data"][:], offline["data"][:])
        if dfd:
            assert original["data"].shape == (24, 91, channels + 2)
            assert original["data"][0, 0, 0] == 70000
            for name in original["dfd_windows"]:
                np.testing.assert_array_equal(original[f"dfd_windows/{name}"][:], offline[f"dfd_windows/{name}"][:])
            expected = original["data"][:, :, :channels].sum(axis=(1, 2), dtype=np.uint64).reshape(2, 2, 6).sum(axis=2)
            np.testing.assert_array_equal(snapshots[-1]["rgb_image"].sum(axis=2), expected)
            assert snapshots[-1]["dfd_hist_seconds"] == pytest.approx(c["dwell"] * c["bins_per_pixel"] * 24 / FIRMWARE["clock_hz"])
        else:
            assert original["data"].shape == (1, 1, 2, 2, 2, 3, 2, channels)
            expected = original["data"][0, 0].sum(axis=(2, 3, 4, 5), dtype=np.uint64)
        np.testing.assert_array_equal(snapshots[-1]["image"], expected)


@pytest.mark.parametrize("failure", ["truncate", "bad_stream", "service_error"])
def test_failed_dma_or_scan_aborts_and_keeps_partial_status(tmp_path, failure):
    c = request(nx=1, ny=1)
    service = Service(c, **{failure: True})
    settings = FlareSettings(host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0,
                             http_timeout_seconds=0.1)
    filename = tmp_path / "partial.h5"
    result = FlareAcquisition(settings, c, filename=filename, client_factory=lambda _: service).run()
    assert not result["complete"] and result.get("error")
    assert "stop" in service.calls
    with h5py.File(filename) as output:
        assert not output.attrs["complete"]


def test_normal_masks_holdoff_and_lasers_are_configured_without_post_config_register_writes():
    c = request(False, nx=1, ny=1, laser_1_enable=True, laser_4_enable=True)
    service = Service(c)
    service.read_all = lambda: dict(detector_enable=5, detector_enable_high=0, detector_fpga_holdoff_cycles=7)
    controls = FlareLiveControls()
    controls.request(dict(laser_1_enable=0, axis_start_offset_volts=[0, 0, 0]))
    settings = FlareSettings(host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0)
    result = FlareAcquisition(settings, c, live_controls=controls, client_factory=lambda _: service).run()
    assert result.get("error") is None, result
    assert result["complete"]
    assert service.effective["physical_mask"] == [5, 0]
    assert service.effective["detector_fpga_holdoff_cycles"] == 7
    assert service.effective["laser_enable_mask"] == 9
    assert not controls.has_pending()


def test_v19_does_not_send_deprecated_trigger_aliases_and_rejects_changed_start_metadata():
    c = request()
    assert "dfd_trigger" not in c and "dfd_dwell_time_cycles_120mhz" not in c
    a = accepted(c)
    changed = dict(a, laser_hz=20000000)
    with pytest.raises(ValueError, match="clock profile"):
        v19.validate_accepted(c, changed)
    run = dict(streams=dict(dfd=dict(acquisition=changed)))
    with pytest.raises(ValueError, match="laser_hz"):
        v19.validate_stream(run, a)
