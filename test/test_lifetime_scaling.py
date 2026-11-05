import numpy as np

from brighteyes_mcs.acquisition.lifetime import circular_mean_from_positions
from brighteyes_mcs.ui.lifetime_scaling import (
    analyze_lifetime_histograms, apply_equalization, equalization_lut, inverse_equalization,
    sample_lifetime_data,
)


def test_zero_count_lifetimes_do_not_divide_by_zero():
    with np.errstate(divide="raise", invalid="raise"):
        mean, spread = circular_mean_from_positions([[0, 0, 0], [1, 0, 0]], [0.1, 0.3, 0.7])
        scalar_mean, _ = circular_mean_from_positions([0, 0, 0], [0.1, 0.3, 0.7])
    assert np.isnan(mean[0]) and np.isnan(spread[0]) and np.isnan(scalar_mean)
    np.testing.assert_allclose(mean[1], 0.1)


def test_equalization_expands_a_narrow_distribution_and_preserves_order():
    values = np.linspace(0.3, 0.4, 1000)
    lut = equalization_lut(values)
    mapped = apply_equalization(values, lut)
    assert np.ptp(mapped) > 0.95
    assert np.all(np.diff(mapped) >= 0)
    assert equalization_lut(np.ones(20)) is None
    assert equalization_lut([]) is None


def test_inverse_equalization_uses_monotone_scale_and_keeps_fit_endpoints():
    values = 0.2 + 0.5 * np.linspace(0, 1, 1000) ** 3
    lut = equalization_lut(values)
    ticks = np.linspace(0, 1, 5)
    labels = inverse_equalization(ticks, lut)
    assert np.all(np.diff(labels) > 0)
    np.testing.assert_allclose(labels[[0, -1]], [values.min(), values.max()])
    np.testing.assert_allclose(apply_equalization(labels[1:-1], lut), ticks[1:-1])
    np.testing.assert_allclose(inverse_equalization(ticks, None), ticks)


def test_analysis_samples_are_bounded_and_exclude_invalid_pixels():
    h = np.ones((1000, 1000)) * 0.3
    valid = np.ones_like(h, dtype=bool)
    valid[::2, ::2] = False
    samples = sample_lifetime_data(h, h, h, valid)
    assert samples.shape[0] <= 65536
    assert samples.shape[1] == 3
    wide = np.ones((1, 100000))
    assert len(sample_lifetime_data(wide, wide, wide, wide)) <= 65536


def test_histogram_equalization_keeps_lifetime_units_in_histogram_ranges():
    samples = np.column_stack((np.linspace(0.3, 0.4, 1000),
                               np.ones(1000), np.linspace(10, 20, 1000)))
    result = analyze_lifetime_histograms(samples, {"H": (0, 1), "C": (0, 1), "L": (0, 100)},
                                         {"C": False, "L": True}, (1, 99), {"H": True, "L": True})
    assert result["ranges"]["H"] == (0, 1)
    assert result["luts"]["H"] is not None and result["luts"]["L"] is not None
    np.testing.assert_allclose(result["ranges"]["L"], (10.1, 19.9))


def test_zero_anchored_brightness_keeps_upper_percentile_and_other_channels():
    samples = np.column_stack((np.linspace(0.3, 0.4, 1000),
                               np.linspace(0.2, 0.8, 1000), np.linspace(10, 20, 1000)))
    ranges = {"H": (0, 1), "C": (0, 1), "L": (0, 100)}
    result = analyze_lifetime_histograms(samples, ranges, {"C": True, "L": True},
                                         (5, 95), {}, auto_counts_zero=True)
    np.testing.assert_allclose(result["ranges"]["L"], (0, 19.5))
    assert result["bounds"]["L"][0] == 0
    np.testing.assert_allclose(result["ranges"]["C"], (0.23, 0.77))
    manual = analyze_lifetime_histograms(samples, dict(ranges, L=(12, 18)), {},
                                         (5, 95), {}, auto_counts_zero=True)
    assert manual["ranges"]["L"] == (12, 18)
