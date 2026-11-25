"""Tag duty cycles use their own scan periods, with firmware fallback at zero."""

import pytest
from itertools import product

from brighteyes_mcs.ui.controllers.tag_clock import (
    tag_duration_cycles, tag_period_cycles, tag_pulse_intervals, tag_pulse_widths_ns,
    tag_output_intervals, tag_level_intervals, tag_exclude_intervals,
    tag_preview_windows, tag_edge_positions,
)


def test_periods_use_line_and_frame_geometry_and_circular_factors():
    assert tag_period_cycles(80, 10, 5, 7) == (800, 4000, 28000)
    assert tag_period_cycles(80, 10, 5, 7, circular_points=3, circular_repetitions=2) == (
        800, 24000, 168000,
    )


def test_duty_cycles_scale_with_the_axis_period():
    pixel, line, frame = tag_period_cycles(80, 10, 5, 7)
    assert tag_duration_cycles("Duty cycle", pixel, 50, 19) == 400
    assert tag_duration_cycles("Duty cycle", line, 25, 19) == 1000
    assert tag_duration_cycles("Duty cycle", frame, 10, 19) == 2800
    assert tag_duration_cycles("Duty cycle", 15, 25, 19) == 3


def test_follow_and_fixed_modes_ignore_scan_period_changes():
    for period in (800, 16000, 123456789):
        assert tag_duration_cycles("Follow X", period, 50, 19) == 0
        assert tag_duration_cycles("Fixed cycles", period, 50, 19) == 19
    assert tag_duration_cycles("Fixed cycles", 800, 50, 0) == 0


def test_frame_duty_cycle_supports_widths_above_u32_and_limits_to_i64():
    _, _, frame = tag_period_cycles(40000, 1000, 1000, 1000)
    assert tag_duration_cycles("Duty cycle", frame, 50, 200) == 20_000_000_000_000
    assert tag_duration_cycles("Duty cycle", 2**53 + 1, 100, 200) == 2**53 + 1
    assert tag_duration_cycles("Duty cycle", 2**65, 100, 200) == 2**63 - 1
    assert tag_duration_cycles("Duty cycle", 2**65, 100, 200, maximum=0xFFFFFFFF) == 0xFFFFFFFF


def test_zero_and_unknown_modes():
    assert tag_duration_cycles("Duty cycle", 800, 0, 200) == 0
    with pytest.raises(ValueError, match="Unknown tag duration mode"):
        tag_duration_cycles("Unknown", 800, 50, 200)


def test_nanoseconds_use_the_actual_fpga_clock_and_zero_fallback():
    registers = {
        "tag_clock_duration_cycles": 37,
        "tag_y_clock_duration_cycles": 0,
        "tag_z_clock_duration_cycles": 79,
    }
    assert tag_pulse_widths_ns(registers, 40) == (925, 925, 1975)
    assert tag_pulse_widths_ns(registers, 80) == (462.5, 462.5, 987.5)
    registers.update(tag_x_clock_invert=True, tag_exclude_first_x=True)
    assert tag_pulse_widths_ns(registers, 40) == (925, 925, 1975)


def test_nanoseconds_preserve_large_integer_widths_and_reject_invalid_clock():
    assert tag_pulse_widths_ns({"tag_clock_duration_cycles": 2**53 + 1}, 40) == (
        225179981368524825, 225179981368524825, 225179981368524825,
    )
    assert tag_pulse_widths_ns({"tag_clock_duration_cycles": 0}, 40) == (0, 0, 0)
    with pytest.raises(ValueError, match="frequency must be positive"):
        tag_pulse_widths_ns({"tag_clock_duration_cycles": 37}, 0)


def test_preview_repeats_pixels_and_keeps_line_edges_on_the_same_scale():
    assert tag_pulse_intervals(400, 800, 2400) == (
        ((0, 400), (800, 1200), (1600, 2000)), False,
    )
    assert tag_pulse_intervals(400, 1600, 2400) == (((0, 400), (1600, 2000)), False)
    assert tag_pulse_intervals(1000, 4000, 2400) == (((0, 1000),), False)


def test_preview_marks_only_pulses_continuing_past_the_zoom():
    assert tag_pulse_intervals(20000, 8000000, 2400) == (((0, 2400),), True)
    assert tag_pulse_intervals(2400, 8000000, 2400) == (((0, 2400),), False)
    assert tag_pulse_intervals(800, 800, 2400) == (((0, 2400),), True)
    assert tag_pulse_intervals(900, 800, 2400) == (((0, 2400),), True)
    assert tag_pulse_intervals(0, 800, 2400) == ((), False)
    assert tag_pulse_intervals(400, 0, 0) == ((), False)


def test_polarity_inversion_complements_the_visible_signal():
    pulses, _ = tag_pulse_intervals(400, 800, 2400)
    assert tag_level_intervals(pulses, 2400) == pulses
    assert tag_level_intervals(pulses, 2400, invert=True) == (
        (400, 800), (1200, 1600), (2000, 2400),
    )
    assert tag_level_intervals((), 2400, invert=True) == ((0, 2400),)
    assert tag_level_intervals((), 0, invert=True) == ()


def test_exclusion_masks_repeat_and_clip_long_pulses():
    assert tag_exclude_intervals(((0, 80),), 30, 10) == ((10, 30), (40, 60), (70, 80))
    assert tag_exclude_intervals(((0, 80),), 30, 30) == ()
    assert tag_exclude_intervals(((0, 80),), 30, 0) == ((0, 80),)


@pytest.mark.parametrize("invert_x,invert_y,invert_z,exclude_x,exclude_y,exclude_y_for_x,last_x,last_y,last_for_x",
                         tuple(product((False, True), repeat=9)))
def test_output_waveforms_match_confirmed_exclusion_rules(
    invert_x, invert_y, invert_z, exclude_x, exclude_y, exclude_y_for_x, last_x, last_y, last_for_x,
):
    registers = dict(
        tag_clock_duration_cycles=2, tag_y_clock_duration_cycles=7,
        tag_z_clock_duration_cycles=20, tag_x_clock_invert=invert_x,
        tag_y_clock_invert=invert_y, tag_z_clock_invert=invert_z,
        tag_exclude_first_x=exclude_x, tag_exclude_first_y=exclude_y,
        tag_exclude_first_y_for_x=exclude_y_for_x,
        tag_exclude_last_x=last_x, tag_exclude_last_y=last_y, tag_exclude_last_y_for_x=last_for_x,
    )

    def expected(t):
        if t < 0:
            return invert_x, invert_y, invert_z
        x, y, z = t % 5 < 2, t % 15 < 7, t % 30 < 20
        first_x = (t % 15) < 5
        first_y = (t % 30) < 15
        last_pixel = (t % 15) >= 10
        last_line = (t % 30) >= 15
        skip_x = ((exclude_x and first_x) or (exclude_y_for_x and first_y)
                  or (last_x and last_pixel) or (last_for_x and last_line))
        skip_y = (exclude_y and first_y) or (last_y and last_line)
        return (x and not skip_x) ^ invert_x, (y and not skip_y) ^ invert_y, z ^ invert_z

    for window in (15, 60):
        outputs, idle, continues = tag_output_intervals(registers, (5, 15, 30), window)
        assert idle == expected(-1)
        for t in range(window):
            actual = tuple(any(start <= t < end for start, end in signal) for signal in outputs)
            assert actual == expected(t)
        assert continues == tuple(
            previous == following and previous != baseline
            for previous, following, baseline in zip(
                expected(window - 1), expected(window), idle, strict=True,
            )
        )


def test_first_x_is_skipped_again_on_every_line():
    registers = dict(tag_clock_duration_cycles=4, tag_exclude_first_x=True)
    outputs, _, _ = tag_output_intervals(registers, (10, 30, 60), 90)
    assert outputs[0] == ((10, 14), (20, 24), (40, 44), (50, 54), (70, 74), (80, 84))


def test_first_y_is_skipped_again_on_every_frame():
    registers = dict(tag_clock_duration_cycles=4, tag_y_clock_duration_cycles=5,
                     tag_exclude_first_y=True)
    outputs, _, _ = tag_output_intervals(registers, (10, 30, 60), 150)
    assert outputs[1] == ((30, 35), (90, 95))
    assert outputs[0][0] == (0, 4)


def test_first_line_for_x_suppresses_all_its_pixels_in_each_frame():
    registers = dict(tag_clock_duration_cycles=4, tag_exclude_first_y_for_x=True)
    outputs, _, _ = tag_output_intervals(registers, (10, 30, 60), 120)
    assert outputs[0] == ((30, 34), (40, 44), (50, 54), (90, 94), (100, 104), (110, 114))
    assert outputs[1][0] == (0, 4)
    registers['tag_exclude_first_x'] = True
    outputs, _, _ = tag_output_intervals(registers, (10, 30, 60), 120)
    assert outputs[0] == ((40, 44), (50, 54), (100, 104), (110, 114))


def test_single_pixel_lines_and_single_line_frames_can_be_fully_excluded():
    registers = dict(tag_clock_duration_cycles=4, tag_exclude_first_x=True,
                     tag_exclude_first_y=True)
    outputs, _, continues = tag_output_intervals(registers, (10, 10, 10), 30)
    assert outputs[:2] == ((), ())
    assert outputs[2] == ((0, 4), (10, 14), (20, 24))
    assert continues == (False, False, False)
    registers.update(tag_x_clock_invert=True, tag_y_clock_invert=True)
    outputs, idle, continues = tag_output_intervals(registers, (10, 10, 10), 30)
    assert outputs[:2] == (((0, 30),), ((0, 30),))
    assert idle == (True, True, False)
    assert continues == (False, False, False)


def test_long_pulse_stops_at_the_next_excluded_pixel_boundary():
    registers = dict(tag_clock_duration_cycles=40, tag_exclude_first_x=True)
    outputs, _, continues = tag_output_intervals(registers, (10, 30, 60), 30)
    assert outputs[0] == ((10, 30),)
    assert continues[0] is False
    registers['tag_exclude_first_x'] = False
    outputs, _, continues = tag_output_intervals(registers, (10, 30, 60), 30)
    assert outputs[0] == ((0, 30),)
    assert continues[0] is True


def test_follow_x_is_resolved_before_independent_exclusions():
    registers = dict(tag_clock_duration_cycles=400, tag_y_clock_duration_cycles=0,
                     tag_z_clock_duration_cycles=0, tag_exclude_first_x=True,
                     tag_exclude_first_y=True)
    outputs, idle, _ = tag_output_intervals(registers, (800, 1600, 3200), 2400)
    assert outputs == (((800, 1200),), ((1600, 2000),), ((0, 400),))
    assert idle == (False, False, False)


def test_removed_xor_flags_do_not_affect_the_preview():
    registers = dict(tag_clock_duration_cycles=400)
    expected = tag_output_intervals(registers, (800, 4000, 28000), 2400)
    registers.update(tag_yz_xor_x=True, tag_yz_xor_x_invert=True)
    assert tag_output_intervals(registers, (800, 4000, 28000), 2400) == expected


def test_pulse_windows_include_context_and_jump_to_late_lines_without_replaying_scan():
    assert tag_pulse_intervals(4, 10, 8, start_cycles=29) == (((30, 34),), False)
    assert tag_pulse_intervals(4, 10, 12, start_cycles=-2) == (((0, 4),), False)
    assert tag_pulse_intervals(4, 10, 2, start_cycles=2) == (((2, 4),), False)
    start = 10**15
    assert tag_pulse_intervals(4, 10, 30, start_cycles=start) == (
        ((start, start + 4), (start + 10, start + 14), (start + 20, start + 24)), False,
    )


def test_later_line_excerpts_reveal_resumed_tags_after_exclusions():
    registers = dict(tag_clock_duration_cycles=4, tag_exclude_first_x=True,
                     tag_exclude_first_y=True, tag_exclude_first_y_for_x=True)
    first, _, _ = tag_output_intervals(registers, (10, 1000, 100000), 30)
    following, _, _ = tag_output_intervals(registers, (10, 1000, 100000), 30, start_cycles=1000)
    assert first[:2] == ((), ())
    assert following[:2] == (((10, 14), (20, 24)), ((0, 4),))


def test_offset_output_window_matches_a_slice_of_the_full_signal():
    registers = dict(tag_clock_duration_cycles=4, tag_y_clock_duration_cycles=5,
                     tag_z_clock_duration_cycles=8, tag_exclude_first_x=True,
                     tag_exclude_first_y=True, tag_exclude_first_y_for_x=True,
                     tag_x_clock_invert=True, tag_y_clock_invert=True)
    full, _, _ = tag_output_intervals(registers, (10, 30, 60), 120)
    excerpt, _, _ = tag_output_intervals(registers, (10, 30, 60), 40, start_cycles=25)
    expected = tuple(tuple((max(start, 25) - 25, min(end, 65) - 25)
                           for start, end in signal if max(start, 25) < min(end, 65))
                     for signal in full)
    assert excerpt == expected


def test_preview_windows_show_next_line_or_next_single_line_frame():
    assert tag_preview_windows((800, 240000, 72000000)) == (
        ("Line 1", 0, 2400), ("Line 2", 240000, 2400),
    )
    assert tag_preview_windows((800, 1600, 3200)) == (
        ("Line 1", 0, 1600), ("Line 2", 1600, 1600),
    )
    assert tag_preview_windows((800, 800, 800)) == (
        ("Line 1", 0, 800), ("Next frame", 800, 800),
    )


def test_schematic_spacing_separates_distinct_edges_and_preserves_coincidence():
    positions = tag_edge_positions((0, 1, 1, 2, 1000), 200)
    assert tuple(time for time, _ in positions) == (0, 1, 2, 1000)
    assert positions[0][1] == 0
    assert positions[-1][1] == 200
    assert all(right - left >= 10 for (_, left), (_, right) in zip(
        positions[:-1], positions[1:], strict=True,
    ))


def test_last_exclusions_repeat_on_every_line_and_frame():
    registers = dict(tag_clock_duration_cycles=4, tag_y_clock_duration_cycles=5,
                     tag_exclude_last_x=True, tag_exclude_last_y=True)
    output, _, _ = tag_output_intervals(registers, (10, 30, 60), 120)
    assert output[0] == ((0, 4), (10, 14), (30, 34), (40, 44),
                         (60, 64), (70, 74), (90, 94), (100, 104))
    assert output[1] == ((0, 5), (60, 65))
    registers['tag_exclude_last_y_for_x'] = True
    output, _, _ = tag_output_intervals(registers, (10, 30, 60), 120)
    assert output[0] == ((0, 4), (10, 14), (60, 64), (70, 74))


def test_first_and_last_masks_can_exclude_every_tag_in_small_geometries():
    registers = dict(tag_clock_duration_cycles=4, tag_exclude_first_x=True,
                     tag_exclude_last_x=True, tag_exclude_first_y=True, tag_exclude_last_y=True)
    output, _, _ = tag_output_intervals(registers, (10, 20, 40), 80)
    assert output[:2] == ((), ())
    assert tag_exclude_intervals(((0, 100),), 30, 10, last_cycles=10) == (
        (10, 20), (40, 50), (70, 80),
    )


def test_last_tag_preview_includes_line_end_and_last_line_without_replaying_the_frame():
    windows = tag_preview_windows((800, 240000, 72000000), dict(
        tag_exclude_last_x=True, tag_exclude_last_y=True, tag_exclude_last_y_for_x=True,
    ))
    assert windows == (("Line 1", 0, 2400), ("Line 2", 240000, 2400),
                       ("Line 2 end", 477600, 2400), ("Last line", 71760000, 2400))
    assert len(tag_preview_windows((800, 800, 800), dict(tag_exclude_last_x=True,
               tag_exclude_last_y=True))) == 2
