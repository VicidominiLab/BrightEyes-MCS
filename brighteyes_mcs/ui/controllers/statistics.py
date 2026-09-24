"""Scan statistics without Qt, hardware access, or an implicit clock.

Durations describe scan data only; startup waits and disk flushing are excluded.
The unusual hours:seconds:minutes total-time display is a compatibility choice.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta


def scan_duration_seconds(
    time_resolution_us: float,
    time_bins: int,
    pixels_x: int,
    pixels_y: int,
    frames: int = 1,
    repetitions: int = 1,
    *,
    circular_points: int = 1,
    circular_repetitions: int = 1,
) -> float:
    """Return configured scan time; omit frames/repetitions for a single frame."""
    return (
        time_resolution_us * time_bins * circular_points * circular_repetitions
        * pixels_x * pixels_y * frames * repetitions * 1e-6
    )


def format_total_duration(seconds: float) -> str:
    """Display hh:ss:mm, truncating fractional seconds without wrapping hours."""
    hours, remainder = divmod(int(max(0.0, seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{seconds:02d}:{minutes:02d}"


def completion_eta(seconds: float, *, now: datetime) -> str:
    """Format completion in the caller's clock/timezone, preserving fractions."""
    return (now + timedelta(seconds=seconds)).strftime("%y/%m/%d %H:%M:%S")


def acquisition_eta(
    duration_seconds: float,
    fifo_elements: Mapping[str, int],
    expected_fifo_elements: Mapping[str, int],
    *,
    now: datetime,
) -> str:
    """Estimate remaining time from the least-complete valid FIFO."""
    fractions = [
        max(0.0, min(1.0, fifo_elements[fifo] / expected))
        for fifo, expected in expected_fifo_elements.items()
        if expected > 0
    ]
    if not fractions:
        return "--"
    return completion_eta(duration_seconds * (1.0 - min(fractions)), now=now)
