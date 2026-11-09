"""Schema-4 DFD1/DFD2 contracts, recording, display and analysis checks."""

import socket
import struct
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import h5py
import numpy as np
import pytest

from brighteyes_mcs.acquisition.detectors.flare.config import (
    FlareSettings, configuration_from_gui, check_transport,
)
from brighteyes_mcs.acquisition.detectors.flare.dfd import (
    FlareDfdDecoder, DfdPreview, sequence_from_gui, layout_for, validate_accepted,
    REFERENCE_FACTOR, REFERENCE_METADATA, reference_configuration, validate_dfd_request,
)
from brighteyes_mcs.acquisition.detectors.flare.dfd_format import pack_sequence
from brighteyes_mcs.acquisition.flare import FlareAcquisition
from brighteyes_mcs.hardware.flare import FlareClient, FlareError
from brighteyes_mcs.storage.flare import FLARE_DFD_FORMAT, FlareRecording
from brighteyes_mcs.storage.raw import convert_raw_acquisition


def request(channels=25, **changes):
    c = dict(acquisition_mode="dfd", pixels=3, lines=2, frames=1, repetitions=1,
             bins_per_pixel=2, dwell=5000, channels=channels, packet_records=2, dummy=1,
             x_start=0, x_step=0, y_start=0, y_step=0, dfd_trigger="pixel_end",
             dfd_clock_profile="40MHz_91", dfd_dwell_time_cycles_120mhz=0,
             dfd_reference_enable=1, laser_excitation_sequence=[1, 0, 0, 2, 0, 0], laser_enable_mask=3)
    return dict(c, **changes)


def accepted(c, version=1):
    layout = replace(layout_for(c), format_version=version)
    result = dict(c)
    holdoff = result.pop("detector_fpga_holdoff_cycles", 0)
    result.update(
        stream_format=f"DFD{version}", stream_format_version=version, record_unit="pixel", record_bytes=layout.record_bytes,
        detector_channels=c["channels"], stream_channels=layout.stream_channels, histogram_bins=91,
        reference_channel_index=layout.reference_channel_index, count_bits=16, total_records=layout.total_records,
        total_bytes=layout.total_bytes, sys_hz=100000000, dma_hz=100000000, sampling_hz_num=3640000000,
        sampling_hz_den=9, laser_hz=40000000, fast_exc_hz=240000000, laser_slots=6,
        pixel_sys_cycles=c["dwell"] * c["bins_per_pixel"], holdoff_cycles=holdoff,
        holdoff_clock="clk_sampling", reference_enabled=bool(c["dfd_reference_enable"]),
    )
    if version == 2:
        result.update(extra_channel_count=1, extra_channel_index=c["channels"], extra_channel_physical_io=False,
                      padded_channels=layout.padded_channels, padding_channel_indices=[layout.stream_channels],
                      channel_roles=["detector"] * c["channels"] + ["extra", "laser_reference"])
    if REFERENCE_FACTOR in c:
        result.update(excitation_calibration_decimation_factor=1,
                      reference_histogram_counting='first_then_every_nth_raw_reference_edge')
    return result


def record(c, index, run_id=0x12345678, partial=False):
    layout = layout_for(c)
    x, y, z, rep = layout.coordinates(index)
    counts = ((np.arange(91 * layout.stream_channels).reshape(91, -1) + index * 1000) % 65536).astype('<u2')
    counts[0, 0] = 65535
    counts[:, -1] = 60000  # Bright reference must never leak into intensity/fingerprint.
    padded = np.zeros((91, layout.padded_channels), dtype='<u2')
    padded[:, :layout.stream_channels] = counts
    header = struct.pack('<5Q', layout.magic << 32 | 91 | layout.stream_channels << 16,
                         run_id << 32 | index, x << 32 | y, z << 32 | rep,
                         layout.payload_words << 32 | partial)
    return header + padded.tobytes() + struct.pack('<Q', 0x4446445f454e4421), counts


@pytest.mark.parametrize("channels,size", [(25, 5144), (49, 9512)])
@pytest.mark.parametrize("chunk", [1, 7, 39, 40, 517, 262144])
def test_fragmented_histograms_preserve_full_run_id_u16_and_reference(channels, size, chunk):
    c = request(channels)
    fixtures = [record(c, index) for index in range(layout_for(c).total_records)]
    raw = b''.join(r for r, _ in fixtures)
    decoder = FlareDfdDecoder(accepted(c), 0x12345678)
    chunks = [decoder.feed(raw[offset:offset + chunk]) for offset in range(0, len(raw), chunk)]
    decoder.finish()
    np.testing.assert_array_equal(np.concatenate(chunks), np.stack([counts for _, counts in fixtures]))
    assert decoder.index == 6 and decoder.bin_bytes == size


@pytest.mark.parametrize("channels", [25, 49])
def test_independent_upstream_ramp_fixture(channels):
    # Byte-for-byte fixtures supplied by brighteyes-flare fc5f8a9.
    raw = (Path(__file__).parent / f'fixtures/flare_dfd{channels}_ramp.bin').read_bytes()
    run = struct.unpack_from('<Q', raw, 8)[0] >> 32
    decoder = FlareDfdDecoder(accepted(request(channels, pixels=1, lines=1)), run)
    counts = decoder.feed(raw)
    decoder.finish()
    assert counts.shape == (1, 91, channels + 1)
    assert counts[0, 0, :4].tolist() == [0, 1, 2, 3]


@pytest.mark.parametrize("offset", [0, 2, 4, 8, 12, 16, 24, 32, 36, 92, 5143])
def test_corruption_and_full_width_identity_are_rejected(offset):
    c = request(pixels=1, lines=1)
    raw = bytearray(record(c, 0)[0])
    raw[offset] ^= 2
    decoder = FlareDfdDecoder(accepted(c), 0x12345678)
    with pytest.raises(ValueError):
        decoder.feed(raw)
    with pytest.raises(ValueError):
        decoder.feed(b'')


def test_partial_flag_and_truncated_suffix_never_report_complete():
    c = request(pixels=1, lines=1)
    for raw in (record(c, 0, partial=True)[0], record(c, 0)[0][:-1]):
        decoder = FlareDfdDecoder(accepted(c), 0x12345678)
        decoder.feed(raw)
        with pytest.raises(ValueError):
            decoder.finish()


def test_gui_timing_masks_and_sequence_are_adapted_without_changing_ni_encoding():
    values = dict(nx=3, ny=2, nframe=1, nrep=1, timebin_per_pixel=91, time_resolution=2,
                  spad_channels="25", calib_x=1, calib_y=1, range_x=0, range_y=0, range_z=0,
                  offset_x_um=0, offset_y_um=0, dfd_enable=True, DFD_laser_debug=True,
                  laser_sequence_1=1, laser_sequence_4=4, laser_1_enable=True, laser_4_enable=True)
    c = configuration_from_gui(values, 100000000, FlareSettings())
    assert c["dwell"] == 200 and c["bins_per_pixel"] == 91
    assert c["packet_records"] == 6 and "packet_bins" not in c  # Capped to this six-pixel scan.
    assert c["laser_excitation_sequence"] == [1, 0, 0, 8, 0, 0]
    assert c["laser_enable_mask"] == 9
    assert pack_sequence(c["laser_excitation_sequence"]) == 0x100800
    assert check_transport(c, 100000000, FlareSettings()) > 0
    with pytest.raises(ValueError, match="clear slots"):
        sequence_from_gui(dict(values, laser_sequence_7=2))
    values["dfd_enable"] = False
    assert "acquisition_mode" not in configuration_from_gui(values, 100000000, FlareSettings())


@pytest.mark.parametrize("channels", [25, 49])
def test_preview_sums_exclude_reference_and_do_not_overflow(channels):
    c = accepted(request(channels))
    data = np.stack([record(c, i)[1] for i in range(6)])
    image = np.zeros((2, 3), dtype=np.uint64)
    preview = DfdPreview(c, image)
    sums = preview.update(data, 0, None)
    np.testing.assert_array_equal(sums, data[:, :, :channels].sum(axis=(1, 2), dtype=np.uint64))
    np.testing.assert_array_equal(image.ravel(), sums)
    assert image.max() > 65535
    assert preview.snapshot()["hcl_image"].shape == (2, 3, 3)
    preview.update(data[:1], 0, (0,))
    assert image[0, 0] == data[0, :, 0].sum(dtype=np.uint64)
    assert preview.hist_records == 1
    single = preview.snapshot()["hcl_image"].copy()
    preview.update(data[:1], 0, (1,))
    assert image[0, 0] == data[0, :, 1].sum(dtype=np.uint64)
    assert preview.hist_records == 1
    assert not np.array_equal(single[0, 0], preview.snapshot()["hcl_image"][0, 0])
    preview.update(data[:1], 0, None)
    assert image[0, 0] == data[0, :, :channels].sum(dtype=np.uint64)
    assert preview.hist_records == 1


@pytest.mark.parametrize("version", [1, 2, 3])
def test_exponential_preview_recovers_decay_and_can_switch_methods(version):
    if version == 3:
        from test.test_flare_v19 import accepted as scoped_accepted, request as scoped_request
        c = scoped_accepted(scoped_request(nx=3, ny=2, points=2, circles=1))
        visits = 2
    else:
        c = accepted(request(), version)
        visits = 1
    tau_cycles, peak = 0.12, 47
    arrival = np.rint(50000 * np.exp(-((np.arange(91) - peak) % 91) / (91 * tau_cycles)))
    counts = np.zeros((6 * visits, 91, c["stream_channels"]), dtype=np.uint16)
    counts[:, :, 0] = arrival
    preview = DfdPreview(c, np.zeros((2, 3), dtype=np.uint64))
    preview.update(counts, 0, (0,))
    original = preview.hcl.copy()
    photon_image = preview.image.copy()
    original_records = preview.hist_records
    preview.update(counts[:visits], 0, (0,), lifetime_estimator="exponential")
    np.testing.assert_allclose(preview.hcl[:, :, 0], tau_cycles, rtol=0.002)
    np.testing.assert_array_equal(preview.image, photon_image)
    assert preview.hist_records == original_records + visits
    assert preview.snapshot()["lifetime_estimator"] == "exponential"
    assert (preview.hcl[:, :, 1] > 0).all()
    preview = DfdPreview(
        c, preview.image, initial_hcl=preview.hcl, initial_rgb=preview.rgb,
        selection=(0,), lifetime_estimator="exponential",
    )
    preview.update(counts[:visits], 0, (0,), lifetime_estimator="circular")
    np.testing.assert_allclose(preview.hcl, original)


def test_preview_batch_crossing_frames_keeps_last_visit_to_each_pixel():
    c = accepted(request(25))
    data = np.arange(15 * 91 * 26, dtype=np.uint16).reshape(15, 91, 26)
    image = np.zeros((2, 3), dtype=np.uint64)
    preview = DfdPreview(c, image)
    sums = preview.update(data, 4, None)
    expected = np.zeros_like(image)
    for offset, count in enumerate(sums):
        expected.flat[(4 + offset) % image.size] = count
    np.testing.assert_array_equal(image, expected)


@pytest.mark.parametrize("version", [1, 2, 3])
def test_dfd_preview_replaces_only_visited_pixels_across_repetitions(version):
    if version == 3:
        from test.test_flare_v19 import accepted as scoped_accepted, request as scoped_request, record as scoped_record
        c = scoped_accepted(scoped_request(nx=3, ny=2, points=2, circles=1))
        visits = 2
        counts = scoped_record(c, 0)[1]
    else:
        c = accepted(request(), version)
        visits = 1
        counts = record(c, 0)[1]
    image = np.full((2, 3), 123, dtype=np.uint64)
    hcl = np.full((2, 3, 3), 0.25)
    rgb = np.full((2, 3, 3), 456, dtype=np.uint64)
    preview = DfdPreview(c, image, initial_hcl=hcl, initial_rgb=rgb, selection=(1,))
    expected = counts[:, 1].sum(dtype=np.uint64)
    for index in (0, image.size * visits):
        preview.update(counts[None], index, (1,))
        assert image[0, 0] == expected
        np.testing.assert_array_equal(image.ravel()[1:], 123)
        np.testing.assert_array_equal(preview.hcl.reshape(-1, 3)[1:], 0.25)
        np.testing.assert_array_equal(preview.rgb.reshape(-1, 3)[1:], 456)
    np.testing.assert_array_equal(hcl, 0.25)
    np.testing.assert_array_equal(rgb, 456)


@pytest.mark.parametrize("channels", [25, 49])
def test_batched_recording_preserves_pixels_across_rows_frames_and_repetitions(tmp_path, channels):
    c = accepted(request(channels, pixels=5, lines=3, frames=2, repetitions=2))
    count = c["total_records"]
    histograms = np.arange(count * 91 * (channels + 1), dtype=np.uint16).reshape(count, 91, channels + 1)
    recording = FlareRecording(tmp_path / "batched.h5", c)
    assert recording.data.chunks[-2:] == (91, channels + 1)
    offset = 0
    for size in (1, 4, 8, 19, 3, count):
        batch = histograms[offset:offset + size]
        recording.append(offset, batch)
        offset += len(batch)
        assert recording.written_bins == offset
    recording.finish({"complete": True, "validated_bins": count})
    with h5py.File(recording.path) as output:
        expected = histograms.reshape(2, 2, 3, 5, 91, channels + 1)
        np.testing.assert_array_equal(output["data"][:], expected)
        assert output.attrs["stored_bins"] == count
        assert output.attrs["complete"]


class Service:
    def __init__(self, c, *, truncate=False, fault=False, version=1, decimation=False):
        self.c, self.truncate, self.fault = c, truncate, fault
        self.version = version
        self.firmware = dict(board_id=0x464c5234, schema_version=0x40000, clock_hz=100000000,
                             supported_acquisition_modes=['normal', 'dfd'], supported_dfd_formats=[f'DFD{version}'])
        if decimation:
            self.firmware['board_capabilities'] = 2046
        self.done = threading.Event()
        self.calls = []
        self.run_id = 0x12345678
        self.stream = None

    def discover(self):
        return {"firmware": self.firmware}

    def check_acquisition_support(self, *, dfd=False):
        assert dfd

    require_idle = close = lambda self: None

    def read_all(self):
        return {"detector_enable": 5, "detector_enable_high": 0, "detector_fpga_holdoff_cycles": 7}

    def configure(self, c):
        self.calls.append(("configure", dict(c)))
        self.effective = accepted(c, self.version)
        return self.effective

    def read_register(self, name):
        return {"name": name, "value": int(self.fault) if name == 'dfd_fault_flags' else self.run_id}

    def write_register(self, name, value):
        raise AssertionError("DFD accepted registers must not be modified between configure and start")

    def stream_settings(self, settings):
        self.destination = settings
        return settings

    def status(self):
        return dict(dma=dict(state=4 if self.done.is_set() else 2, error=0, pl_error=0), stream=self.stream)

    def command(self, name):
        self.calls.append((name,))
        if name == 'start':
            self.stream = dict(self.effective, id='dfd-test', complete=False, acquisition_done=0, sender_done=0)

            def send():
                raw = b''.join(record(self.effective, i, self.run_id)[0] for i in range(layout_for(self.c).total_records))
                if self.truncate:
                    raw = raw[:-23]
                with socket.create_connection((self.destination['host'], self.destination['port'])) as connection:
                    for i in range(0, len(raw), 1703):
                        connection.sendall(raw[i:i + 1703])
                self.stream.update(complete=not self.truncate, acquisition_done=1, sender_done=1)
                self.done.set()

            sender = threading.Thread(target=send)
            sender.start()
            sender.join(5)  # Data is deliberately sent before the HTTP response.
            assert not sender.is_alive()
            return self.stream
        return {"command": name}


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("reset_trace", [False, True])
def test_repeated_dfd_acquisition_restores_all_preview_planes_before_first_channel_update(monkeypatch, version, reset_trace):
    if version == 3:
        from test.test_flare_v19 import request as scoped_request, Service as ScopedService
        c = scoped_request(nx=3, ny=2)
        service = ScopedService(c)
    else:
        c = request()
        service = Service(c, version=version)
    image = np.full((2, 3), 123, dtype=np.uint64)
    hcl = np.full((2, 3, 3), 0.25)
    rgb = np.full((2, 3, 3), 456, dtype=np.uint64)
    previous_histogram = np.full(91, 10000, dtype=np.uint64)
    previous_records, previous_seconds, previous_generation = 24, 0.02, 3
    observed = []
    update = DfdPreview.update

    def observe(preview, counts, index, selection, **kwargs):
        if not observed:
            observed.append((preview.image.copy(), preview.hcl.copy(), preview.rgb.copy(), preview.selection,
                             preview.hist_sum.copy(), preview.hist_records, preview.hist_seconds,
                             preview.trace_reset_generation))
        return update(preview, counts, index, selection, **kwargs)

    monkeypatch.setattr(DfdPreview, "update", observe)
    snapshots = []
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    run = FlareAcquisition(
        settings, c, client_factory=lambda _: service, on_snapshot=snapshots.append,
        initial_image=image, initial_preview=dict(
            hcl_image=hcl, rgb_image=rgb, display_channels=(0, 1),
            dfd_hist_sum=previous_histogram, dfd_hist_records=previous_records,
            dfd_hist_seconds=previous_seconds, dfd_trace_reset_generation=previous_generation,
        ),
    )
    generation = previous_generation + int(reset_trace)
    run.display_state = dict(channels=(0, 1), trace_reset_generation=generation)
    result = run.run()
    assert result.get("error") is None, result
    assert observed[0][3] == (0, 1)
    for actual, expected in zip(observed[0][:3], (image, hcl, rgb)):
        np.testing.assert_array_equal(actual, expected)
    assert snapshots[-1]["display_channels"] == (0, 1)
    np.testing.assert_array_equal(observed[0][4], 0 if reset_trace else previous_histogram)
    assert observed[0][5] == (0 if reset_trace else previous_records)
    assert observed[0][6] == (0 if reset_trace else previous_seconds)
    assert observed[0][7] == generation
    assert snapshots[-1]["dfd_trace_reset_generation"] == generation
    assert snapshots[-1]["dfd_hist_records"] == snapshots[-1]["bins"] + (0 if reset_trace else previous_records)
    np.testing.assert_array_equal(previous_histogram, 10000)
    np.testing.assert_array_equal(hcl, 0.25)
    np.testing.assert_array_equal(rgb, 456)


def test_retained_dfd_reference_prevents_peak_relearning_from_first_dim_pixel():
    c = accepted(request())
    peak, tau = 47, 0.12
    strong_histogram = np.rint(100000 * np.exp(-((np.arange(91) - peak) % 91) / (91 * tau))).astype(np.uint64)
    previous = dict(dfd_hist_sum=strong_histogram, dfd_hist_records=1000)
    counts = np.zeros((1, 91, c["stream_channels"]), dtype=np.uint16)
    counts[0, [50, 60, 70], 0] = [6, 3, 1]
    image = np.zeros((2, 3), dtype=np.uint64)
    fresh = DfdPreview(c, image.copy(), selection=(0,))
    fresh.update(counts, 0, (0,), lifetime_estimator="exponential")
    assert fresh.hist_sum.argmax() == 50
    retained = DfdPreview(c, image.copy(), selection=(0,), initial_trace=previous)
    retained.update(counts, 0, (0,), lifetime_estimator="exponential")
    assert retained.hist_sum.argmax() == peak
    assert retained.hist_records == 1001
    diagnostics = retained.lifetime_diagnostics()
    assert diagnostics["reference_peak_bin"] == peak
    assert diagnostics["scan_peak_bin"] == 50
    assert diagnostics["scan_photons"] == 10
    assert diagnostics["reference_photons"] == int(strong_histogram.sum()) + 10
    assert diagnostics["illuminated_pixels"] == 1
    assert diagnostics["median_pixel_photons"] == 10
    np.testing.assert_array_equal(retained.hist_live, counts[0, :, 0])
    np.testing.assert_array_equal(retained.hist_sum, strong_histogram + counts[0, :, 0])
    # A source change must discard history from the previous detector selection.
    retained.update(counts, 0, (0, 1), lifetime_estimator="exponential")
    assert retained.hist_sum.argmax() == 50
    assert retained.hist_records == 1
    np.testing.assert_array_equal(retained.hist_sum, counts[0, :, 0])
    assert retained.lifetime_diagnostics()["scan_photons"] == 10


def test_empty_lifetime_scan_diagnostics_have_no_fabricated_peak_or_lifetime():
    preview = DfdPreview(accepted(request()), np.zeros((2, 3), dtype=np.uint64))
    diagnostics = preview.lifetime_diagnostics()
    assert diagnostics["reference_peak_bin"] is None
    assert diagnostics["scan_peak_bin"] is None
    assert diagnostics["illuminated_pixels"] == diagnostics["valid_pixels"] == 0
    assert diagnostics["tau_ns_p05_p50_p95"] is None
    assert diagnostics["median_precision"] is None


@pytest.mark.parametrize("estimator", ["integer_reference_aperture_v1", "integer_reference_half_height_v2"])
def test_reference_alignment_survives_capture_preview_and_conversion(tmp_path, estimator):
    import json

    c = request()
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    service = Service(c, version=2, decimation=True)
    alignment = dict(
        excitation_reference_source=0, excitation_reference_requested_source=0,
        excitation_reference_pending=False, excitation_reference_status=0x41e,
        excitation_reference_ready=True, excitation_reference_fault=0,
        excitation_alignment_generation=7, excitation_phase_offset_bins=87,
        excitation_reference_span_bins=9, excitation_phase_residual=None,
        excitation_phase_residual_valid=False, excitation_phase_registration=estimator,
        excitation_phase_integer_correction_applied=True,
    )
    configure = service.configure

    def configure_with_alignment(configuration):
        result = configure(configuration)
        result.update(alignment)
        return result

    service.configure = configure_with_alignment
    path = tmp_path / 'aligned.h5'
    snapshots = []
    result = FlareAcquisition(settings, c, filename=path, on_snapshot=snapshots.append,
                             client_factory=lambda _: service).run()
    assert result.get('error') is None, result
    assert result['complete']
    sidecar = json.loads(path.with_suffix('.flare.json').read_text())
    for key, value in alignment.items():
        assert sidecar['configuration'][key] == value
        assert snapshots[-1]['dfd_layout'][key] == value
    converted = tmp_path / 'converted.h5'
    convert_raw_acquisition(path.with_suffix('.flare.json'), converted)
    with h5py.File(path) as original, h5py.File(converted) as offline:
        expected = np.stack([record(service.effective, i)[1] for i in range(6)])
        for output in (original, offline):
            np.testing.assert_array_equal(output['data'][:].reshape(expected.shape), expected)
            for attrs in (output.attrs, output['data'].attrs, output['raw/metadata'].attrs):
                for key, value in alignment.items():
                    if value is None:
                        assert key not in attrs
                    else:
                        assert attrs[key] == value


@pytest.mark.parametrize("channels", [25, 49])
def test_capture_and_offline_conversion_preserve_histograms_reference_and_reader_metadata(tmp_path, channels):
    c = request(channels)
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    service = Service(c)
    filename = tmp_path / 'dfd.h5'
    snapshots = []
    run = FlareAcquisition(settings, c, filename=filename, on_snapshot=snapshots.append, client_factory=lambda _: service)
    run.display_state = dict(trace_bin_seconds=0.0003, trace_history_seconds=1)
    result = run.run()
    assert result.get('error') is None, result
    assert result['complete'] and result['validated_records'] == 6
    configured = service.calls[0][1]
    assert configured['physical_mask'] == [5, 0] and configured['detector_fpga_holdoff_cycles'] == 7
    expected = np.stack([record(c, i)[1] for i in range(6)]).reshape(1, 1, 2, 3, 91, channels + 1)
    with h5py.File(filename) as output:
        assert output.attrs['data_format_version'] == FLARE_DFD_FORMAT
        assert output['data'].dtype == np.uint16
        np.testing.assert_array_equal(output['data'][:], expected)
        assert output.attrs['reference_channel_index'] == channels
        assert output['raw/metadata'].attrs['dfd_active']
    from brighteyes_mcs_reader import load
    data, metadata = load(filename)
    np.testing.assert_array_equal(data, expected)
    assert metadata.dfd_active and metadata.dfd_nbins == 91 and metadata.dfd_freq == 40
    converted = tmp_path / 'converted.h5'
    convert_raw_acquisition(filename.with_suffix('.flare.json'), converted)
    with h5py.File(converted) as output:
        np.testing.assert_array_equal(output['data'][:], expected)
    assert snapshots[-1]['bins'] == snapshots[-1]['total_bins'] == 6
    assert snapshots[-1]['bin_seconds'] == 0.0001
    assert len(snapshots[-1]['dfd_hist_sum']) == 91
    expected_counts = expected.reshape(6, 91, channels + 1)[:, :, :channels].sum(axis=(1, 2))
    np.testing.assert_allclose(snapshots[-1]['trace'], expected_counts.reshape(2, 3).sum(axis=1) / 0.0003)
    np.testing.assert_allclose(snapshots[-1]['trace_times'], [0, 0.0003])


@pytest.mark.parametrize("version", [1, 2])
def test_dfd_trace_rounds_nonmultiple_width_to_whole_91_bin_records(version):
    c = request(bins_per_pixel=91, dwell=200)
    service = Service(c, version=version)
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    snapshots = []
    run = FlareAcquisition(settings, c, on_snapshot=snapshots.append, client_factory=lambda _: service)
    run.display_state = dict(trace_bin_seconds=0.0004, trace_history_seconds=1)
    result = run.run()
    assert result.get('error') is None, result
    record_seconds = 91 * 2e-6
    counts = np.stack([record(service.effective, i)[1][:, :25] for i in range(6)])
    np.testing.assert_allclose(
        snapshots[-1]['trace'], counts.reshape(2, 3, 91, 25).sum(axis=(1, 2, 3)) / (3 * record_seconds),
    )
    np.testing.assert_allclose(snapshots[-1]['trace_times'], [0, 3 * record_seconds])


@pytest.mark.parametrize("truncate,fault", [(True, False), (False, True)])
def test_dfd_delivery_or_clock_faults_leave_partial_recordings(tmp_path, truncate, fault):
    c = request()
    service = Service(c, truncate=truncate, fault=fault)
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    result = FlareAcquisition(settings, c, filename=tmp_path / 'partial.h5', client_factory=lambda _: service).run()
    assert not result['complete'] and result.get('error')
    with h5py.File(tmp_path / 'partial.h5') as output:
        assert not output.attrs['complete']


def test_mode_and_layout_discovery_prevent_using_a2_for_dfd():
    client = FlareClient(FlareSettings(), session=Mock(), token='')
    client.firmware = dict(board_id=0x464c5234, schema_version=0x40000, clock_hz=100000000)
    client.check_acquisition_support()  # Schema-4 normal A2 remains compatible.
    with pytest.raises(FlareError, match='advertising DFD'):
        client.check_acquisition_support(dfd=True)
    client.firmware['supported_acquisition_modes'] = ['normal', 'dfd']
    client.check_acquisition_support(dfd=True)
    c = request()
    for key, value in [('record_bytes', 120), ('pixel_sys_cycles', 5000), ('histogram_bins', 81),
                       ('sampling_hz_den', 8), ('fast_exc_hz', 120000000),
                       ('reference_enabled', False), ('record_unit', 'bin')]:
        with pytest.raises(ValueError):
            validate_accepted(c, dict(accepted(c), **{key: value}), 100000000)


@pytest.mark.parametrize("channels", [25, 49])
@pytest.mark.parametrize("chunk_size", [1, 39, 40, 517, 262144])
def test_dfd2_fragmented_extra_and_reference_are_distinct(channels, chunk_size):
    c = accepted(request(channels, pixels=1, lines=1), version=2)
    validate_accepted(request(channels, pixels=1, lines=1), c, 100000000)
    raw, expected = record(c, 0)
    decoder = FlareDfdDecoder(c, 0x12345678)
    parts = [decoder.feed(raw[i:i + chunk_size]) for i in range(0, len(raw), chunk_size)]
    decoder.finish()
    actual = np.concatenate(parts)
    np.testing.assert_array_equal(actual[0], expected)
    assert actual.shape == (1, 91, channels + 2)
    assert np.any(actual[0, :, channels] != 0)
    assert np.all(actual[0, :, channels + 1] == 60000)
    image = np.zeros((1, 1), dtype=np.uint64)
    preview = DfdPreview(c, image)
    preview.update(actual, 0, None)
    assert image[0, 0] == expected[:, :channels].sum(dtype=np.uint64)
    for index in (channels, channels + 1):
        preview.update(actual, 0, (index,))
        assert image[0, 0] == expected[:, index].sum(dtype=np.uint64)
        np.testing.assert_array_equal(preview.hist_sum, expected[:, index])


@pytest.mark.parametrize("channels", [25, 49])
def test_dfd2_capture_conversion_and_channel_metadata(tmp_path, channels):
    c = request(channels)
    effective = accepted(c, version=2)
    service = Service(c, version=2)
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    filename = tmp_path / 'dfd2.h5'
    snapshots = []
    run = FlareAcquisition(settings, c, filename=filename, client_factory=lambda _: service,
                           on_snapshot=snapshots.append)
    run.display_channels = (channels + 1,)
    result = run.run()
    assert result.get('error') is None, result
    assert result['complete']
    expected = np.stack([record(effective, i)[1] for i in range(6)])
    converted = tmp_path / 'converted.h5'
    convert_raw_acquisition(filename.with_suffix('.flare.json'), converted)
    for path in (filename, converted):
        with h5py.File(path) as output:
            np.testing.assert_array_equal(output['data'][:].reshape(expected.shape), expected)
            assert output.attrs['stream_format'] == 'DFD2'
            assert output['data'].attrs['extra_channel_index'] == channels
            assert output['data'].attrs['reference_channel_index'] == channels + 1
            assert output.attrs['channel_roles'][-2:].tolist() == ['extra', 'laser_reference']
    assert snapshots[-1]['dfd_layout']['reference_channel_index'] == channels + 1
    np.testing.assert_array_equal(snapshots[-1]['image'], np.full((2, 3), 91 * 60000))
    np.testing.assert_array_equal(snapshots[-1]['fingerprint'], expected[:, :, :channels].sum(axis=(0, 1)))


@pytest.mark.parametrize("channels", [25, 49])
def test_dfd2_rejects_wrong_layout_padding_and_incomplete_data(channels):
    request_config = request(channels, pixels=1, lines=1)
    c = accepted(request_config, version=2)
    raw = record(c, 0)[0]
    with pytest.raises(ValueError):
        FlareDfdDecoder(accepted(request_config), 0x12345678).feed(raw)
    for key, value in (("reference_channel_index", channels), ("extra_channel_index", channels + 1),
                       ("extra_channel_physical_io", True), ("channel_roles", ['detector'] * (channels + 2)),
                       ("padding_channel_indices", []), ("stream_format_version", 1)):
        with pytest.raises(ValueError):
            FlareDfdDecoder(dict(c, **{key: value}), 0x12345678)
    corrupt = bytearray(raw)
    corrupt[40 + 2 * c['stream_channels']] = 1
    with pytest.raises(ValueError):
        FlareDfdDecoder(c, 0x12345678).feed(corrupt)
    for incomplete in (raw[:-1], record(c, 0, partial=True)[0]):
        decoder = FlareDfdDecoder(c, 0x12345678)
        decoder.feed(incomplete)
        with pytest.raises(ValueError):
            decoder.finish()


@pytest.mark.parametrize("factor", [1, 101, 65535])
@pytest.mark.parametrize("channels", [25, 49])
def test_reference_decimation_capture_display_and_conversion(tmp_path, channels, factor):
    c = request(channels, **{REFERENCE_FACTOR: factor})
    service = Service(c, version=2, decimation=True)
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    path = tmp_path / 'decimated.h5'
    snapshots = []
    run = FlareAcquisition(settings, c, filename=path, on_snapshot=snapshots.append, client_factory=lambda _: service)
    run.display_channels = (channels + 1,)
    result = run.run()
    assert result.get('error') is None, result
    assert result['complete']
    assert service.calls[0][1][REFERENCE_FACTOR] == factor
    effective = service.effective
    expected = np.stack([record(effective, i)[1] for i in range(6)])
    # The mock transmits large U16 values irrespective of N. MCS must preserve
    # exactly those values, without scaling, wrapping or estimating full rate.
    np.testing.assert_array_equal(snapshots[-1]['image'], np.full((2, 3), 91 * 60000))
    np.testing.assert_array_equal(snapshots[-1]['dfd_hist_sum'], np.full(91, 6 * 60000))
    assert snapshots[-1]['dfd_layout'][REFERENCE_FACTOR] == factor
    np.testing.assert_array_equal(snapshots[-1]['fingerprint'], expected[:, :, :channels].sum(axis=(0, 1)))
    converted = tmp_path / 'converted.h5'
    convert_raw_acquisition(path.with_suffix('.flare.json'), converted)
    for filename in (path, converted):
        with h5py.File(filename) as output:
            np.testing.assert_array_equal(output['data'][:].reshape(expected.shape), expected)
            for key in REFERENCE_METADATA:
                assert output.attrs[key] == effective[key]
                assert output['data'].attrs[key] == effective[key]
                assert output['raw/metadata'].attrs[key] == effective[key]
    import json
    sidecar = json.loads(path.with_suffix('.flare.json').read_text())
    assert sidecar['configuration'][REFERENCE_FACTOR] == factor


@pytest.mark.parametrize("factor", [0, 65536, True, 1.5, '101'])
def test_reference_decimation_rejects_invalid_requests(factor):
    with pytest.raises(ValueError, match='Reference decimation'):
        validate_dfd_request(request(**{REFERENCE_FACTOR: factor}))


def test_reference_decimation_defaults_and_legacy_negotiation():
    c = request()
    assert reference_configuration(c, {'board_capabilities': 2046})[REFERENCE_FACTOR] == 65535
    assert reference_configuration(dict(c, **{REFERENCE_FACTOR: 101}), {'board_capabilities': 2046})[REFERENCE_FACTOR] == 101
    assert REFERENCE_FACTOR not in reference_configuration(dict(c, **{REFERENCE_FACTOR: 101}), {})
    for version in (1, 2):
        service = Service(c, version=version)
        settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
        run = FlareAcquisition(settings, dict(c, **{REFERENCE_FACTOR: 101}), client_factory=lambda _, device=service: device)
        result = run.run()
        assert result['complete'], result
        assert REFERENCE_FACTOR not in service.calls[0][1]
        assert result['configuration'][REFERENCE_FACTOR] == 1
        assert result['configuration']['reference_histogram_counting'] == 'legacy_shared_detector_holdoff'


@pytest.mark.parametrize("changes", [
    {REFERENCE_FACTOR: 7}, {'excitation_calibration_decimation_factor': 101},
    {'reference_histogram_counting': 'unknown'},
])
def test_reference_decimation_rejects_inconsistent_accepted_metadata(changes):
    c = request(**{REFERENCE_FACTOR: 101})
    with pytest.raises(ValueError):
        validate_accepted(c, dict(accepted(c, version=2), **changes), 100000000)


def test_reference_decimation_start_must_match_accepted_factor():
    c = request(**{REFERENCE_FACTOR: 101})
    service = Service(c, version=2, decimation=True)
    command = service.command

    def mismatched_start(name):
        response = command(name)
        return dict(response, **{REFERENCE_FACTOR: 7}) if name == 'start' else response

    service.command = mismatched_start
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    result = FlareAcquisition(settings, c, client_factory=lambda _: service).run()
    assert not result['complete']
    assert 'reference decimation disagrees' in result['error']
