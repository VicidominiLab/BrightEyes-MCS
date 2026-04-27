
"""Standalone channel skew estimation utilities.

This module provides a lightweight, dependency-free (NumPy-only) implementation
of per-channel skew estimation using FFT-based cross-correlation with
sub-bin quadratic peak refinement. It's intended to be copied into other
projects and used independently of brighteyes_flim or brighteyes_ism.

Functions
- estimate_channel_skew: estimate per-channel shifts (in bins) for a set of
  time histograms relative to a reference channel.

Usage example
-------------
>>> import numpy as np
>>> from channel_skew_estimator import estimate_channel_skew
>>> t = 256
>>> ch = 8
>>> # synthetic data: a reference pulse shifted progressively
>>> x = np.linspace(0, 2*np.pi, t)
>>> ref = np.exp(-0.5*(np.sin(x)*8)**2)
>>> data = np.stack([np.roll(ref, i) for i in range(ch)], axis=1)
>>> shifts, errors, meta = estimate_channel_skew(data, reference=None)
>>> print(shifts.shape)

"""

from typing import Optional, Tuple, Dict
import numpy as np


def _validate_histogram(arr: np.ndarray, name: str) -> Tuple[int, int]:
    arr = np.asarray(arr, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be 2D with shape (t, channels), got {arr.shape}")
    nbin, nch = int(arr.shape[0]), int(arr.shape[1])
    if nbin <= 0 or nch <= 0:
        raise ValueError(f"{name} must have positive dimensions, got {arr.shape}")
    return nbin, nch


def _apply_apodize(arr: np.ndarray) -> np.ndarray:
    n = arr.shape[0]
    window = np.hanning(n)
    return arr * window[:, None]


def _fft_cross_correlation(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return circular cross-correlation of 1D arrays a and b.

    cross = ifft(FFT(a) * conj(FFT(b))). We return the real part.
    """
    fa = np.fft.fft(a)
    fb = np.fft.fft(b)
    cross = np.fft.ifft(fa * np.conj(fb))
    return np.real(cross)


def _quadratic_peak_refine(corr: np.ndarray, peak_idx: int) -> float:
    """Refine peak location using quadratic interpolation around peak.

    Returns sub-sample offset relative to the integer peak index.
    """
    n = len(corr)
    left = (peak_idx - 1) % n
    right = (peak_idx + 1) % n
    ym = corr[peak_idx]
    yl = corr[left]
    yr = corr[right]
    denom = (yl - 2 * ym + yr)
    if denom == 0:
        return 0.0
    delta = 0.5 * (yl - yr) / denom
    return float(delta)


def estimate_channel_skew(
    data_hist: np.ndarray,
    reference_hist: Optional[np.ndarray] = None,
    reference_channel: Optional[int] = None,
    upsampling: int = 10,
    apodize: bool = False,
) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """Estimate per-channel temporal skew (in histogram bins).

    Parameters
    ----------
    data_hist : ndarray
        Time histograms with shape (t, channels) for the dataset to align.
    reference_hist : ndarray or None
        Optional reference histograms with shape (t, channels_ref). When
        provided, each column of `data_hist` is aligned to
        `reference_hist[:, reference_channel]`. When ``None``, the central
        channel of `data_hist` is used as reference.
    reference_channel : int or None
        Index of channel within `reference_hist` to use as reference. If
        ``None``, the middle channel is used.
    upsampling : int
        Present for API compatibility; quadratic refinement is used so this
        acts as a soft hint but is not required for correctness.
    apodize : bool
        If True, apply a Hanning window along the time axis to reduce edge
        artifacts.

    Returns
    -------
    shifts : ndarray
        1D array of length `channels` containing estimated shifts in bins.
        Positive values mean the data channel must be shifted to the right
        (increasing bin index) to align with the reference.
    errors : ndarray
        Heuristic per-channel uncertainty derived from the local
        cross-correlation peak curvature.
    meta : dict
        Diagnostic metadata including resolved reference channel index.
    """
    nbin, nch = _validate_histogram(data_hist, "data_hist")
    data = np.asarray(data_hist, dtype=float)

    if reference_hist is None:
        if reference_channel is None:
            ref_pos = int(nch // 2)
        else:
            ref_pos = int(reference_channel)
        if ref_pos < 0 or ref_pos >= nch:
            raise IndexError("reference_channel out of range for data_hist")
        ref = data[:, ref_pos : ref_pos + 1]
    else:
        nbin_r, nch_r = _validate_histogram(reference_hist, "reference_hist")
        if nbin_r != nbin:
            raise ValueError("data_hist and reference_hist must have same time bins (t)")
        ref_array = np.asarray(reference_hist, dtype=float)
        if reference_channel is None:
            ref_pos = int(nch_r // 2)
        else:
            ref_pos = int(reference_channel)
        if ref_pos < 0 or ref_pos >= nch_r:
            raise IndexError("reference_channel out of range for reference_hist")
        ref = ref_array[:, ref_pos : ref_pos + 1]

    if apodize:
        data = _apply_apodize(data)
        ref = _apply_apodize(ref)

    shifts = np.zeros(nch, dtype=float)
    errors = np.full(nch, np.nan, dtype=float)

    ref_vec = ref[:, 0]

    for i in range(nch):
        sig = data[:, i]
        # cross-correlation via FFT
        corr = _fft_cross_correlation(sig, ref_vec)
        # shift zero-lag to center for signed displacement
        corr = np.fft.fftshift(corr)
        peak_idx = int(np.argmax(corr))
        # integer shift relative to center
        center = nbin // 2
        int_shift = peak_idx - center
        # quadratic refinement for sub-bin precision
        delta = _quadratic_peak_refine(corr, peak_idx)
        subbin_shift = float(int_shift) + delta
        shifts[i] = subbin_shift
        left = corr[(peak_idx - 1) % nbin]
        mid = corr[peak_idx]
        right = corr[(peak_idx + 1) % nbin]
        curvature = left - 2 * mid + right
        if curvature < 0:
            errors[i] = 1.0 / np.sqrt(abs(curvature) + 1e-12)

    meta = {
        "reference_channel_resolved": int(ref_pos),
        "reference_position": int(ref_pos),
    }

    return -shifts, errors, meta



if __name__ == "__main__":
    # quick smoke test
    import numpy as _np

    t = 256
    ch = 8
    x = _np.linspace(0, 2 * _np.pi, t, endpoint=False)
    base = _np.exp(-0.5 * (_np.sin(x) * 8) ** 2)
    data = _np.stack([_np.roll(base, i * 3) for i in range(ch)], axis=1)
    shifts, errs, meta = estimate_channel_skew(data, reference_hist=None)
    print("shifts:", shifts)

    
