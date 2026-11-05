import numpy as np
import pytest

from brighteyes_mcs.acquisition.flare_trace import FlareTrace, records_per_trace_bin


def test_trace_integrates_across_packet_boundaries_and_normalizes_rate():
    trace = FlareTrace()
    trace.update([2, 4], 0.001, 0.003, 10)
    assert trace.snapshot()["trace"].size == 0
    trace.update([6, 8, 10, 12, 14], 0.001, 0.003, 10)
    np.testing.assert_allclose(trace.snapshot()["trace"], [4000, 10000])
    np.testing.assert_allclose(trace.snapshot()["trace_times"], [0, 0.003])
    trace.update([16, 18], 0.001, 0.003, 10)
    np.testing.assert_allclose(trace.snapshot()["trace"], [4000, 10000, 16000])


def test_trace_uses_actual_dfd_window_durations():
    trace = FlareTrace()
    trace.update([3, 5, 7], [0.002, 0.004, 0.003], 0.005, 10)
    np.testing.assert_allclose(trace.snapshot()["trace"], [8 / 0.006])
    trace.update([9], [0.004], 0.005, 10)
    np.testing.assert_allclose(trace.snapshot()["trace_times"], [0, 0.006])
    np.testing.assert_allclose(trace.snapshot()["trace"], [8 / 0.006, 16 / 0.007])


def test_trace_live_binning_changes_and_history_limit():
    trace = FlareTrace()
    trace.update([1, 1, 1], 0.001, 0.002, 10)
    trace.update([2, 2, 2, 2], 0.001, 0.004, 10)
    np.testing.assert_allclose(trace.snapshot()["trace_times"], [0.003])
    np.testing.assert_allclose(trace.snapshot()["trace"], [2000])
    trace.update([4] * 8, 0.001, 0.004, 0.005)
    np.testing.assert_allclose(trace.snapshot()["trace_times"], [0.011])


@pytest.mark.parametrize("requested,expected", [(0.01, 55), (0.01001, 55), (0.0100101, 56), (0, 1)])
def test_dfd_trace_width_rounds_up_to_complete_records(requested, expected):
    assert records_per_trace_bin(requested, 91 * 2e-6) == expected


def test_dfd_trace_integrates_all_91_phases_in_fixed_groups_across_packets():
    trace = FlareTrace()
    record_seconds = 91 * 2e-6
    group = records_per_trace_bin(0.01, record_seconds)
    histograms = np.arange(165 * 91, dtype=np.uint64).reshape(165, 91)
    counts = histograms.sum(axis=1)
    # A tiny duration perturbation must not alternate 55- and 56-record bins.
    durations = np.full(165, record_seconds * (1 - 2e-12))
    start = 0
    for end in (8, 53, 54, 55, 56, 109, 111, 165):
        trace.update(counts[start:end], durations[start:end], 0.01001, 10, records_per_bin=group)
        start = end
    np.testing.assert_allclose(
        trace.snapshot()["trace"],
        histograms.reshape(3, 55, 91).sum(axis=(1, 2)) / durations.reshape(3, 55).sum(axis=1),
    )
    np.testing.assert_allclose(trace.snapshot()["trace_times"], [0, 0.01001, 0.02002])
    assert trace.pending_records == 0


def test_dfd_fixed_groups_use_actual_exposure_and_discard_partial_bin_on_reconfigure():
    trace = FlareTrace()
    trace.update([3, 5, 7], [0.002, 0.004, 0.003], 0.005, 10, records_per_bin=2)
    np.testing.assert_allclose(trace.snapshot()["trace"], [8 / 0.006])
    assert trace.pending_records == 1
    trace.update([9], [0.004], 0.005, 10, records_per_bin=2)
    np.testing.assert_allclose(trace.snapshot()["trace"], [8 / 0.006, 16 / 0.007])
    trace.update([11], 0.002, 0.005, 10, records_per_bin=2)
    trace.update([13, 15, 17], 0.002, 0.006, 10, records_per_bin=3)
    np.testing.assert_allclose(trace.snapshot()["trace"], [45 / 0.006])
    np.testing.assert_allclose(trace.snapshot()["trace_times"], [0.015])
    trace.update([1], 0.002, 0.006, 10, records_per_bin=3)
    trace.reset()
    assert trace.pending_records == 0
    assert not trace.pending_counts and not trace.pending_seconds

