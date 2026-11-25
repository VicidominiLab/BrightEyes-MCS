"""Tag pulse widths calculated from configured FPGA scan periods."""

from decimal import Decimal


def tag_period_cycles(
    time_bin_cycles, time_bins, pixels_x, pixels_y,
    *, circular_points=1, circular_repetitions=1,
):
    """Return pixel, line and frame periods; exclude waits and frame repetitions."""
    pixel = time_bin_cycles * time_bins
    line = pixel * pixels_x * circular_points * circular_repetitions
    return pixel, line, line * pixels_y


def tag_duration_cycles(mode, period_cycles, duty_cycle, fixed_cycles, *, maximum=2**63 - 1):
    """Return the register width, rounded down; Follow X sends firmware sentinel 0."""
    if mode == "Follow X":
        return 0
    if mode == "Fixed cycles":
        cycles = fixed_cycles
    elif mode == "Duty cycle":
        cycles = Decimal(str(period_cycles)) * Decimal(str(duty_cycle)) / 100
    else:
        raise ValueError(f"Unknown tag duration mode: {mode!r}")
    return max(0, min(maximum, int(cycles)))


def tag_pulse_widths_ns(registers, clock_base_mhz):
    """Return X/Y/Z pulse widths in ns, resolving the firmware's zero fallback."""
    clock = Decimal(str(clock_base_mhz))
    if clock <= 0:
        raise ValueError("The FPGA clock frequency must be positive")
    pixel = registers["tag_clock_duration_cycles"]
    cycles = (
        pixel,
        registers.get("tag_y_clock_duration_cycles", 0) or pixel,
        registers.get("tag_z_clock_duration_cycles", 0) or pixel,
    )
    return tuple(Decimal(value) * 1000 / clock for value in cycles)


def tag_pulse_intervals(width_cycles, period_cycles, window_cycles, *, start_cycles=0):
    """Return absolute pulse intervals within a window and its continuation flag."""
    if width_cycles <= 0 or period_cycles <= 0 or window_cycles <= 0:
        return (), False
    stop = start_cycles + window_cycles
    first = max(0, (start_cycles // period_cycles) * period_cycles)
    if stop <= max(0, start_cycles):
        return (), False
    if width_cycles >= period_cycles:
        return ((max(0, start_cycles), stop),), True
    intervals = tuple(
        (max(start, start_cycles), min(start + width_cycles, stop))
        for start in range(first, stop, period_cycles)
        if start + width_cycles > start_cycles
    )
    last = ((stop - 1) // period_cycles) * period_cycles
    return intervals, bool(intervals and last + width_cycles > stop)


def tag_preview_windows(period_cycles, registers=None):
    """Select line-start excerpts and relevant last-pixel/last-line excerpts."""
    pixel, line, frame = period_cycles
    span = min(3 * pixel, line)
    if pixel <= 0 or line <= 0 or frame <= 0:
        return (("Start", 0, 0),)
    following = ("Line 2", line) if frame > line else ("Next frame", frame)
    windows = [("Line 1", 0, span), (*following, span)]
    registers = registers or {}
    if registers.get("tag_exclude_last_x", False):
        focus = (line if frame > line else 0) + line - span
        if all(start != focus for _, start, _ in windows):
            windows.append(("Line 2 end" if frame > line else "Line 1 end", focus, span))
    if registers.get("tag_exclude_last_y", False) or registers.get("tag_exclude_last_y_for_x", False):
        focus = frame - line
        if all(start != focus for _, start, _ in windows):
            windows.append(("Last line", focus, span))
    return tuple(sorted(windows, key=lambda window: window[1]))


def tag_edge_positions(edges, width, minimum_gap=10):
    """Space distinct edges schematically while preserving order and coincidence."""
    times = sorted(set(edges))
    if len(times) < 2 or width <= 0:
        return tuple((time, 0.0) for time in times)
    gap = min(minimum_gap, width / (1.5 * (len(times) - 1)))
    remaining = width - gap * (len(times) - 1)
    duration = times[-1] - times[0]
    return tuple(
        (time, index * gap + (time - times[0]) / duration * remaining)
        for index, time in enumerate(times)
    )


def tag_level_intervals(intervals, window_cycles, *, invert=False):
    """Return output HIGH intervals after applying the selected polarity."""
    if window_cycles <= 0:
        return ()
    if not invert:
        return tuple(intervals)
    result = []
    previous = 0
    for start, end in intervals:
        if start > previous:
            result.append((previous, start))
        previous = end
    if previous < window_cycles:
        result.append((previous, window_cycles))
    return tuple(result)


def tag_exclude_intervals(intervals, period_cycles, first_cycles=0, *, last_cycles=0):
    """Remove first/last regions of every period from active tag intervals."""
    if period_cycles <= 0 or first_cycles + last_cycles >= period_cycles:
        return ()
    if first_cycles <= 0 and last_cycles <= 0:
        return tuple(intervals)
    allowed_stop = period_cycles - last_cycles
    result = []
    for start, end in intervals:
        position = start
        while position < end:
            phase = position % period_cycles
            if phase < first_cycles:
                position = min(end, position + first_cycles - phase)
            elif phase >= allowed_stop:
                position = min(end, position + period_cycles - phase + first_cycles)
            else:
                allowed_end = min(end, position + allowed_stop - phase)
                result.append((position, allowed_end))
                position = allowed_end
    return tuple(result)


def tag_output_intervals(registers, period_cycles, window_cycles, *, start_cycles=0):
    """Return output HIGH intervals, idle levels, and continuation after exclusions."""
    pixel_period, line_period, frame_period = period_cycles
    pixel = registers["tag_clock_duration_cycles"]
    widths = (
        pixel, registers.get("tag_y_clock_duration_cycles", 0) or pixel,
        registers.get("tag_z_clock_duration_cycles", 0) or pixel,
    )
    # Probe one more cycle so a falling edge at the zoom boundary is distinguished
    # from a pulse continuing beyond it, including a simultaneous exclusion edge.
    active = [
        tag_pulse_intervals(width, period, window_cycles + 1, start_cycles=start_cycles)[0]
        for width, period in zip(widths, period_cycles, strict=True)
    ]
    if registers.get("tag_exclude_first_x", False):
        active[0] = tag_exclude_intervals(active[0], line_period, pixel_period)
    if registers.get("tag_exclude_first_y_for_x", False):
        active[0] = tag_exclude_intervals(active[0], frame_period, line_period)
    if registers.get("tag_exclude_first_y", False):
        active[1] = tag_exclude_intervals(active[1], frame_period, line_period)
    if registers.get("tag_exclude_last_x", False):
        active[0] = tag_exclude_intervals(active[0], line_period, last_cycles=pixel_period)
    if registers.get("tag_exclude_last_y_for_x", False):
        active[0] = tag_exclude_intervals(active[0], frame_period, last_cycles=line_period)
    if registers.get("tag_exclude_last_y", False):
        active[1] = tag_exclude_intervals(active[1], frame_period, last_cycles=line_period)
    idle_levels = tuple(bool(registers.get(name, False)) for name in (
        "tag_x_clock_invert", "tag_y_clock_invert", "tag_z_clock_invert",
    ))
    outputs = tuple(
        tag_level_intervals(
            tuple((start - start_cycles, min(end, start_cycles + window_cycles) - start_cycles)
                  for start, end in intervals if start < start_cycles + window_cycles),
            window_cycles, invert=inverted,
        )
        for intervals, inverted in zip(active, idle_levels, strict=True)
    )
    continues = tuple(
        any(start < start_cycles + window_cycles < end for start, end in intervals)
        for intervals in active
    )
    return outputs, idle_levels, continues
