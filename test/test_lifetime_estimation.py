"""Physical lifetime recovery, timing wrap, and photon-limited precision."""

import numpy as np
import pytest

from brighteyes_mcs.acquisition.lifetime import (
    flim_parameters_from_3samples, flim_map_to_hcl,
)


def estimate(counts, *, peak=0, lengths=(30, 30, 31), total_bins=91):
    return flim_parameters_from_3samples(
        *np.moveaxis(counts, -1, 0), T_cycle=25e-9,
        sample_idx=np.cumsum(lengths) - (np.asarray(lengths) + 1) / 2,
        peak_idx=peak, total_bins=total_bins, method="exponential", window_lengths=lengths,
    )


def test_equal_gates_recover_analytic_count_ratio_lifetime():
    # Two equal integration steps reduce counts by a factor of 16.
    tau, brightness, quality, valid = estimate(
        np.array([1600, 400, 100]), lengths=(30, 30, 30), total_bins=90,
    )
    assert valid
    assert tau == pytest.approx(2 / (3 * np.log(16)), rel=0.002)
    assert brightness == 2100
    assert 0 < quality < 1


@pytest.mark.parametrize("peak", [0, 14, 29, 30, 59, 60, 90])
@pytest.mark.parametrize("tau", [0.025, 0.12, 0.4, 0.8])
def test_recovers_lifetime_with_unequal_gates_and_peak_inside_any_gate(peak, tau):
    # Generate a full cyclic arrival histogram, then discard everything except gates.
    arrival = np.exp(-((np.arange(91) - peak) % 91) / (91 * tau))
    counts = np.array([arrival[:30].sum(), arrival[30:60].sum(), arrival[60:].sum()])
    measured, _, _, valid = estimate(counts * 10000, peak=peak)
    assert valid
    assert measured == pytest.approx(tau, rel=0.002)


def test_saturation_tracks_photon_precision_without_changing_lifetime():
    counts = np.array([160, 40, 10])
    tau, _, quality, valid = estimate(
        np.stack([counts, 100 * counts]), lengths=(30, 30, 30), total_bins=90,
    )
    assert valid.all()
    assert tau[0] == pytest.approx(tau[1])
    assert quality[1] > quality[0]


@pytest.mark.parametrize("counts,peak", [
    ([0, 0, 0], 0), ([100, 0, 0], 0), ([10, 10, 10], 0),
    ([1, 4, 16], 0), ([16, 4, 1], None), ([16, 4, 1], -1),
    ([np.nan, 4, 1], 0), ([-1, 4, 1], 0),
])
def test_unresolved_or_invalid_inputs_are_not_displayed_as_lifetimes(counts, peak):
    tau, brightness, quality, valid = estimate(
        np.array(counts), peak=peak, lengths=(30, 30, 30), total_bins=90,
    )
    assert not valid
    hue, chroma, lightness = flim_map_to_hcl(tau, brightness, quality, valid, 0, 1)
    assert (hue, chroma, lightness) == (0, 0, 0)


def test_multidimensional_images_and_chunking_keep_pixel_order():
    counts = np.broadcast_to([1600, 400, 100], (50, 51, 3)).copy()
    counts[4, 7] = 0
    tau, brightness, quality, valid = estimate(counts, lengths=(30, 30, 30), total_bins=90)
    assert tau.shape == brightness.shape == quality.shape == valid.shape == (50, 51)
    assert not valid[4, 7]
    assert valid.sum() == 2549
    np.testing.assert_allclose(tau[valid], 1 / (3 * np.log(4)), rtol=0.002)


def test_circular_estimator_remains_the_default():
    kwargs = dict(T_cycle=25e-9, sample_idx=[14.5, 44.5, 75], peak_idx=10, total_bins=91)
    default = flim_parameters_from_3samples(100, 20, 5, **kwargs)
    explicit = flim_parameters_from_3samples(100, 20, 5, method="circular", **kwargs)
    for actual, expected in zip(default, explicit, strict=True):
        np.testing.assert_array_equal(actual, expected)
