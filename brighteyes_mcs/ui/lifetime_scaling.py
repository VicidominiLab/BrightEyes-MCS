"""Bounded, Qt-free histogram analysis for live lifetime displays."""

import numpy as np


def sample_lifetime_data(h, quality, counts, valid, max_samples=65536):
    stride = max(1, int(np.ceil(np.size(h) / max_samples)))
    arrays = [np.asarray(a).flat[::stride] for a in (h, quality, counts)]
    mask = np.asarray(valid, dtype=bool).flat[::stride].copy()
    for values in arrays:
        mask &= np.isfinite(values)
    return np.column_stack([values[mask] for values in arrays])


def equalization_lut(values):
    """Return a bounded CDF lookup table; constant/empty data keep linear scaling."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values) & (values >= 0) & (values <= 1)]
    if values.size < 2 or np.ptp(values) <= 1e-12:
        return None
    hist, edges = np.histogram(values, bins=256, range=(0, 1))
    cumulative = hist.cumsum().astype(float)
    baseline = cumulative[np.flatnonzero(hist)[0]]
    span = cumulative[-1] - baseline
    if span <= 0:
        return None
    return (0.5 * (edges[:-1] + edges[1:]), np.clip((cumulative - baseline) / span, 0, 1),
            (float(values.min()), float(values.max())))


def analyze_lifetime_histograms(samples, ranges, auto_ranges, percentiles, equalize,
                                repeat_hue=False, equalization_requests=None, auto_counts_zero=False):
    """Compute histograms, percentile ranges and equalization without Qt calls."""
    result = dict(bounds={}, ranges={}, histograms={}, luts={}, h_values=samples[:, 0].copy())
    result["equalization_requests"] = {
        key: generation for key, generation in (equalization_requests or {}).items()
        if equalize.get(key)
    }
    for index, key in enumerate(("H", "C", "L")):
        values = samples[:, index]
        if key in ("H", "C"):
            low, high = 0.0, 1.0
        elif values.size:
            low, high = float(values.min()), float(values.max())
            if high <= low:
                high = low + 1e-9
        else:
            low, high = ranges[key]
        current = ranges[key]
        if auto_ranges.get(key) and values.size:
            auto_low, auto_high = np.percentile(values, percentiles)
            if key == "L" and auto_counts_zero:
                auto_low = 0.0
                auto_high = max(float(auto_high), 1e-9)
            if auto_high <= auto_low:
                auto_low = min(0.0, auto_high)
                auto_high = max(auto_high, auto_low + 1e-9)
            current = (float(auto_low), float(auto_high))
            low, high = min(low, current[0]), max(high, current[1])
        current = (max(low, current[0]), min(high, current[1]))
        if current[0] >= current[1]:
            current = (low, high)
        if key == "H":
            center = 0.5 * sum(current)
            values = values + np.round(center - values)
        hist, edges = np.histogram(values, bins=100, range=(low, high))
        result["bounds"][key] = (low, high)
        result["ranges"][key] = current
        result["histograms"][key] = (0.5 * (edges[:-1] + edges[1:]), hist)
        lut = None
        if equalize.get(key):
            normalized = (values - current[0]) / max(current[1] - current[0], 1e-12)
            if key == "H" and repeat_hue:
                normalized = np.mod(normalized, 1.0)
            lut = equalization_lut(normalized)
        result["luts"][key] = lut
    return result


def apply_equalization(values, lut):
    if lut is None:
        return values
    return np.interp(values, *lut[:2], left=0.0, right=1.0)


def inverse_equalization(values, lut):
    """Invert a monotone CDF for scale labels, including its flat intervals."""
    values = np.clip(np.asarray(values, dtype=float), 0, 1)
    if lut is None:
        return values
    coordinates, cumulative = lut[:2]
    upper = np.clip(np.searchsorted(cumulative, values, side="left"), 1, len(cumulative) - 1)
    lower = upper - 1
    span = cumulative[upper] - cumulative[lower]
    fraction = np.divide(values - cumulative[lower], span,
                         out=np.zeros_like(values), where=span > 0)
    result = coordinates[lower] + fraction * (coordinates[upper] - coordinates[lower])
    # The first visible color represents the upper edge of the zero-CDF tail.
    first = max(0, np.searchsorted(cumulative, 0, side="right") - 1)
    limits = lut[2] if len(lut) > 2 else (coordinates[first], coordinates[-1])
    result = np.where(values <= 0, limits[0], result)
    return np.where(values >= 1, limits[1], result)
