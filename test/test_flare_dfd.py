"""Schema-4 DFD1 contract, independent fixtures, recording and analysis checks."""

import socket
import struct
import threading
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
)
from brighteyes_mcs.acquisition.detectors.flare.dfd_format import pack_sequence
from brighteyes_mcs.acquisition.flare import FlareAcquisition
from brighteyes_mcs.hardware.flare import FlareClient, FlareError
from brighteyes_mcs.storage.flare import FLARE_DFD_FORMAT
from brighteyes_mcs.storage.raw import convert_raw_acquisition


def request(channels=25, **changes):
    c = dict(acquisition_mode="dfd", pixels=3, lines=2, frames=1, repetitions=1,
             bins_per_pixel=2, dwell=5000, channels=channels, packet_records=2, dummy=1,
             x_start=0, x_step=0, y_start=0, y_step=0, dfd_trigger="pixel_end",
             dfd_clock_profile="40MHz_91", dfd_dwell_time_cycles_120mhz=0,
             dfd_reference_enable=1, laser_excitation_sequence=[1, 0, 0, 2, 0, 0], laser_enable_mask=3)
    return dict(c, **changes)


def accepted(c):
    layout = layout_for(c)
    result = dict(c)
    holdoff = result.pop("detector_fpga_holdoff_cycles", 0)
    result.update(
        stream_format="DFD1", stream_format_version=1, record_unit="pixel", record_bytes=layout.record_bytes,
        detector_channels=c["channels"], stream_channels=layout.stream_channels, histogram_bins=91,
        reference_channel_index=c["channels"], count_bits=16, total_records=layout.total_records,
        total_bytes=layout.total_bytes, sys_hz=100000000, dma_hz=100000000, sampling_hz_num=3640000000,
        sampling_hz_den=9, laser_hz=40000000, fast_exc_hz=240000000, laser_slots=6,
        pixel_sys_cycles=c["dwell"] * c["bins_per_pixel"], holdoff_cycles=holdoff,
        holdoff_clock="clk_sampling", reference_enabled=bool(c["dfd_reference_enable"]),
    )
    return result


def record(c, index, run_id=0x12345678, partial=False):
    layout = layout_for(c)
    x, y, z, rep = layout.coordinates(index)
    counts = ((np.arange(91 * layout.stream_channels).reshape(91, -1) + index * 1000) % 65536).astype('<u2')
    counts[0, 0] = 65535
    counts[:, -1] = 60000  # Bright reference must never leak into intensity/fingerprint.
    padded = np.zeros((91, layout.padded_channels), dtype='<u2')
    padded[:, :layout.stream_channels] = counts
    header = struct.pack('<5Q', 0x444644310000005b | layout.stream_channels << 16,
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
    assert c["packet_records"] == 4 and "packet_bins" not in c
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


class Service:
    def __init__(self, c, *, truncate=False, fault=False):
        self.c, self.truncate, self.fault = c, truncate, fault
        self.firmware = dict(board_id=0x464c5234, schema_version=0x40000, clock_hz=100000000,
                             supported_acquisition_modes=['normal', 'dfd'])
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
        self.effective = accepted(c)
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
                raw = b''.join(record(self.c, i, self.run_id)[0] for i in range(layout_for(self.c).total_records))
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


@pytest.mark.parametrize("channels", [25, 49])
def test_capture_and_offline_conversion_preserve_histograms_reference_and_reader_metadata(tmp_path, channels):
    c = request(channels)
    settings = FlareSettings(host='127.0.0.1', bind_host='127.0.0.1', receiver_host='127.0.0.1', receiver_port=0)
    service = Service(c)
    filename = tmp_path / 'dfd.h5'
    snapshots = []
    run = FlareAcquisition(settings, c, filename=filename, on_snapshot=snapshots.append, client_factory=lambda _: service)
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
