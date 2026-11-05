"""Shared lifetime estimation for NI and Flare DFD previews."""

import numpy as np


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

def flim_parameters_from_3samples(d1, d2, d3, T_cycle, sample_idx, peak_idx=None, total_bins=None):
    """
    Estimate lifetime and quality metrics from three sampled points.

    Tau is returned in T_cycle units, where 1.0 corresponds to one full cycle.
    Callers that need physical time can convert it afterwards, for example to ns.
    """
    if total_bins is None or total_bins <= 0:
        raise ValueError("total_bins must be provided and > 0")

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

    luminance = brightness.astype(float)
    luminance[~valid] = 0

    return h, c, luminance
