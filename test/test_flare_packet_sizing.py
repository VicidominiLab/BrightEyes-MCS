"""Automatic Flare DMA batching across rates, formats and mode changes."""

from dataclasses import replace

import pytest

from brighteyes_mcs.acquisition.detectors.flare.config import (
    FlareSettings, automatic_packet_bins, check_transport, configuration_from_gui,
    stream_parameters, total_bins,
)
from test.test_flare import configuration
from test.test_flare_dfd import accepted, request


@pytest.mark.parametrize("channels", [25, 49])
@pytest.mark.parametrize("microseconds", [2, 5, 100, 1000, 10000])
@pytest.mark.parametrize("mode", ["normal", "DFD1", "DFD2"])
def test_auto_respects_latency_dma_and_burst_capacity(channels, microseconds, mode):
    settings = FlareSettings()
    if mode == "normal":
        config = configuration(channels, pixels=200, lines=200, frames=1, repetitions=1,
                               dwell=microseconds * 100)
    else:
        config = accepted(request(channels, pixels=200, lines=200, dwell=microseconds * 100,
                                  bins_per_pixel=91),
                          version=int(mode[-1]))
    _, dwell, _ = stream_parameters(config)
    settings = replace(settings, buffer_seconds=max(0.25, 64 * dwell / 100000000))
    packet = automatic_packet_bins(config, 100000000, settings)
    key = "packet_bins" if mode == "normal" else "packet_records"
    config[key] = packet
    size, dwell, _ = stream_parameters(config)
    assert 1 <= packet <= min(4096, total_bins(config))
    assert packet * size <= 8388607
    assert packet == 1 or packet * dwell / 100000000 <= 0.002
    slots = int(settings.buffer_seconds * 100000000 / (dwell * packet))
    assert slots >= min(32, (total_bins(config) + packet - 1) // packet)
    assert check_transport(config, 100000000, settings) > 0


def gui_values(**changes):
    values = dict(nx=200, ny=200, nframe=1, nrep=1, timebin_per_pixel=2,
                  time_resolution=5, spad_channels="25", calib_x=1, calib_y=1,
                  range_x=0, range_y=0, range_z=0, offset_x_um=0, offset_y_um=0,
                  dfd_enable=False)
    return dict(values, **changes)


def test_auto_recalculates_normal_dfd_normal_without_mutating_settings():
    settings = FlareSettings()
    normal = configuration_from_gui(gui_values(), 100000000, settings)
    dfd = configuration_from_gui(gui_values(dfd_enable=True, time_resolution=2,
                                           timebin_per_pixel=91), 100000000, settings)
    restored = configuration_from_gui(gui_values(), 100000000, settings)
    assert normal["packet_bins"] == 137  # About 16 KiB, rather than 480-byte packets.
    assert dfd["packet_records"] == 8
    assert "packet_bins" not in dfd
    assert normal == restored
    assert settings.packet_bins == 0


def test_auto_uses_discovered_clock_and_record_size():
    config = configuration(dwell=500, pixels=200, lines=200)
    settings = FlareSettings()
    assert automatic_packet_bins(config, 100000000, settings) == 137
    assert automatic_packet_bins(dict(config, channels=49), 100000000, settings) == 76
    # At 1 MHz the same cycle count is a much longer exposure.
    assert automatic_packet_bins(config, 1000000, settings) == 4


@pytest.mark.parametrize("channels", [25, 49])
@pytest.mark.parametrize("microseconds,expected", [(2, 8), (5, 4), (100, 1)])
def test_dfd3_auto_batches_more_records_without_exceeding_latency(channels, microseconds, expected):
    from test.test_flare_v19 import FIRMWARE

    settings = FlareSettings()
    config = configuration_from_gui(
        gui_values(dfd_enable=True, time_resolution=microseconds,
                   timebin_per_pixel=91, spad_channels=str(channels)),
        100000000, settings, firmware=FIRMWARE,
    )
    size, dwell, packet = stream_parameters(config)
    assert packet == expected
    assert packet == 1 or packet * dwell / 100000000 <= 0.002
    assert packet * size <= 8388607
    assert check_transport(config, 100000000, settings) > 0


def test_auto_small_buffer_reduces_batch_and_impossible_buffer_fails():
    config = configuration(dwell=500, pixels=200, lines=200)
    settings = FlareSettings(buffer_seconds=0.001)
    assert automatic_packet_bins(config, 100000000, settings) == 3
    with pytest.raises(ValueError, match="completion burst"):
        automatic_packet_bins(dict(config, dwell=10000), 100000000, settings)
    with pytest.raises(ValueError, match="256 MiB"):
        automatic_packet_bins(config, 100000000, replace(settings, buffer_seconds=100))


def test_auto_caps_to_finite_acquisition_and_retains_manual_profiles():
    values = gui_values(nx=1, ny=1, timebin_per_pixel=1)
    assert configuration_from_gui(values, 100000000, FlareSettings())["packet_bins"] == 1
    settings = FlareSettings.from_legacy({"flare_packet_bins": 128}).validate()
    assert configuration_from_gui(values, 100000000, settings)["packet_bins"] == 128
    assert FlareSettings.from_legacy(FlareSettings().legacy_values()).packet_bins == 0
    for packet in (-1, True, 4097):
        with pytest.raises(ValueError, match="packet_bins"):
            FlareSettings(packet_bins=packet).validate()
