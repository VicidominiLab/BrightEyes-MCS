"""Flare protocol, lossless recording and lifecycle tests without hardware."""

import json
import socket
import struct
import subprocess
import sys
import threading
from unittest.mock import Mock

import h5py
import numpy as np
import pytest
import requests

from brighteyes_mcs.acquisition.detectors.flare.config import (
    FlareSettings,
    axis_registers_from_gui,
    check_transport,
    configuration_from_gui,
    total_bins,
    validate_configuration,
)
from brighteyes_mcs.acquisition.detectors.flare.decoder import FlareDecoder
from brighteyes_mcs.acquisition.detectors.flare.controls import FlareLiveControls
from brighteyes_mcs.acquisition.detectors.models import (
    DETECTOR_FLARE,
    detector_uses_flare,
    detector_uses_nifpga_control,
    detector_uses_nifpga_fifo,
    normalize_detector_model,
)
from brighteyes_mcs.acquisition.flare import FlareAcquisition, _update_preview_image
from brighteyes_mcs.hardware.flare import FlareClient, FlareError
from brighteyes_mcs.storage.flare import FlareRecording
from brighteyes_mcs.storage.raw import convert_raw_acquisition
from brighteyes_mcs.storage.legacy_config import LegacyConfigurationTranslator


def configuration(channels=25, **changes):
    result = dict(
        pixels=3,
        lines=2,
        frames=2,
        repetitions=2,
        bins_per_pixel=3,
        dwell=100000,
        packet_bins=4,
        channels=channels,
        dummy=1,
        x_start=0,
        x_step=0,
        y_start=0,
        y_step=0,
    )
    result.update(changes)
    return result


def raw_fixture(config, run_id=257):
    result = bytearray()
    expected = []
    for index in range(total_bins(config)):
        n = index
        coords = []
        for name in ("bins_per_pixel", "pixels", "lines", "frames", "repetitions"):
            coords.append(n % config[name])
            n //= config[name]
        b, x, y, z, rep = coords
        header = config["channels"] | ((b & 255) << 8) | ((rep & 255) << 16) | ((z & 255) << 24)
        header |= ((y & 255) << 32) | ((x & 255) << 40) | ((run_id & 255) << 48) | (0xA2 << 56)
        counts = [((index + 1) * 70000 + ch) & 0xFFFFFFFF for ch in range(config["channels"])]
        result.extend(struct.pack("<Q", header))
        result.extend(struct.pack(f"<{config['channels']}I", *counts))
        result.extend(struct.pack("<IQ", 0, 0x465047415F454E44))
        expected.append(counts)
    return bytes(result), np.asarray(expected, dtype=np.uint32)


def test_preview_refreshes_only_visited_pixels_and_accumulates_split_timebins():
    image = np.array([[100, 200], [300, 400]], dtype=np.uint64)
    _update_preview_image(image, np.array([1, 2], dtype=np.uint64), 0, 3)
    np.testing.assert_array_equal(image, [[3, 200], [300, 400]])
    _update_preview_image(image, np.arange(3, 8, dtype=np.uint64), 2, 3)
    np.testing.assert_array_equal(image, [[6, 15], [7, 400]])
    # Cross a frame boundary in one batch, ending midway through its first pixel.
    _update_preview_image(image, np.arange(8, 15, dtype=np.uint64), 7, 3)
    np.testing.assert_array_equal(image, [[27, 15], [24, 33]])
    _update_preview_image(image, np.array([15], dtype=np.uint64), 14, 3)
    np.testing.assert_array_equal(image, [[42, 15], [24, 33]])


def test_preview_handles_multiple_frames_in_one_batch_without_adding_old_counts():
    image = np.full((2, 2), 999, dtype=np.uint64)
    # Two complete frames followed by one pixel of the next repetition.
    _update_preview_image(image, np.arange(1, 28, dtype=np.uint64), 0, 3)
    np.testing.assert_array_equal(image, [[78, 51], [60, 69]])


@pytest.mark.parametrize("channels", [25, 49])
@pytest.mark.parametrize("fragment", [1, 119, 217, 262144])
def test_decoder_handles_fragmentation_and_preserves_u32(channels, fragment):
    config = configuration(channels, pixels=257, lines=1, frames=1, repetitions=1, bins_per_pixel=1)
    raw, expected = raw_fixture(config)
    decoder = FlareDecoder(config, 257)
    batches = [decoder.feed(raw[i : i + fragment]) for i in range(0, len(raw), fragment)]
    decoder.finish()
    np.testing.assert_array_equal(np.concatenate(batches), expected)


@pytest.mark.parametrize("offset", [0, 7, 5, 6, 108, 112])
def test_decoder_rejects_structural_corruption(offset):
    raw, _ = raw_fixture(configuration())
    raw = bytearray(raw)
    raw[offset] ^= 1
    with pytest.raises(ValueError):
        FlareDecoder(configuration(), 1).feed(raw)


def test_decoder_rejects_short_extra_and_partial_records():
    config = configuration()
    raw, _ = raw_fixture(config)
    for payload in (raw[:-1], raw[:-120]):
        decoder = FlareDecoder(config, 1)
        decoder.feed(payload)
        with pytest.raises(ValueError):
            decoder.finish()
    with pytest.raises(ValueError):
        FlareDecoder(config, 1).feed(raw + raw[:120])


def test_settings_and_routing_do_not_change_legacy_profiles():
    assert normalize_detector_model("TCP/IP - FPGA Flare") == DETECTOR_FLARE
    assert detector_uses_flare(DETECTOR_FLARE)
    assert not detector_uses_nifpga_fifo(DETECTOR_FLARE)
    assert not detector_uses_nifpga_control(DETECTOR_FLARE)
    assert detector_uses_nifpga_control(DETECTOR_FLARE, "slave")
    payload = {"detector_model": "SPAD Array", "flare_port": "invalid dormant value", "future": [1]}
    config = LegacyConfigurationTranslator.from_legacy(payload)
    restored = LegacyConfigurationTranslator.to_legacy(config)
    assert restored["flare_port"] == payload["flare_port"]
    assert restored["detector_model"] == "SPAD Array"
    assert not any(k.startswith("flare_") and k != "flare_port" for k in restored)
    payload = dict(detector_model=DETECTOR_FLARE, flare_mode="slave", flare_port=8081)
    restored = LegacyConfigurationTranslator.to_legacy(
        LegacyConfigurationTranslator.from_legacy(payload)
    )
    assert restored["flare_mode"] == "slave"
    assert restored["flare_host"] == "mmskria3"


@pytest.fixture
def scan_values():
    return dict(
        nx=3,
        ny=2,
        nframe=1,
        nrep=2,
        timebin_per_pixel=3,
        time_resolution=1000,
        spad_channels="25",
        calib_x=1,
        calib_y=1,
        range_x=0.3,
        range_y=0.2,
        range_z=0,
        offset_x_um=0,
        offset_y_um=0,
        offset_z_um=0,
    )


def test_scan_limits_and_clock_conversion(scan_values):
    values = scan_values
    config = configuration_from_gui(values, 100000000, FlareSettings())
    assert config["dwell"] == 100000
    assert config["repetitions"] == 2
    assert config["x_step"] == 328
    assert check_transport(config, 100000000, FlareSettings()) > 0
    for bad in (
        dict(pixels=True),
        dict(channels=26),
        dict(pixels=2**31 - 1, lines=3),
        dict(dwell=31),
        dict(x_start=32768),
        dict(y_step=32768),
    ):
        with pytest.raises(ValueError):
            validate_configuration(configuration(**bad))
    assert configuration_from_gui(dict(values, range_z=1), 100000000, FlareSettings())["frames"] == 1
    registers = axis_registers_from_gui(dict(values, range_z=1, nframe=2, calib_z=2, offset_z_um=1))
    assert registers["axis_start_offset_volts"][2] == round(0.25 * 32768 / 10)
    assert registers["axis_calibration_volts_per_step"][2] == round(0.25 * 32768 / 10)
    assert configuration_from_gui(dict(values, nframe=2), 100000000, FlareSettings())["frames"] == 2
    assert total_bins(configuration(pixels=2**20, lines=2**10, frames=1, repetitions=1)) > 2**31


@pytest.mark.parametrize("axis,offset", [("x", -3), ("x", 3), ("y", -3), ("y", 3)])
@pytest.mark.parametrize("preview", [False, True])
def test_configured_voltage_limits_warn_and_keep_requested_scan(scan_values, caplog, axis, offset, preview):
    values = dict(scan_values, **{f"offset_{axis}_um": offset})
    expected = configuration_from_gui(values, 100000000, FlareSettings(), preview=preview)
    values.update({f"min_{axis}_V": -1, f"max_{axis}_V": 1})
    actual = configuration_from_gui(values, 100000000, FlareSettings(), preview=preview)
    assert actual == expected  # Neither clip the scan nor change its geometry.
    assert f"{axis.upper()} scan exceeds the configured voltage limits" in caplog.text
    assert "continuing with the requested scan" in caplog.text


@pytest.mark.parametrize("field,value", [("range_x", float("nan")), ("offset_y_um", float("inf"))])
def test_nonfinite_scan_coordinates_still_block(scan_values, field, value):
    with pytest.raises(ValueError, match="non-finite coordinates"):
        configuration_from_gui(dict(scan_values, **{field: value}), 100000000, FlareSettings())


def test_physical_dac_limit_still_blocks_despite_advisory_configured_limits(scan_values):
    with pytest.raises(ValueError, match="physical signed 16-bit DAC range"):
        configuration_from_gui(dict(scan_values, offset_x_um=11), 100000000, FlareSettings())


def client_with_response(status=200, payload=None):
    session = Mock()
    session.headers = {}
    response = Mock(status_code=status)
    response.json.return_value = payload
    session.request.return_value = response
    client = FlareClient(FlareSettings(), session=session, token="secret")
    return client, session, response


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 503])
def test_http_errors_preserve_status_errno_and_endpoint(status):
    client, session, response = client_with_response(status, {"error": "busy", "errno": 16})
    with pytest.raises(FlareError, match=f"HTTP {status}, errno=16"):
        client.command("start")
    assert session.request.call_count == 1
    response.json.side_effect = ValueError()
    with pytest.raises(FlareError, match="invalid JSON"):
        client.status()


def test_ambiguous_timeout_is_not_retried():
    client, session, _ = client_with_response()
    session.request.side_effect = requests.Timeout()
    with pytest.raises(FlareError, match="inspect status"):
        client.command("start")
    assert session.request.call_count == 1


def test_register_names_arrays_and_readback_are_forwarded_without_policy_veto():
    client, session, _ = client_with_response(payload={"name": "scratch", "value": 7})
    client.catalog = {
        "scratch": dict(
            address=4, type="U32", elements=1, bits_per_element=32, write_policy="live"
        ),
        "axis": dict(
            address=8, type="I32-Array", elements=3, bits_per_element=32, write_policy="stopped"
        ),
        "start": dict(write_policy="command"),
    }
    assert client.resolve_register("0x4") == "scratch"
    assert client.resolve_register("REG_SCRATCH") == "scratch"
    assert client.write_register("scratch", 7)["value"] == 7
    assert [call.args[0] for call in session.request.call_args_list] == ["PUT", "GET"]
    client.require_idle = Mock(side_effect=AssertionError("Server decides write policy"))
    client.write_register("scratch", 2**32)
    client.write_register("start", 1)
    client.write_register("axis", [-10, 0, 10])
    client.write_register("axis", [1, 2])
    client.write_register("REG_NEW_REGISTER", 1)
    assert session.request.call_args_list[-2].args[1].endswith("/registers/new_register")
    assert [call.kwargs["json"] for call in session.request.call_args_list if call.args[0] == "PUT"] == [
        {"value": 7}, {"value": 2**32}, {"value": 1}, {"value": [-10, 0, 10]},
        {"value": [1, 2]}, {"value": 1},
    ]


@pytest.mark.parametrize("name,address,kind,bits,value", [
    ("laser_1_enable", 0x0450, "Bool", 1, 1),
    ("laser_1_enable", 0x0450, "Bool", 1, 0),
    ("master_laser_clk_multiplier", 0x8070, "U32", 32, 10),
    ("master_laser_clk_divider", 0x8074, "U32", 32, 50),
    ("master_laser_clk_apply", 0x8078, "U32", 32, 1),
    ("axis_start_offset_volts", 0x0124, "I32", 32, [-1, 2, -3]),
    ("max_pixel", 0x0104, "I32", 32, 7),
    ("command", 0x0010, "U32", 32, 1),
    ("start_command", 0x0028, "Bool", 1, 1),
    ("soft_reset", 0x8030, "U32", 32, 1),
    ("channel_count", 0x804C, "U32", 32, 25),
    ("dma_packet_bins", 0x8040, "U32", 32, 4),
])
def test_firmware_1_0_4_live_writes_use_register_endpoint_without_idle_or_lifecycle(
    name, address, kind, bits, value,
):
    # Policies from brighteyes-flare 2985e2f: commands and geometry are now live.
    client, session, _ = client_with_response(payload={"name": name, "value": value})
    client.catalog = {name: dict(
        address=address, type=kind, elements=3 if isinstance(value, list) else 1,
        bits_per_element=bits, write_policy="live",
    )}
    client.require_idle = Mock(side_effect=AssertionError("Live writes must not require idle"))
    assert client.write_register(hex(address), value) == {"name": name, "value": value}
    assert [(call.args[0], call.args[1]) for call in session.request.call_args_list] == [
        ("PUT", client.base_url + "/registers/" + name),
        ("GET", client.base_url + "/registers/" + name),
    ]
    assert session.request.call_args_list[0].kwargs["json"] == {"value": value}


def test_legacy_laser_busy_response_is_reported_without_retry_or_reset():
    client, session, _ = client_with_response(409, {
        "error": "[Errno 16] acquisition or stream is still active", "errno": 16,
    })
    client.catalog = {"laser_1_enable": dict(
        address=0x0450, type="Bool", elements=1, bits_per_element=1, write_policy="live",
    )}
    with pytest.raises(FlareError, match="PUT /registers/laser_1_enable: HTTP 409, errno=16"):
        client.write_register("laser_1_enable", 1)
    assert session.request.call_count == 1


def test_legacy_stopped_register_busy_rejection_comes_from_server():
    client, session, _ = client_with_response(409, {
        "error": "acquisition or stream is still active", "errno": 16,
    })
    client.catalog = {"max_pixel": dict(
        address=0x0104, type="I32", elements=1, bits_per_element=32, write_policy="stopped",
    )}
    with pytest.raises(FlareError, match="PUT /registers/max_pixel: HTTP 409, errno=16"):
        client.write_register("max_pixel", 7)
    assert [call.args[0] for call in session.request.call_args_list] == ["PUT"]


@pytest.mark.parametrize("policy,status,errno", [
    ("read_only", 403, 1), ("command", 403, 1), ("stopped", 409, 16), (None, 404, 2),
])
def test_server_rejects_registers_even_when_catalog_would_disallow_them(policy, status, errno):
    client, session, _ = client_with_response(status, {"error": "server rejection", "errno": errno})
    client.catalog = {"example": {"write_policy": policy}} if policy is not None else {}
    with pytest.raises(FlareError, match=f"HTTP {status}, errno={errno}: server rejection"):
        client.write_register("example", 1)
    assert session.request.call_count == 1
    assert session.request.call_args.args[0] == "PUT"


class FakeClient:
    def __init__(self, settings, config, *, truncate=False, service_error=False, early=False):
        self.settings = settings
        self.config = config
        self.firmware = {
            "board_id": 0x464C5234,
            "schema_version": 0x00030000,
            "clock_hz": 100000000,
        }
        self.done = threading.Event()
        self.stream = None
        self.calls = []
        self.truncate, self.service_error, self.early = truncate, service_error, early

    def discover(self):
        return {"firmware": self.firmware}

    check_acquisition_support = require_idle = close = lambda self: None

    def configure(self, config):
        self.calls.append("configure")
        return config

    def read_all(self):
        return {"scratch": 0}

    def read_register(self, name):
        return {"name": name, "value": 257}

    def stream_settings(self, settings):
        self.destination = settings
        return settings

    def status(self):
        stream = (
            None
            if self.stream is None
            else dict(
                self.stream,
                complete=self.done.is_set() and not self.service_error,
                acquisition_done=int(self.done.is_set()),
                sender_done=int(self.done.is_set()),
                stream_error=int(self.service_error),
                acquisition_error=0,
            )
        )
        return {
            "dma": {"state": 4 if self.done.is_set() else 2, "error": 0, "pl_error": 0},
            "stream": stream,
        }

    def command(self, name):
        self.calls.append(name)
        if name == "start":
            self.stream = {"id": "test-stream", "complete": False}

            def send():
                raw, _ = raw_fixture(self.config)
                if self.truncate:
                    raw = raw[:-1]
                try:
                    with socket.create_connection(
                        (self.destination["host"], self.destination["port"])
                    ) as conn:
                        for offset in range(0, len(raw), 217):
                            conn.sendall(raw[offset : offset + 217])
                except OSError:
                    pass  # Expected when a simulated failure makes the receiver close early.
                finally:
                    self.done.set()

            self.sender = threading.Thread(target=send)
            self.sender.start()
            if self.early:
                self.sender.join()  # Data arrives before the HTTP start response.
            return self.stream
        return {"command": name}


@pytest.mark.parametrize("policy", ["stopped", "live"])
def test_detector_masks_and_holdoff_survive_configuration_reset(policy):
    config = configuration(frames=1, repetitions=1)
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0,
    )
    requested = {"detector_enable": 5, "detector_enable_high": 3, "detector_fpga_holdoff_cycles": 12}

    class ResettingClient(FakeClient):
        catalog = {name: {"write_policy": policy} for name in requested}

        def __init__(self):
            super().__init__(settings, config, early=True)
            self.values = dict(requested)

        def configure(self, config):
            self.values = dict.fromkeys(requested, 0)
            return super().configure(config)

        def read_all(self):
            return dict(self.values)

        def write_register(self, name, value):
            self.values[name] = value
            self.calls.append((name, value))
            return {"name": name, "value": value}

        def command(self, name):
            if name == "start":
                assert self.values == requested
            return super().command(name)

    fake = ResettingClient()
    run = FlareAcquisition(settings, config, client_factory=lambda settings: fake)
    result = run.run()
    assert result.get("error") is None, result
    assert result["complete"]
    assert result["detector_settings"] == requested
    assert result["registers"] == requested
    assert fake.calls == ["configure", *requested.items(), "start"]


@pytest.mark.parametrize("channels", [25, 49])
def test_acquisition_restores_lasers_and_records_live_position_updates(tmp_path, channels):
    config = configuration(channels, frames=1, repetitions=1)
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0,
    )
    controls = FlareLiveControls()
    controls.request({
        "axis_start_offset_volts": [0, 0, 10], "axis_calibration_volts_per_step": [0, 0, 2],
        "laser_1_enable": 1,
    })

    class LiveClient(FakeClient):
        def configure(self, config):
            self.values = {"laser_1_enable": 0}
            return super().configure(config)

        def write_register(self, name, value):
            self.values[name] = value
            self.calls.append((name, value))
            return {"name": name, "value": value}

        def read_all(self):
            return dict(getattr(self, "values", {}))

        def command(self, name):
            if name == "start":
                assert self.values["laser_1_enable"] == 1
                assert self.values["axis_start_offset_volts"] == [0, 0, 10]
                assert self.values["command"] == 1
            return super().command(name)

    fake = LiveClient(settings, config, early=True)
    updated = False

    def publish(snapshot):
        nonlocal updated
        if not updated:
            updated = True
            controls.request({
                "axis_start_offset_volts": [123, -456, 10],
                "axis_calibration_volts_per_step": [7, 8, 2], "laser_1_enable": 0,
            })
            controls.apply(fake)

    filename = tmp_path / "live.h5"
    run = FlareAcquisition(
        settings, config, filename=filename, live_controls=controls,
        on_snapshot=publish, client_factory=lambda settings: fake,
    )
    result = run.run()
    assert result.get("error") is None, result
    assert result["complete"]
    assert result["registers"]["laser_1_enable"] == 1
    assert fake.values["laser_1_enable"] == 0
    events = result["live_register_updates"]
    assert [event["value"] for event in events if event["name"] == "laser_1_enable"] == [1, 0]
    assert [event["value"] for event in events if event["name"] == "axis_start_offset_volts"] == [
        [0, 0, 10], [123, -456, 10],
    ]
    sidecar = json.loads(filename.with_suffix(".flare.json").read_text())
    assert sidecar["live_register_updates"] == events
    assert all("readback" in event and "requested_at" in event for event in events)
    assert fake.calls.index("configure") < fake.calls.index(("laser_1_enable", 1)) < fake.calls.index("start")


@pytest.mark.parametrize("same_shape", [True, False])
def test_preview_run_copies_previous_image_and_discards_incompatible_geometry(monkeypatch, same_shape):
    config = configuration(frames=1, repetitions=1)
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0
    )
    seed = np.full((2, 3) if same_shape else (3, 2), 123, dtype=np.uint64)
    fake = FakeClient(settings, config, early=True)
    before_updates, snapshots = [], []

    def observe_update(image, *args):
        before_updates.append(image.copy())
        _update_preview_image(image, *args)

    monkeypatch.setattr("brighteyes_mcs.acquisition.flare._update_preview_image", observe_update)
    run = FlareAcquisition(
        settings, config, initial_image=seed, on_snapshot=snapshots.append,
        client_factory=lambda settings: fake,
    )
    seed.fill(999)  # The GUI's array must not be shared with the acquisition worker.
    assert run.run()["complete"]
    np.testing.assert_array_equal(before_updates[0], np.full((2, 3), 123 if same_shape else 0))
    np.testing.assert_array_equal(seed, np.full(seed.shape, 999))
    _, expected = raw_fixture(config)
    np.testing.assert_array_equal(
        snapshots[-1]["image"], expected.astype(np.uint64).sum(axis=1).reshape(2, 3, 3).sum(axis=-1)
    )


@pytest.mark.parametrize("channels", [25, 49])
def test_finite_acquisition_streams_before_start_response_and_saves_losslessly(tmp_path, channels):
    config = configuration(channels)
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0
    )
    fake = FakeClient(settings, config, early=True)
    snapshots = []
    filename = tmp_path / "capture.h5"
    run = FlareAcquisition(
        settings,
        config,
        filename=filename,
        on_snapshot=snapshots.append,
        client_factory=lambda settings: fake,
    )
    result = run.run()
    assert result.get("error") is None, result
    assert result["complete"] is True
    raw, expected = raw_fixture(config)
    assert filename.with_suffix(".flare.raw").read_bytes() == raw
    shape = (
        config["repetitions"],
        config["frames"],
        config["lines"],
        config["pixels"],
        config["bins_per_pixel"],
        channels,
    )
    with h5py.File(filename) as output:
        assert output["data"].dtype == np.uint32
        np.testing.assert_array_equal(output["data"][:], expected.reshape(shape))
    from brighteyes_mcs_reader import load

    loaded, metadata = load(filename)
    np.testing.assert_array_equal(loaded, expected.reshape(shape))
    assert metadata.nx == config["pixels"]
    assert metadata.dt == 1000
    convert_raw_acquisition(filename.with_suffix(".flare.json"), tmp_path / "converted.h5")
    with h5py.File(tmp_path / "converted.h5") as output:
        np.testing.assert_array_equal(output["data"][:], expected.reshape(shape))
    assert snapshots[-1]["bins"] == total_bins(config)
    assert fake.calls == ["configure", "start"]


@pytest.mark.parametrize("truncate,service_error", [(True, False), (False, True)])
def test_capture_failure_stays_partial_without_silently_stopping_hardware(
    tmp_path, truncate, service_error
):
    config = configuration()
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0
    )
    fake = FakeClient(settings, config, truncate=truncate, service_error=service_error)
    result = FlareAcquisition(
        settings, config, filename=tmp_path / "bad.h5", client_factory=lambda settings: fake
    ).run()
    assert result["complete"] is False
    assert result["error"]
    metadata = json.loads((tmp_path / "bad.flare.json").read_text())
    assert metadata["complete"] is False
    assert "stop" not in fake.calls
    assert result["recovery_required"] is True


def test_cancel_before_configuration_does_not_touch_scan():
    settings = FlareSettings()
    fake = FakeClient(settings, configuration())
    run = FlareAcquisition(settings, configuration(), client_factory=lambda settings: fake)
    run.stop()
    result = run.run()
    assert result["result"] == "cancelled"
    assert fake.calls == []


def test_start_failure_preserves_original_error_without_retry_or_reset(tmp_path):
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0
    )
    fake = FakeClient(settings, configuration())
    command = fake.command

    def failed_start(name):
        command(name)
        raise FlareError("start response was lost")

    fake.command = failed_start
    result = FlareAcquisition(
        settings,
        configuration(),
        filename=tmp_path / "ambiguous.h5",
        client_factory=lambda settings: fake,
    ).run()
    assert result["complete"] is False
    assert result["error"] == "start response was lost"
    assert fake.calls == ["configure", "start"]
    assert result["recovery_required"] is True


def test_selected_channel_changes_preview_without_narrowing_saved_counts(tmp_path):
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0
    )
    config = configuration(frames=1, repetitions=1)
    fake = FakeClient(settings, config, early=True)
    snapshots = []
    runner = FlareAcquisition(
        settings, config, on_snapshot=snapshots.append, client_factory=lambda settings: fake
    )
    runner.display_channels = (3,)
    assert runner.run()["complete"]
    _, expected = raw_fixture(config)
    np.testing.assert_array_equal(
        snapshots[-1]["image"], expected[:, 3].reshape(2, 3, 3).sum(axis=-1)
    )


def test_native_flare_service_imports_with_ni_packages_forbidden():
    code = """
import sys
import importlib.abc
class BlockNi(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('nifpga', 'nifpga_fast_fifo_recv')):
            raise AssertionError('NI import attempted: ' + fullname)
sys.meta_path.insert(0, BlockNi())
from brighteyes_mcs.acquisition.flare import FlareAcquisition
from brighteyes_mcs.ui.qt.main_window import MainWindow
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_recording_rejects_overwrite_and_keeps_partial_on_failure(tmp_path):
    recording = FlareRecording(tmp_path / "scan.h5", configuration())
    recording.finish({"error": "test interrupted", "complete": False})
    with pytest.raises(FileExistsError):
        FlareRecording(tmp_path / "scan.h5", configuration())


def test_disk_writer_failure_cannot_report_a_successful_capture(tmp_path, monkeypatch):
    settings = FlareSettings(
        host="127.0.0.1", bind_host="127.0.0.1", receiver_host="127.0.0.1", receiver_port=0
    )
    fake = FakeClient(settings, configuration(), early=True)

    def disk_full(*args):
        raise OSError("disk full")

    monkeypatch.setattr(FlareRecording, "append", disk_full)
    result = FlareAcquisition(
        settings,
        configuration(),
        filename=tmp_path / "full.h5",
        client_factory=lambda settings: fake,
    ).run()
    assert not result["complete"]
    assert result["error"] == "disk full"
    with h5py.File(tmp_path / "full.h5") as output:
        assert not output.attrs["complete"]
        assert output.attrs["stored_bins"] == 0
