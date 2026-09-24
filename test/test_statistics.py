"""Statistics calculations must work without Qt or acquisition hardware."""

from datetime import datetime

import pytest

from brighteyes_mcs.ui.controllers.statistics import (
    acquisition_eta,
    completion_eta,
    format_total_duration,
    scan_duration_seconds,
)


def test_duration_includes_dimensions_frames_and_circular_factors():
    assert scan_duration_seconds(2, 5, 100, 200, 3, 4) == pytest.approx(2.4)
    assert scan_duration_seconds(
        2, 5, 100, 200, 3, 4, circular_points=8, circular_repetitions=2,
    ) == pytest.approx(38.4)
    assert scan_duration_seconds(2, 5, 0, 200) == 0


@pytest.mark.parametrize("seconds, expected", [
    (0, "00:00:00"), (-1, "00:00:00"), (3723.99, "01:03:02"),
    (90061, "25:01:01"),
])
def test_total_duration_preserves_display_order(seconds, expected):
    assert format_total_duration(seconds) == expected


def test_eta_preserves_fractional_duration_and_rolls_over_year():
    now = datetime(2026, 12, 31, 23, 59, 59, 750000)
    assert completion_eta(0.5, now=now) == "27/01/01 00:00:00"


@pytest.mark.parametrize("current, expected, eta", [
    ({"a": 50, "b": 75}, {"a": 100, "b": 100}, "26/09/25 00:00:10"),
    ({"a": -10}, {"a": 100}, "26/09/25 00:00:30"),
    ({"a": 110}, {"a": 100}, "26/09/24 23:59:50"),
    ({"a": 0}, {"a": 0}, "--"),
    ({}, {}, "--"),
    ({"a": 50, "b": 0}, {"a": 100, "b": -1}, "26/09/25 00:00:10"),
])
def test_acquisition_eta_uses_valid_slowest_fifo(current, expected, eta):
    assert acquisition_eta(
        40, current, expected, now=datetime(2026, 9, 24, 23, 59, 50),
    ) == eta
