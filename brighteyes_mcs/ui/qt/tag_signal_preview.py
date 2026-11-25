"""Readable excerpts of tag signals at the beginnings of successive scan lines."""

from decimal import Decimal

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..controllers.tag_clock import (
    tag_edge_positions, tag_level_intervals, tag_output_intervals, tag_preview_windows,
    tag_pulse_widths_ns,
)


def _ns_label(value):
    return f"{value:,.3f}".rstrip("0").rstrip(".") + " ns"


class TagSignalPreview(QWidget):
    """Show skipped tags and their resumption with spaced edges and --- breaks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(196)
        self.setAccessibleName("Tag signal preview")
        self._registers = {}
        self._clock_base_mhz = None
        self._period_cycles = None
        self.set_registers({"tag_clock_duration_cycles": 200}, 40, (400, 4000, 40000))

    def sizeHint(self):
        return QSize(560, 196)

    def minimumSizeHint(self):
        return QSize(340, 196)

    def set_registers(self, registers, clock_base_mhz, period_cycles):
        period_cycles = tuple(period_cycles)
        if (self._registers == registers and self._clock_base_mhz == clock_base_mhz
                and self._period_cycles == period_cycles):
            return
        self.pulse_widths_ns = tag_pulse_widths_ns(registers, clock_base_mhz)
        self._registers = dict(registers)
        self._clock_base_mhz = clock_base_mhz
        self._period_cycles = period_cycles
        self.pixel_period_ns = Decimal(period_cycles[0]) * 1000 / Decimal(str(clock_base_mhz))
        self._window_cycles = 3 * period_cycles[0]
        self.pulse_intervals_cycles, self._idle_levels, self.continues = tag_output_intervals(
            registers, period_cycles, self._window_cycles,
        )
        active_intervals = tuple(
            tag_level_intervals(signal, self._window_cycles, invert=idle)
            for signal, idle in zip(self.pulse_intervals_cycles, self._idle_levels, strict=True)
        )
        ns_per_cycle = Decimal(1000) / Decimal(str(clock_base_mhz))
        self.output_pulse_widths_ns = tuple(
            tuple(dict.fromkeys(
                Decimal(end - start) * ns_per_cycle for start, end in intervals
                if end < self._window_cycles or not continues
            ))
            for intervals, continues in zip(active_intervals, self.continues, strict=True)
        )
        self._inverted = tuple(bool(registers.get(key, False)) for key in (
            "tag_x_clock_invert", "tag_y_clock_invert", "tag_z_clock_invert",
        ))
        exclusions_x = []
        if registers.get("tag_exclude_first_x", False):
            exclusions_x.append("first X per line")
        if registers.get("tag_exclude_first_y_for_x", False):
            exclusions_x.append("X on first line")
        if registers.get("tag_exclude_last_x", False):
            exclusions_x.append("last X per line")
        if registers.get("tag_exclude_last_y_for_x", False):
            exclusions_x.append("X on last line")
        exclusions_y = []
        if registers.get("tag_exclude_first_y", False):
            exclusions_y.append("first Y per frame")
        if registers.get("tag_exclude_last_y", False):
            exclusions_y.append("last Y per frame")
        self._exclusions = (
            ", ".join(exclusions_x),
            ", ".join(exclusions_y),
            "",
        )
        self._labels = tuple(_ns_label(width) for width in self.pulse_widths_ns)
        self._panels = []
        pixel, line, frame = period_cycles
        context = max(1, pixel // 4)
        edges = {0}
        for label, focus, span in tag_preview_windows(period_cycles, registers):
            duration = context + span
            signals, _, continues = tag_output_intervals(
                registers, period_cycles, duration, start_cycles=focus - context,
            )
            annotations = ["", "", ""]
            marks = [[], [], []]
            first_line = frame > 0 and focus % frame < line
            last_line = frame > 0 and focus % frame >= frame - line
            if ((first_line and registers.get("tag_exclude_first_y_for_x", False))
                    or (last_line and registers.get("tag_exclude_last_y_for_x", False))):
                annotations[0] = "line skipped"
                marks[0].append((context, duration, "line skipped"))
            else:
                if line > 0 and focus % line == 0 and registers.get("tag_exclude_first_x", False):
                    annotations[0] = "skip first"
                    marks[0].append((context, min(context + pixel, duration), "skip"))
                if line > 0 and (focus + span) % line == 0 and registers.get("tag_exclude_last_x", False):
                    annotations[0] += " / skip last" if annotations[0] else "skip last"
                    marks[0].append((max(context, duration - pixel), duration, "skip"))
            if first_line and registers.get("tag_exclude_first_y", False):
                annotations[1] = "first tag skipped"
                marks[1].append((context, duration, "first tag skipped"))
            elif last_line and registers.get("tag_exclude_last_y", False):
                annotations[1] = "last tag skipped"
                marks[1].append((context, duration, "last tag skipped"))
            first_pixel = (focus % line) // pixel if line > 0 and pixel > 0 else 0
            self._panels.append(dict(
                label=label, focus=focus, span=span, duration=duration,
                signals=signals, continues=continues, annotations=annotations, marks=marks,
                first_pixel=first_pixel,
            ))
            edges.update((context, duration))
            if pixel > 0:
                edges.update(range(context, duration + 1, pixel))
            for signal in signals:
                for start, end in signal:
                    edges.update((start, end))
        self._context_cycles = context
        self._edge_times = tuple(sorted(edges))
        descriptions = [
            f"{axis}: {_ns_label(width)}, " + ("inverted" if inverted else "normal polarity")
            for axis, width, inverted in zip(
                "XYZ", self.pulse_widths_ns, self._inverted, strict=True
            )
        ]
        descriptions.append(
            "Line-start excerpts, " + _ns_label(self.pixel_period_ns)
            + " per pixel. --- marks omitted time or continuation. Distinct edges are "
            "spaced schematically; simultaneous X/Y/Z edges stay aligned. "
            "Duration labels give configured pulse widths in ns."
        )
        descriptions.extend(f"{axis} output: {label}" for axis, label in zip(
            "XYZ", self._labels, strict=True,
        ))
        descriptions.extend(
            f"{axis}: skip {exclusions}."
            for axis, exclusions in zip("XYZ", self._exclusions, strict=True) if exclusions
        )
        descriptions.extend(
            f"{panel['label']} {axis}: {annotation}."
            for panel in self._panels
            for axis, annotation in zip("XYZ", panel["annotations"], strict=True) if annotation
        )
        descriptions.append("Exclusions are applied before each axis's polarity inversion.")
        description = "\n".join(descriptions)
        self.setToolTip(description)
        self.setAccessibleDescription(description)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        foreground = palette.windowText().color()
        painter.setPen(foreground)
        painter.drawText(QRectF(4, 0, self.width() - 8, 18),
                         Qt.AlignmentFlag.AlignLeft, "Tag outputs - schematic")
        painter.drawText(QRectF(4, 0, self.width() - 8, 18),
                         Qt.AlignmentFlag.AlignRight, _ns_label(self.pixel_period_ns) + "/pixel")
        dark = foreground.lightness() > 128
        colors = ("#56b4e9", "#e69f00", "#33b99a") if dark else (
            "#0072b2", "#a86700", "#008065",
        )
        plot_left, plot_right = 82, max(202, self.width() - 38)
        count = len(self._panels)
        gap = 48 if count <= 2 else 28
        panel_width = (plot_right - plot_left - gap * (count - 1)) / count
        positions = dict(tag_edge_positions(self._edge_times, panel_width))
        pixel = self._period_cycles[0]
        context = self._context_cycles
        for index, panel in enumerate(self._panels):
            left = plot_left + index * (panel_width + gap)
            painter.setPen(foreground)
            painter.drawText(QRectF(left, 20, panel_width, 18),
                             Qt.AlignmentFlag.AlignCenter, panel["label"])
            grid_color = QColor(foreground)
            grid_color.setAlpha(40)
            painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
            boundaries = list(range(context, panel["duration"] + 1, pixel)) if pixel > 0 else []
            for boundary in boundaries:
                x = left + positions[boundary]
                painter.drawLine(int(x), 39, int(x), 172)
            painter.setPen(foreground)
            for number, (first, last) in enumerate(zip(
                boundaries[:-1], boundaries[1:], strict=True,
            ), 1):
                cell_left = left + positions[first]
                cell_width = positions[last] - positions[first]
                pixel_label = f"P{panel['first_pixel'] + number}"
                painter.save()
                label_width = painter.fontMetrics().horizontalAdvance(pixel_label)
                if label_width > cell_width - 6:
                    font = painter.font()
                    font.setPointSizeF(max(7.0, font.pointSizeF() * max(1, cell_width - 6) / label_width))
                    painter.setFont(font)
                painter.drawText(QRectF(cell_left, 178, cell_width, 18),
                                 Qt.AlignmentFlag.AlignCenter, pixel_label)
                painter.restore()
        for row, (name, label, color) in enumerate(zip(
            ("X: pixel", "Y: line", "Z: frame"), self._labels, colors, strict=True,
        )):
            top = 40 + row * 44
            high, low = top + 18, top + 35
            painter.setPen(foreground)
            painter.drawText(QRectF(4, top + 17, 74, 20),
                             Qt.AlignmentFlag.AlignVCenter, name)
            label = painter.fontMetrics().elidedText(
                label, Qt.TextElideMode.ElideMiddle, int(plot_right - plot_left)
            )
            painter.drawText(QRectF(plot_left, top - 2, plot_right - plot_left, 17),
                             Qt.AlignmentFlag.AlignCenter, label)
            for index, panel in enumerate(self._panels):
                left = plot_left + index * (panel_width + gap)
                right = left + panel_width
                intervals = panel["signals"][row]
                initial_high = bool(intervals and intervals[0][0] == 0)
                path = QPainterPath()
                path.moveTo(left, high if initial_high else low)
                for first, last in intervals:
                    first_x, last_x = left + positions[first], left + positions[last]
                    if first > 0:
                        path.lineTo(first_x, low)
                        path.lineTo(first_x, high)
                    path.lineTo(last_x, high)
                    if last < panel["duration"]:
                        path.lineTo(last_x, low)
                level = high if intervals and intervals[-1][1] == panel["duration"] else low
                path.lineTo(right, level)
                idle = high if self._idle_levels[row] else low
                if not panel["continues"][row] and level != idle:
                    path.lineTo(right, idle)
                painter.setPen(QPen(QColor(color), 1.8))
                painter.drawPath(path)
                if index < count - 1:
                    painter.drawText(QRectF(right, top + 16, gap, 22),
                                     Qt.AlignmentFlag.AlignCenter, "---")
                elif panel["continues"][row]:
                    painter.drawText(QRectF(right + 4, level - 11, 30, 22),
                                     Qt.AlignmentFlag.AlignCenter, "---")
                for first, last, annotation in panel["marks"][row]:
                    first_x = left + positions[first]
                    annotation_width = positions[last] - positions[first]
                    annotation = painter.fontMetrics().elidedText(
                        annotation, Qt.TextElideMode.ElideRight, int(annotation_width)
                    )
                    painter.setPen(foreground)
                    painter.drawText(QRectF(first_x, top + 18, annotation_width, 17),
                                     Qt.AlignmentFlag.AlignCenter, annotation)
        painter.setPen(foreground)
        painter.drawText(QRectF(plot_right + 4, 178, 30, 18),
                         Qt.AlignmentFlag.AlignCenter, "---")
