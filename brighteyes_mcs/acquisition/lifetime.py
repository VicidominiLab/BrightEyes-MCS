"""Shared lifetime estimation for NI and Flare DFD previews."""

from functools import lru_cache

import numpy as np


@lru_cache(maxsize=8)
def _exponential_window_lookup(total_bins, window_lengths, peak_idx):
    """Periodic single-exponential probabilities, integrated over actual bins.

    Profile out the unknown amplitude by normalizing the three window integrals.
    Lifetimes are in cycle units. The finite search range is 1/8 bin to one cycle.
    No background or instrument response is fitted.
    """
    log_tau = np.linspace(np.log(1 / (8 * total_bins)), np.log(0.999), 256)
    tau = np.exp(log_tau)
    delay = (np.arange(sum(window_lengths)) - peak_idx) % total_bins / total_bins
    delay -= delay.min()  # The common amplitude cancels; avoid underflow for partial cycles.
    decay = np.exp(-delay[None, :] / tau[:, None])
    ends = np.cumsum(window_lengths)
    probabilities = np.stack([
        decay[:, start:end].sum(axis=1)
        for start, end in zip(np.r_[0, ends[:-1]], ends, strict=True)
    ], axis=-1)
    probabilities /= probabilities.sum(axis=-1, keepdims=True)
    log_probabilities = np.log(np.maximum(probabilities, 1e-300))
    # Fisher information for log(tau); its inverse is relative variance.
    derivative = np.gradient(log_probabilities, log_tau, axis=0)
    information = np.sum(probabilities * derivative**2, axis=-1)
    return log_tau, log_probabilities, information


def exponential_parameters_from_3windows(d1, d2, d3, *, total_bins,
                                         window_lengths, peak_idx):
    """Poisson maximum-likelihood lifetime with a known global excitation peak.

    Returns tau (cycles), photon counts, precision saturation and validity.
    The profiled Poisson likelihood equals a multinomial window likelihood.
    Saturation is 1/(1 + relative standard error), conditional on this model.
    Boundary solutions and missing timing references are invalid, not lifetimes
    silently clamped to the search limits.
    """
    weights = np.stack(np.broadcast_arrays(d1, d2, d3), axis=-1).astype(float)
    brightness = weights.sum(axis=-1)
    tau = np.full(brightness.shape, np.nan)
    quality = np.zeros(brightness.shape)
    valid = np.zeros(brightness.shape, dtype=bool)
    if peak_idx is None or not np.isfinite(peak_idx) or peak_idx < 0:
        return tau, brightness, quality, valid
    lengths = tuple(int(value) for value in window_lengths)
    if (len(lengths) != 3 or min(lengths) <= 0 or total_bins <= 0
            or sum(lengths) > total_bins):
        return tau, brightness, quality, valid
    log_tau, log_p, information = _exponential_window_lookup(
        int(total_bins), lengths, int(peak_idx) % int(total_bins),
    )
    usable = np.flatnonzero(
        ((brightness > 0) & np.isfinite(weights).all(axis=-1)
         & (weights >= 0).all(axis=-1)).ravel()
    )
    # Bound temporary memory independently of the number of pixels in a packet.
    for start in range(0, len(usable), 2048):
        pixels = usable[start:start + 2048]
        counts = weights.reshape(-1, 3)[pixels]
        likelihood = counts @ log_p.T
        best = np.argmax(likelihood, axis=1)
        interior = (best > 0) & (best < len(log_tau) - 1)
        pixels, best = pixels[interior], best[interior]
        if not len(pixels):
            continue
        rows = np.flatnonzero(interior)
        left = likelihood[rows, best - 1]
        center = likelihood[rows, best]
        right = likelihood[rows, best + 1]
        curvature = left - 2 * center + right
        offset = np.divide(0.5 * (left - right), curvature,
                           out=np.zeros_like(center), where=curvature < 0)
        estimate = log_tau[best] + np.clip(offset, -0.5, 0.5) * (log_tau[1] - log_tau[0])
        precision = np.sqrt(brightness.ravel()[pixels] * np.interp(estimate, log_tau, information))
        tau.ravel()[pixels] = np.exp(estimate)
        quality.ravel()[pixels] = precision / (1 + precision)
        valid.ravel()[pixels] = precision > 1e-6
    return tau, brightness, quality, valid


def circular_mean_from_positions(weights, phases):
    """
    weights : (..., M)
    phases  : (M,) in [0, 1), referred to the full T_cycle

    Returns
    -------
    mean_phase : (...) in [0, 1)
    std_phase  : (...) in cycle units
    """
    weights = np.asarray(weights, dtype=float)
    phases = np.asarray(phases, dtype=float)

    angles = 2.0 * np.pi * phases
    z = np.sum(weights * np.exp(1j * angles), axis=-1)

    wsum = np.sum(weights, axis=-1)
    z = np.divide(z, wsum, out=np.full_like(z, complex(np.nan, np.nan)), where=wsum > 0)

    mean_angle = np.mod(np.angle(z), 2.0 * np.pi)
    mean_phase = mean_angle / (2.0 * np.pi)

    R = np.abs(z)
    std_angle = np.sqrt(np.maximum(0.0, -2.0 * np.log(np.clip(R, 1e-15, 1.0))))
    std_phase = std_angle / (2.0 * np.pi)

    return mean_phase, std_phase

def flim_parameters_from_3samples(d1, d2, d3, T_cycle, sample_idx, peak_idx=None,
                                  total_bins=None, method="circular", window_lengths=None):
    """
    Estimate lifetime and quality metrics from three sampled points.

    Tau is returned in T_cycle units, where 1.0 corresponds to one full cycle.
    Callers that need physical time can convert it afterwards, for example to ns.
    """
    if total_bins is None or total_bins <= 0:
        raise ValueError("total_bins must be provided and > 0")

    if method == "exponential":
        if window_lengths is None:
            raise ValueError("window_lengths must be provided for the exponential estimator")
        return exponential_parameters_from_3windows(
            d1, d2, d3, total_bins=total_bins,
            window_lengths=window_lengths, peak_idx=peak_idx,
        )
    if method != "circular":
        raise ValueError(f"Unknown lifetime estimator: {method}")

    weights = np.stack([d1, d2, d3], axis=-1).astype(float)
    sample_idx = np.asarray(sample_idx, dtype=float)
    sample_phase = np.mod(sample_idx / float(total_bins), 1.0)

    phase, std_circ = circular_mean_from_positions(weights, sample_phase)
    tau = phase
    if peak_idx is not None:
        peak_phase = np.mod(float(peak_idx), float(total_bins)) / float(total_bins)
        tau = np.mod(peak_phase-phase, 1.0)

    brightness = np.sum(weights, axis=-1)
    quality = std_circ
    valid = brightness > 0

    return tau, brightness, quality, valid

def flim_map_to_hcl(tau, brightness, quality, valid,
                    tau_min, tau_max,
                    log_brightness=True,
                    alpha=1.0):
    h = np.zeros_like(tau, dtype=float)
    mask = valid & np.isfinite(tau)
    if tau_max > tau_min:
        h[mask] = (tau[mask] - tau_min) / (tau_max - tau_min)
    h = np.clip(h, 0.0, 1.0)

    c = np.zeros_like(tau, dtype=float)
    c[valid] = np.clip(quality[valid], 0.0, 1.0)

    luminance = np.where(valid, brightness, 0.0).astype(float)

    return h, c, luminance
