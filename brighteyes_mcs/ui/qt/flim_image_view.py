"""Custom ImageView with FLIM-aware histogram controls."""

from PySide6 import QtCore, QtGui, QtWidgets
import numpy as np
import pyqtgraph as pg
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from ..lifetime_scaling import (
    analyze_lifetime_histograms, apply_equalization, inverse_equalization, sample_lifetime_data,
)


_FIXED_RGB_LEVELS = [[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]
_HISTOGRAM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Lifetime histogram")


def control_modifier_selects_navigation(modifiers, inverted=False):
    """Return whether the Ctrl state selects preview navigation."""
    control_pressed = bool(
        modifiers & QtCore.Qt.KeyboardModifier.ControlModifier
    )
    return control_pressed != bool(inverted)


def auxiliary_modifier_selects_navigation(modifiers):
    """Return whether Ctrl+Shift selects auxiliary-position dragging."""
    required = (
        QtCore.Qt.KeyboardModifier.ControlModifier
        | QtCore.Qt.KeyboardModifier.ShiftModifier
    )
    return modifiers & required == required


def _lab_f_inv(t):
    delta = 6.0 / 29.0
    return np.where(
        t > delta,
        t ** 3,
        3.0 * (delta ** 2) * (t - 4.0 / 29.0),
    )


def lch_to_srgb(l, c, h):
    angle = 2.0 * np.pi * h
    a = c * np.cos(angle)
    b = c * np.sin(angle)

    fy = (l + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    x = 95.047 * _lab_f_inv(fx) / 100.0
    y = 100.0 * _lab_f_inv(fy) / 100.0
    z = 108.883 * _lab_f_inv(fz) / 100.0

    r_lin = 3.2406 * x - 1.5372 * y - 0.4986 * z
    g_lin = -0.9689 * x + 1.8758 * y + 0.0415 * z
    b_lin = 0.0557 * x - 0.2040 * y + 1.0570 * z

    rgb_lin = np.stack([r_lin, g_lin, b_lin], axis=-1)
    threshold = 0.0031308
    rgb = np.where(
        rgb_lin <= threshold,
        12.92 * rgb_lin,
        1.055 * np.power(np.clip(rgb_lin, 0.0, None), 1.0 / 2.4) - 0.055,
    )
    return np.clip(rgb, 0.0, 1.0)


def hsv_to_rgb(h, s, v):
    h = np.mod(np.asarray(h, dtype=float), 1.0)
    s = np.clip(np.asarray(s, dtype=float), 0.0, 1.0)
    v = np.clip(np.asarray(v, dtype=float), 0.0, 1.0)

    h6 = h * 6.0
    i = np.floor(h6).astype(int) % 6
    f = h6 - np.floor(h6)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)

    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


def hsl_to_rgb(h, s, l):
    h = np.mod(np.asarray(h, dtype=float), 1.0)
    s = np.clip(np.asarray(s, dtype=float), 0.0, 1.0)
    l = np.clip(np.asarray(l, dtype=float), 0.0, 1.0)

    c = (1.0 - np.abs(2.0 * l - 1.0)) * s
    h6 = h * 6.0
    x = c * (1.0 - np.abs(np.mod(h6, 2.0) - 1.0))
    m = l - 0.5 * c
    i = np.floor(h6).astype(int) % 6

    r1 = np.choose(i, [c, x, 0.0, 0.0, x, c])
    g1 = np.choose(i, [x, c, c, x, 0.0, 0.0])
    b1 = np.choose(i, [0.0, 0.0, x, c, c, x])
    rgb = np.stack([r1 + m, g1 + m, b1 + m], axis=-1)
    return np.clip(rgb, 0.0, 1.0)


def render_lifetime_rgb(h, quality, counts_norm, mode):
    mode = str(mode).lower()
    if mode == "hsv":
        return hsv_to_rgb(h, quality, counts_norm)
    if mode == "hsl":
        return hsl_to_rgb(h, quality, counts_norm)
    return lch_to_srgb(counts_norm * 100.0, quality * 100.0, h)


def wrap_phase_values(values, phase_range):
    values = np.asarray(values, dtype=float)
    low, high = map(float, phase_range)
    center = 0.5 * (low + high)
    return values + np.round(center - values)


class ResettableLinearRegionItem(pg.LinearRegionItem):
    def __init__(self, values, *args, **kwargs):
        super().__init__(values, *args, **kwargs)
        self._reset_region = tuple(values)

    def set_reset_region(self, values):
        self._reset_region = tuple(values)

    def mouseDoubleClickEvent(self, ev):
        self.setRegion(self._reset_region)
        ev.accept()


class ZoomableHistogramViewBox(pg.ViewBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, enableMenu=False, **kwargs)
        self.setMouseEnabled(x=False, y=False)
        self._default_x_range = (0.0, 1.0)

    def set_default_x_range(self, bounds, reset=False):
        low, high = map(float, bounds)
        if high <= low:
            high = low + 1e-12
        self._default_x_range = (low, high)
        self.setLimits(xMin=low, xMax=high)
        if reset:
            self.reset_x_range()

    def reset_x_range(self):
        low, high = self._default_x_range
        self.setXRange(low, high, padding=0.0)

    def wheelEvent(self, ev, axis=None):
        low, high = self.viewRange()[0]
        default_low, default_high = self._default_x_range
        full_span = max(default_high - default_low, 1e-12)
        span = max(high - low, 1e-12)

        factor = 1.25 ** (ev.delta() / 120.0)
        new_span = np.clip(span / factor, full_span * 1e-4, full_span)

        anchor = float(self.mapToView(ev.pos()).x())
        anchor = float(np.clip(anchor, low, high))
        anchor_fraction = np.clip((anchor - low) / span, 0.0, 1.0)

        new_low = anchor - anchor_fraction * new_span
        new_high = new_low + new_span

        if new_low < default_low:
            new_low = default_low
            new_high = new_low + new_span
        if new_high > default_high:
            new_high = default_high
            new_low = new_high - new_span

        self.setXRange(new_low, new_high, padding=0.0)
        ev.accept()
        self.sigRangeChangedManually.emit([True, False])

    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.reset_x_range()
            ev.accept()
            self.sigRangeChangedManually.emit([True, False])
            return
        super().mouseClickEvent(ev)


class ModifierGatedViewBox(pg.ViewBox):
    """ViewBox that tracks when navigation should affect the microscope."""

    sigAuxiliaryDrag = QtCore.Signal(float, float, bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._invert_control = False
        self._navigation_event_active = False

    @property
    def navigation_event_active(self):
        """Whether a permitted mouse navigation event is being processed."""
        return self._navigation_event_active

    def set_control_inverted(self, inverted):
        """Invert which Ctrl state applies navigation to the microscope."""
        self._invert_control = bool(inverted)

    def navigation_allowed(self, modifiers):
        """Return whether *modifiers* select microscope navigation."""
        return control_modifier_selects_navigation(
            modifiers,
            self._invert_control,
        )

    def _handle_navigation_event(self, ev, handler, axis):
        # Dragging and wheel zooming always manipulate the displayed image.
        # The modifier only decides whether the resulting range is also sent
        # to the microscopy position/range controls by ``axesRangeChanged``.
        self._navigation_event_active = self.navigation_allowed(ev.modifiers())
        try:
            handler(ev, axis=axis)
        finally:
            self._navigation_event_active = False

    def mouseDragEvent(self, ev, axis=None):
        if (
            ev.button() == QtCore.Qt.MouseButton.LeftButton
            and auxiliary_modifier_selects_navigation(ev.modifiers())
        ):
            # Match the displacement that ViewBox panning would produce, but
            # leave the displayed image range untouched.
            current = self.mapToView(ev.pos())
            previous = self.mapToView(ev.lastPos())
            self._navigation_event_active = False
            self.sigAuxiliaryDrag.emit(
                previous.x() - current.x(),
                previous.y() - current.y(),
                ev.isFinish(),
            )
            ev.accept()
            return
        self._handle_navigation_event(ev, super().mouseDragEvent, axis)

    def wheelEvent(self, ev, axis=None):
        self._handle_navigation_event(ev, super().wheelEvent, axis)


class FlimHistogramLUTItem(pg.HistogramLUTItem):
    sigFlimRangesChanged = QtCore.Signal(object)

    def __init__(self, image=None, fillHistogram=True, levelMode="mono",
                 gradientPosition="right", orientation="vertical"):
        super().__init__(
            image=image,
            fillHistogram=fillHistogram,
            levelMode=levelMode,
            gradientPosition=gradientPosition,
            orientation=orientation,
        )
        self._hcl_ranges = {"H": (0.0, 1.0), "C": (0.0, 1.0), "L": (0.0, 1.0)}
        self._hcl_plots = {}
        self._hcl_regions = {}
        self._hcl_curves = {}
        self._hcl_labels = {}
        self._hcl_bounds = {}
        self._hcl_plot_ranges_initialized = {"H": False, "C": False, "L": False}
        self._hcl_display_max = {"H": 1.0, "C": 1.0, "L": 1.0}
        self._suspend_hcl_range_signal = False
        self._color_lifetime_widgets_attached = False
        self._native_histogram_widgets_attached = True
        self._render_mode = "hcl"
        self._hue_display_range = (0.0, 1.0)
        self._hue_wrap = False
        self._hue_wrap_mode = "repeat"
        self._display_hue_shift = 0.0
        self._value_gamma = 1.0
        self._equalize = {"H": False, "L": False}
        self._equalization_luts = {}
        self._equalization_revision = 0
        self._equalization_requests = {"H": 0, "L": 0}
        self._equalization_applied = {"H": 0, "L": 0}
        self._auto_ranges = {"C": False, "L": False}
        self._percentiles = (1.0, 99.0)
        self._auto_counts_zero = False
        self._hl_colorbar_plot = None
        self._hl_colorbar_image = None
        self._hl_colorbar_rgb_key = None
        self._hl_hist_curve = None
        self._hl_hist_values = np.asarray([], dtype=float)
        self._hl_hover_line = None
        self._hl_hover_phase = None
        self._build_hl_colorbar()
        self._build_hcl_controls()
        self.deactivate_color_lifetime_mode()

    def _build_hl_colorbar(self):
        self._hl_colorbar_plot = pg.PlotItem()
        self._hl_colorbar_plot.setMenuEnabled(False)
        self._hl_colorbar_plot.setMouseEnabled(x=False, y=False)
        self._hl_colorbar_plot.hideButtons()
        self._hl_colorbar_plot.setAspectLocked(False)
        view_box = self._hl_colorbar_plot.getViewBox()
        view_box.invertX(True)
        view_box.invertY(False)
        view_box.setBorder(None)
        self._hl_colorbar_plot.showAxis("top")
        self._hl_colorbar_plot.showAxis("right")
        self._hl_colorbar_plot.hideAxis("bottom")
        self._hl_colorbar_plot.hideAxis("left")
        hidden_pen = pg.mkPen(color=(0, 0, 0, 0))
        for axis_name in ("bottom", "left"):
            axis = self._hl_colorbar_plot.getAxis(axis_name)
            axis.showLabel(False)
            axis.setStyle(showValues=False)
            axis.setPen(hidden_pen)
            axis.setTextPen(hidden_pen)
            axis.setTicks([])
        self._hl_colorbar_plot.getAxis("top").setHeight(36)
        self._hl_colorbar_plot.getAxis("right").setWidth(72)
        self._hl_colorbar_image = pg.ImageItem(axisOrder="row-major")
        self._hl_colorbar_plot.addItem(self._hl_colorbar_image)
        self._hl_hist_curve = pg.PlotCurveItem(
            pen=pg.mkPen(color=(255, 255, 255, 220), width=2)
        )
        self._hl_colorbar_plot.addItem(self._hl_hist_curve)
        self._hl_hover_line = pg.InfiniteLine(
            angle=0, movable=False, span=(0.72, 1.0), pen=pg.mkPen("w", width=2),
            label="", labelOpts=dict(position=0.6, anchors=[(0, 0), (0, 1)],
                                      color="w", fill=(0, 0, 0, 190)),
        )
        self._hl_hover_line.setZValue(100)
        self._hl_hover_line.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self._hl_colorbar_plot.addItem(self._hl_hover_line, ignoreBounds=True)
        self._hl_hover_line.hide()
        self._hl_colorbar_plot.setVisible(False)
        self._update_hl_colorbar()

    def _build_hcl_controls(self):
        base_row = 4
        for idx, key in enumerate(("H", "C", "L")):
            label = pg.LabelItem(justify="left")
            label.setText(f"{key} range")
            plot = pg.PlotItem(viewBox=ZoomableHistogramViewBox())
            plot.hideAxis("left")
            plot.setMinimumHeight(90)
            plot.setMaximumHeight(90)
            plot.setMenuEnabled(False)
            plot.showGrid(x=False, y=False, alpha=0.1)
            curve = pg.PlotCurveItem(fillLevel=0, brush=(120, 120, 120, 80))
            plot.addItem(curve)
            region = ResettableLinearRegionItem([0, 1], orientation="vertical", swapMode="block")
            region.sigRegionChanged.connect(self._emit_hcl_ranges_changed)
            plot.addItem(region)

            self._hcl_labels[key] = label
            self._hcl_plots[key] = plot
            self._hcl_curves[key] = curve
            self._hcl_regions[key] = region
            self._update_axis_representation(key)

    def set_render_mode(self, mode):
        mode = str(mode).lower()
        if mode not in {"hcl", "hsv", "hsl"}:
            mode = "hcl"
        if self._render_mode == mode:
            return
        self._render_mode = mode
        for key in ("H", "C", "L"):
            self._update_axis_representation(key)
        self._update_hl_colorbar()

    def set_hue_display_range(self, hue_range):
        if hue_range is None or len(hue_range) != 2:
            hue_range = (0.0, 1.0)
        start, stop = map(float, hue_range)
        start = np.clip(start, 0.0, 1.0)
        stop = np.clip(stop, 0.0, 1.0)
        if self._hue_display_range == (start, stop):
            return
        self._hue_display_range = (start, stop)
        self._update_hl_colorbar()

    def _map_hue_for_display(self, h):
        return self._palette_hue(self._hue_scale_position(h))

    def _hue_scale_position(self, h):
        h = np.asarray(h, dtype=float)
        if self._hue_wrap and self._hue_wrap_mode == "repeat":
            h = np.mod(h, 1.0)
        else:
            h = np.clip(h, 0.0, 1.0)
        return apply_equalization(h, self._equalization_luts.get("H") if self._equalize["H"] else None)

    def _palette_hue(self, h):
        start, stop = self._hue_display_range
        h = np.asarray(h, dtype=float)
        # Hue vis. supplies both endpoints. Repeat cycles the selected ramp;
        # Arc crosses 1/0 when the selected endpoint is below the start.
        if self._hue_wrap and self._hue_wrap_mode == "arc" and stop < start:
            stop += 1.0
        return np.mod(start + h * (stop - start) + self._display_hue_shift, 1.0)

    def _equalized_hue_scale(self):
        return self._equalize["H"] and self._equalization_luts.get("H") is not None

    def colorbar_lifetime_position(self, phase):
        low, high = self._hcl_ranges["H"]
        phase = wrap_phase_values(phase, (low, high))
        position = self._hue_scale_position((phase - low) / max(high - low, 1e-12))
        if self._equalized_hue_scale():
            return float(position)
        return float((low + position * (high - low)) * self._hcl_display_max["H"])

    def set_hover_lifetime(self, phase):
        self._hl_hover_phase = phase
        if phase is None or not self._color_lifetime_widgets_attached:
            self._hl_hover_line.hide()
            return
        self._hl_hover_line.show()
        self._hl_hover_line.setValue(self.colorbar_lifetime_position(phase))
        self._hl_hover_line.label.setFormat(f"{phase * self._hcl_display_max['H']:.3f} ns")

    def set_scaling(self, auto_quality=False, auto_counts=False,
                    percentiles=(1.0, 99.0), hue_wrap=False, hue_wrap_mode="repeat",
                    equalize_hue=False, equalize_counts=False, hue_offset=0.0, value_gamma=1.0,
                    auto_counts_zero=False):
        if not np.isfinite(value_gamma) or value_gamma <= 0:
            raise ValueError("V gamma must be finite and positive")
        previous_display = (self._hue_wrap, self._hue_wrap_mode, tuple(self._equalize.items()),
                            self._display_hue_shift, self._value_gamma)
        self._auto_ranges = {"C": bool(auto_quality), "L": bool(auto_counts)}
        self._auto_counts_zero = bool(auto_counts_zero)
        self._percentiles = tuple(sorted(np.clip(percentiles, 0.0, 100.0)))
        self._hue_wrap = bool(hue_wrap)
        self._hue_wrap_mode = hue_wrap_mode
        equalize = {"H": bool(equalize_hue), "L": bool(equalize_counts)}
        for key, enabled in equalize.items():
            if enabled != self._equalize[key]:
                self._equalization_requests[key] += 1
                if not enabled:
                    self._equalization_luts.pop(key, None)
        self._equalize = equalize
        self._display_hue_shift = float(hue_offset) % 1.0
        self._value_gamma = float(value_gamma)
        current_display = (self._hue_wrap, self._hue_wrap_mode, tuple(self._equalize.items()),
                           self._display_hue_shift, self._value_gamma)
        if current_display != previous_display:
            self._update_hl_colorbar()

    def _map_counts_for_display(self, counts):
        counts = apply_equalization(counts, self._equalization_luts.get("L") if self._equalize["L"] else None)
        if self._render_mode == "hsv" and self._value_gamma != 1.0:
            counts = np.power(np.clip(counts, 0, 1), 1.0 / self._value_gamma)
        return counts

    def pending_equalization(self):
        return {key: enabled and self._equalization_requests[key] != self._equalization_applied[key]
                for key, enabled in self._equalize.items()}

    def request_equalization(self, channel=None):
        for key, enabled in self._equalize.items():
            if enabled and channel in (None, key):
                self._equalization_requests[key] += 1

    def _display_key_name(self, key):
        if key == "H":
            return "H"
        if key == "C":
            return "S" if self._render_mode in {"hsv", "hsl"} else "C"
        if key == "L":
            return "V" if self._render_mode == "hsv" else "L"
        return key

    def _set_native_histogram_visible(self, visible):
        for attr in ("axis", "vb", "gradient", "plot"):
            item = getattr(self, attr, None)
            if item is not None:
                item.setVisible(visible)

    def _detach_native_histogram_widgets(self):
        if not self._native_histogram_widgets_attached:
            return
        for attr in ("axis", "vb", "gradient"):
            item = getattr(self, attr, None)
            if item is not None:
                self.layout.removeItem(item)
        self._native_histogram_widgets_attached = False

    def _attach_native_histogram_widgets(self):
        if self._native_histogram_widgets_attached:
            return
        avg = (0, 1, 2) if self.gradientPosition in {"right", "bottom"} else (2, 1, 0)
        if self.orientation == "vertical":
            native_layout = (
                ("axis", 0, avg[0]),
                ("vb", 0, avg[1]),
                ("gradient", 0, avg[2]),
            )
        else:
            native_layout = (
                ("axis", avg[0], 0),
                ("vb", avg[1], 0),
                ("gradient", avg[2], 0),
            )
        for attr, row, col in native_layout:
            item = getattr(self, attr, None)
            if item is not None:
                self.layout.addItem(item, row, col)
        self._native_histogram_widgets_attached = True

    def activate_color_lifetime_mode(self):
        self._detach_native_histogram_widgets()
        if not self._color_lifetime_widgets_attached:
            self.layout.addItem(self._hl_colorbar_plot, 0, 0, 4, 3)
            base_row = 4
            for idx, key in enumerate(("H", "C", "L")):
                self.layout.addItem(self._hcl_labels[key], base_row + idx * 2, 0, 1, 3)
                self.layout.addItem(self._hcl_plots[key], base_row + idx * 2 + 1, 0, 1, 3)
            self._color_lifetime_widgets_attached = True
        self._set_native_histogram_visible(False)
        if self._hl_colorbar_plot is not None:
            self._hl_colorbar_plot.setVisible(True)
        for key in ("H", "C", "L"):
            self._hcl_labels[key].setVisible(True)
            self._hcl_plots[key].setVisible(True)

    def deactivate_color_lifetime_mode(self):
        if self._hl_hover_line is not None:
            self.set_hover_lifetime(None)
        if self._hl_colorbar_plot is not None:
            self._hl_colorbar_plot.setVisible(False)
        for key in ("H", "C", "L"):
            self._hcl_labels[key].setVisible(False)
            self._hcl_plots[key].setVisible(False)
        if self._color_lifetime_widgets_attached:
            self.layout.removeItem(self._hl_colorbar_plot)
            for key in ("H", "C", "L"):
                self.layout.removeItem(self._hcl_labels[key])
                self.layout.removeItem(self._hcl_plots[key])
            self._color_lifetime_widgets_attached = False
        # Remove the colorbar's spanning cells before restoring the native
        # histogram. Qt rejects overlapping items even while they are hidden.
        self._attach_native_histogram_widgets()
        self._set_native_histogram_visible(True)

    def _update_hl_colorbar(self, width=192, height=192):
        if self._hl_colorbar_image is None:
            return

        rgb_key = (self._render_mode, self._hue_display_range, self._hue_wrap,
                   self._display_hue_shift, self._value_gamma,
                   self._hue_wrap_mode, tuple(self._equalize.items()),
                   self._equalization_revision, width, height)
        if rgb_key != self._hl_colorbar_rgb_key:
            h = np.tile(np.linspace(0.0, 1.0, height, dtype=float)[:, None], (1, width))
            h_display = self._palette_hue(h) if self._equalized_hue_scale() else self._map_hue_for_display(h)
            counts_norm = np.tile(np.linspace(0.0, 1.0, width, dtype=float), (height, 1))
            quality = np.ones((height, width), dtype=float)
            rgb = render_lifetime_rgb(h_display, quality, self._map_counts_for_display(counts_norm), self._render_mode)
            self._hl_colorbar_image.setImage(rgb, autoLevels=False)
            self._hl_colorbar_image.setLevels(_FIXED_RGB_LEVELS)
            self._hl_colorbar_rgb_key = rgb_key

        h_display_max = float(self._hcl_display_max.get("H", 1.0))
        h_range = self._hcl_ranges.get("H", (0.0, 1.0))
        l_range = self._hcl_ranges.get("L", (0.0, 1.0))
        h_low = float(h_range[0]) * h_display_max
        h_high = float(h_range[1]) * h_display_max
        l_low, l_high = map(float, l_range)
        if h_high <= h_low:
            h_high = h_low + 1e-12
        if l_high <= l_low:
            l_high = l_low + 1e-12

        equalized = self._equalized_hue_scale()
        y_low, y_high = (0.0, 1.0) if equalized else (h_low, h_high)
        self._hl_colorbar_image.setRect(QtCore.QRectF(l_low, y_low, l_high - l_low, y_high - y_low))
        self._hl_colorbar_plot.setYRange(y_low, y_high, padding=0)
        self._hl_colorbar_plot.setXRange(l_low, l_high, padding=0)
        top_axis = self._hl_colorbar_plot.getAxis("top")
        right_axis = self._hl_colorbar_plot.getAxis("right")
        top_axis.setLabel("counts")
        right_axis.setLabel("lifetime [ns]")
        top_axis.setTicks([[
            (l_low, f"{l_low:.3g}"),
            (0.5 * (l_low + l_high), f"{0.5 * (l_low + l_high):.3g}"),
            (l_high, f"{l_high:.3g}"),
        ]])
        positions = np.linspace(y_low, y_high, 5)
        if equalized:
            phases = inverse_equalization(positions, self._equalization_luts["H"])
            labels = h_low + phases * (h_high - h_low)
        else:
            labels = positions
        right_axis.setTicks([[(float(pos), f"{value:.3f}") for pos, value in zip(positions, labels, strict=True)]])

        if self._hl_hist_curve is not None:
            h_values = np.asarray(self._hl_hist_values, dtype=float)
            mask = np.isfinite(h_values)
            h_values = h_values[mask]
            h_range = self._hcl_ranges.get("H", (0.0, 1.0))
            if h_values.size == 0:
                self._hl_hist_curve.setData([], [])
            else:
                h_values_wrapped = wrap_phase_values(h_values, h_range)
                hist, edges = np.histogram(h_values_wrapped, bins=64, range=h_range)
                centers = 0.5 * (edges[:-1] + edges[1:])
                centers_ns = centers * h_display_max
                if equalized:
                    centers_ns = self._hue_scale_position((centers - h_range[0]) / max(h_range[1] - h_range[0], 1e-12))
                if np.max(hist) > 0:
                    hist_norm = hist / np.max(hist)
                    x_hist = l_low + hist_norm * (l_high - l_low)
                    self._hl_hist_curve.setData(x_hist, centers_ns)
                else:
                    self._hl_hist_curve.setData([], [])
        if self._hl_hover_phase is not None:
            self.set_hover_lifetime(self._hl_hover_phase)

    def _update_axis_representation(self, key):
        plot = self._hcl_plots[key]
        axis = plot.getAxis("bottom")
        display_max = float(self._hcl_display_max.get(key, 1.0))
        tick_values = [0.0, 0.5, 1.0]

        if key == "H":
            low, high = self._hcl_bounds.get(key, (0.0, 1.0))
            mid = 0.5 * (low + high)
            tick_values = [low, mid, high]
            tick_labels = [
                f"{low * display_max:.3f}",
                f"{mid * display_max:.3f}",
                f"{high * display_max:.3f}",
            ]
            axis.setLabel("lifetime [ns]")
            self._hcl_labels[key].setText(
                f"{self._display_key_name(key)} range ({low * display_max:.3f}..{high * display_max:.3f} ns)"
            )
        elif key == "C":
            tick_labels = ["0.0", "0.5", "1.0"]
            axis.setLabel("quality")
            self._hcl_labels[key].setText(f"{self._display_key_name(key)} range")
        else:
            low, high = self._hcl_bounds.get(key, (0.0, 1.0))
            mid = 0.5 * (low + high)
            tick_labels = [f"{low:.3g}", f"{mid:.3g}", f"{high:.3g}"]
            axis.setLabel("counts")
            self._hcl_labels[key].setText(f"{self._display_key_name(key)} range")

        axis.setTicks([list(zip(tick_values, tick_labels))])

    def set_flim_visible(self, visible):
        if visible:
            self.activate_color_lifetime_mode()
        else:
            self.deactivate_color_lifetime_mode()

    def set_image_gamma(self, gamma):
        if gamma == getattr(self, "_image_gamma", 1.0):
            return
        self._image_gamma = gamma
        self._setImageLookupTable()

    def _setImageLookupTable(self):
        if getattr(self, "_image_gamma", 1.0) != 1.0:
            self.imageItem().setLookupTable(self.getLookupTable)
        else:
            super()._setImageLookupTable()

    def getLookupTable(self, img=None, n=None, alpha=None):
        lut = super().getLookupTable(img, n, alpha)
        gamma = getattr(self, "_image_gamma", 1.0)
        if lut is None or gamma == 1.0:
            return lut
        positions = np.linspace(0, 1, len(lut)) ** (1 / gamma) * (len(lut) - 1)
        lower = positions.astype(int)
        upper = np.minimum(lower + 1, len(lut) - 1)
        fraction = (positions - lower)[:, None]
        return np.rint(lut[lower] * (1 - fraction) + lut[upper] * fraction).astype(np.uint8)

    def imageChanged(self, autoLevel=False, autoRange=False):
        # H/S/V histograms already use the source lifetime data. Computing the
        # hidden RGB histograms on every color conversion duplicates that work.
        if getattr(self, "_color_lifetime_widgets_attached", False):
            return
        return super().imageChanged(autoLevel=autoLevel, autoRange=autoRange)

    def set_flim_data(self, h, c, l, valid=None, h_display_max=None):
        if valid is None:
            valid = np.ones_like(h, dtype=bool)
        samples = sample_lifetime_data(h, c, l, valid)
        analysis = analyze_lifetime_histograms(
            samples, self.get_flim_ranges(), self._auto_ranges, self._percentiles,
            self.pending_equalization(), self._hue_wrap and self._hue_wrap_mode == "repeat",
            dict(self._equalization_requests),
            self._auto_counts_zero,
        )
        self.apply_analysis(analysis, h_display_max)

    def apply_analysis(self, analysis, h_display_max=None):
        if h_display_max is not None:
            self._hcl_display_max["H"] = max(float(h_display_max), 1e-12)
        self._hl_hist_values = analysis["h_values"]
        updated = False
        for key, generation in analysis.get("equalization_requests", {}).items():
            if self._equalize[key] and self._equalization_requests[key] == generation:
                self._equalization_luts[key] = analysis["luts"][key]
                self._equalization_applied[key] = generation
                updated = True
        if updated:
            self._equalization_revision += 1
        self.set_flim_visible(True)
        self._suspend_hcl_range_signal = True
        try:
            for key in ("H", "C", "L"):
                low, high = analysis["bounds"][key]
                self._hcl_bounds[key] = (low, high)
                self._hcl_curves[key].setData(*analysis["histograms"][key])
                plot_view = self._hcl_plots[key].getViewBox()
                plot_view.set_default_x_range(
                    (low, high), reset=not self._hcl_plot_ranges_initialized[key],
                )
                self._hcl_plot_ranges_initialized[key] = True
                current = analysis["ranges"][key]
                self._hcl_ranges[key] = current
                self._hcl_regions[key].setBounds((low, high))
                self._hcl_regions[key].set_reset_region((low, high))
                if tuple(self._hcl_regions[key].getRegion()) != tuple(current):
                    self._hcl_regions[key].setRegion(current)
                self._update_axis_representation(key)
            self._update_hl_colorbar()
        finally:
            self._suspend_hcl_range_signal = False
        self._emit_hcl_ranges_changed()

    def clear_flim_data(self):
        self._hcl_plot_ranges_initialized = {"H": False, "C": False, "L": False}
        self.deactivate_color_lifetime_mode()

    def get_flim_ranges(self):
        return dict(self._hcl_ranges)

    def _emit_hcl_ranges_changed(self):
        if self._suspend_hcl_range_signal:
            return
        for key, region in self._hcl_regions.items():
            self._hcl_ranges[key] = tuple(region.getRegion())
        self.sigFlimRangesChanged.emit(self.get_flim_ranges())


class GammaImageItem(pg.ImageItem):
    """Apply RGB display gamma after levels, retaining the original image data."""

    def __init__(self, *args, **kwargs):
        self._display_gamma = 1.0
        self._gamma_lut = None
        super().__init__(*args, **kwargs)

    def setGamma(self, gamma):
        if gamma == self._display_gamma:
            return
        self._display_gamma = gamma
        self._gamma_lut = np.rint(255 * (np.arange(256) / 255) ** (1 / gamma)).astype(np.uint8)
        self._renderRequired = True
        self.update()

    def render(self):
        super().render()
        if (self._unrenderable or self._display_gamma == 1 or self.image.ndim != 3
                or self.image.shape[-1] not in (3, 4)):
            return
        # Copy the rendered pixels before editing; Qt may share the original
        # image buffer. Preserve alpha and leave the scientific data untouched.
        rendered = self.qimage.convertToFormat(QtGui.QImage.Format.Format_RGBA8888).copy()
        pixels = pg.functions.ndarray_from_qimage(rendered)
        pixels[..., :3] = self._gamma_lut[pixels[..., :3]]
        self.qimage = rendered


class FlimHistogramLUTWidget(pg.GraphicsView):
    sigFlimRangesChanged = QtCore.Signal(object)

    def __init__(self, parent=None, *args, **kwargs):
        background = kwargs.pop("background", "default")
        super().__init__(parent, useOpenGL=False, background=background)
        self.item = FlimHistogramLUTItem(*args, **kwargs)
        self.setCentralItem(self.item)
        self.item.sigFlimRangesChanged.connect(self.sigFlimRangesChanged.emit)

        self.orientation = kwargs.get("orientation", "vertical")
        if self.orientation == "vertical":
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Expanding)
            self.setMinimumWidth(120)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
            self.setMinimumHeight(120)

    def __getattr__(self, attr):
        return getattr(self.item, attr)


class FlimImageView(pg.ImageView):
    def __init__(self, *args, **kwargs):
        if "imageItem" not in kwargs:
            kwargs["imageItem"] = GammaImageItem()
        super().__init__(*args, **kwargs)
        old_hist = self.ui.histogram
        self.imageItem.sigImageChanged.disconnect(old_hist.item.imageChanged)
        self.ui.gridLayout.removeWidget(old_hist)
        old_hist.setParent(None)
        old_hist.deleteLater()

        self.ui.histogram = FlimHistogramLUTWidget(self.ui.layoutWidget, levelMode="rgba")
        self.ui.gridLayout.addWidget(self.ui.histogram, 0, 1, 1, 2)
        self.ui.histogram.setImageItem(self.imageItem)
        self.ui.histogram.sigFlimRangesChanged.connect(self._on_flim_ranges_changed)
        for name in ("setHistogramRange", "autoHistogramRange", "getLookupTable", "getLevels"):
            setattr(self, name, getattr(self.ui.histogram, name))

        self._hcl_source = None
        self._image_gamma = 1.0
        self._hcl_valid = None
        self._hcl_image_kwargs = {}
        self._hcl_h_shift = 0.0
        self._hcl_render_mode = "hcl"
        self._hcl_hue_display_range = (0.0, 1.0)
        self._force_quality_full = False
        self._analysis_interval = 0.0
        self._analysis_key = None
        self._analysis_future = None
        self._analysis_job_key = None
        self._last_analysis_request = float("-inf")
        self._hcl_display_max = None
        self._analysis_timer = QtCore.QTimer(self)
        self._analysis_timer.setInterval(50)
        self._analysis_timer.timeout.connect(self._poll_histograms)
        self._hover_scene_position = None
        self.scene.sigMouseMoved.connect(self._update_colorbar_hover)
        self._hover_viewport = self.ui.graphicsView.viewport()
        self._hover_viewport.installEventFilter(self)

    def _apply_fixed_rgb_levels(self):
        self.ui.histogram.item.setLevels(rgba=_FIXED_RGB_LEVELS)
        self.imageItem.setLevels(_FIXED_RGB_LEVELS)

    def eventFilter(self, watched, event):
        if (event.type() == QtCore.QEvent.Type.Leave
                and watched is self._hover_viewport):
            self._hover_scene_position = None
            self.ui.histogram.item.set_hover_lifetime(None)
        return super().eventFilter(watched, event)

    def _update_colorbar_hover(self, scene_position):
        self._hover_scene_position = QtCore.QPointF(scene_position)
        item = self.ui.histogram.item
        if self._hcl_source is None:
            item.set_hover_lifetime(None)
            return
        point = self.imageItem.mapFromScene(scene_position)
        if not self.imageItem.boundingRect().contains(point):
            item.set_hover_lifetime(None)
            return
        x, y = int(np.floor(point.x())), int(np.floor(point.y()))
        index = (y, x) if self.imageItem.axisOrder == "row-major" else (x, y)
        if (any(i < 0 or i >= n for i, n in zip(index, self._hcl_valid.shape, strict=True))
                or not self._hcl_valid[index]):
            item.set_hover_lifetime(None)
            return
        phase = float((self._hcl_source[index][0] - self._hcl_h_shift) % 1.0)
        item.set_hover_lifetime(phase)

    def setFlimImage(
        self,
        hcl,
        valid=None,
        h_display_max=None,
        h_shift=0.0,
        render_mode="hcl",
        hue_display_range=None,
        force_quality_full=False,
        auto_quality=False,
        auto_counts=False,
        percentiles=(1.0, 99.0),
        hue_wrap=False,
        hue_wrap_mode="repeat",
        equalize_hue=False,
        equalize_counts=False,
        analysis_interval=0.0,
        hue_offset=0.0,
        value_gamma=1.0,
        auto_counts_zero=False,
        **kwargs,
    ):
        self._set_regular_gamma(1.0)
        if hasattr(self.ui.histogram.item, "activate_color_lifetime_mode"):
            self.ui.histogram.item.activate_color_lifetime_mode()
        self._hcl_source = np.asarray(hcl, dtype=float)
        self._hcl_valid = (
            np.asarray(valid, dtype=bool)
            if valid is not None
            else np.ones(self._hcl_source.shape[:2], dtype=bool)
        )
        self._hcl_valid = self._hcl_valid & np.all(np.isfinite(self._hcl_source), axis=-1)
        self._hcl_h_shift = float(h_shift) % 1.0
        self._hcl_render_mode = str(render_mode).lower()
        if hue_display_range is None or len(hue_display_range) != 2:
            hue_display_range = (0.0, 1.0)
        self._hcl_hue_display_range = tuple(map(float, hue_display_range))
        self._force_quality_full = bool(force_quality_full)
        self._hcl_image_kwargs = dict(kwargs)
        self._hcl_display_max = h_display_max
        if h_display_max is not None and self.ui.histogram.item._hcl_display_max["H"] != float(h_display_max):
            self.ui.histogram.item._hcl_display_max["H"] = max(float(h_display_max), 1e-12)
            self.ui.histogram.item._update_hl_colorbar()
        self._analysis_interval = max(0.0, float(analysis_interval))
        self.ui.histogram.item.set_scaling(
            auto_quality, auto_counts, percentiles, hue_wrap, hue_wrap_mode,
            equalize_hue, equalize_counts,
            hue_offset, value_gamma,
            auto_counts_zero,
        )
        if hasattr(self.ui.histogram.item, "set_render_mode"):
            self.ui.histogram.item.set_render_mode(self._hcl_render_mode)
        if hasattr(self.ui.histogram.item, "set_hue_display_range"):
            self.ui.histogram.item.set_hue_display_range(self._hcl_hue_display_range)
        self._update_histograms()
        self._apply_hcl_render(initial=True)

    def _histogram_key(self):
        item = self.ui.histogram.item
        ranges = item.get_flim_ranges()
        return (self._hcl_source.shape, self._hcl_h_shift, item._percentiles,
                item._auto_counts_zero,
                tuple(item._auto_ranges.items()), tuple(item._equalize.items()),
                tuple(item._equalization_requests.items()),
                item._hue_wrap, item._hue_wrap_mode,
                tuple((key, ranges[key]) for key in ("H", "C", "L") if not item._auto_ranges.get(key)))

    def _update_histograms(self):
        item = self.ui.histogram.item
        key = self._histogram_key()
        if key != self._analysis_key:
            self._analysis_key = key
            self._last_analysis_request = float("-inf")
        if self._analysis_interval > 0:
            self._poll_histograms(render=False)
            if self._analysis_future is not None or time.monotonic() - self._last_analysis_request < self._analysis_interval:
                return
        h = np.mod(self._hcl_source[:, :, 0] - self._hcl_h_shift, 1.0)
        samples = sample_lifetime_data(h, self._hcl_source[:, :, 1],
                                       self._hcl_source[:, :, 2], self._hcl_valid)
        args = (samples, item.get_flim_ranges(), dict(item._auto_ranges), item._percentiles,
                item.pending_equalization(), item._hue_wrap and item._hue_wrap_mode == "repeat",
                dict(item._equalization_requests), item._auto_counts_zero)
        if self._analysis_interval <= 0:
            self._analysis_timer.stop()
            if self._analysis_future is not None:
                self._analysis_future.cancel()
                self._analysis_future = None
            with QtCore.QSignalBlocker(self.ui.histogram):
                item.apply_analysis(analyze_lifetime_histograms(*args), self._hcl_display_max)
        else:
            self._analysis_job_key = key
            self._last_analysis_request = time.monotonic()
            self._analysis_future = _HISTOGRAM_EXECUTOR.submit(analyze_lifetime_histograms, *args)
            self._analysis_timer.start()

    def _poll_histograms(self, render=True):
        future = self._analysis_future
        if future is None or not future.done():
            return
        self._analysis_future = None
        self._analysis_timer.stop()
        try:
            analysis = future.result()
        except Exception:
            logging.getLogger(__name__).exception("Lifetime histogram analysis failed")
            return
        if self._hcl_source is None:
            return
        if self._analysis_job_key != self._histogram_key():
            self._last_analysis_request = float("-inf")
            if render:
                self._update_histograms()
            return
        with QtCore.QSignalBlocker(self.ui.histogram):
            self.ui.histogram.item.apply_analysis(analysis, self._hcl_display_max)
        # Applying automatic ranges must not invalidate the next cache key.
        self._analysis_key = self._histogram_key()
        if render:
            self._apply_hcl_render(initial=False)

    def clearFlimImage(self):
        self._hcl_source = None
        self._hcl_valid = None
        self._hover_scene_position = None
        self.ui.histogram.item.set_hover_lifetime(None)
        self._analysis_timer.stop()
        if self._analysis_future is not None:
            self._analysis_future.cancel()
        self._analysis_future = None
        self._analysis_key = None
        self._last_analysis_request = float("-inf")
        if hasattr(self.ui.histogram, "clear_flim_data"):
            self.ui.histogram.clear_flim_data()
        if hasattr(self.ui.histogram.item, "deactivate_color_lifetime_mode"):
            self.ui.histogram.item.deactivate_color_lifetime_mode()

    def refreshEqualization(self, channel=None):
        """Explicitly refit enabled equalization from the current image only."""
        self.ui.histogram.item.request_equalization(channel)
        if self._hcl_source is not None:
            self._update_histograms()
            self._apply_hcl_render(initial=False)

    def setImageGamma(self, gamma):
        """Set regular image gamma without altering values, levels or histograms."""
        if not np.isfinite(gamma) or gamma <= 0:
            raise ValueError("Image gamma must be finite and positive")
        self._image_gamma = float(gamma)
        if self._hcl_source is None:
            self._set_regular_gamma(self._image_gamma)

    def _set_regular_gamma(self, gamma):
        self.ui.histogram.item.set_image_gamma(gamma)
        if isinstance(self.imageItem, GammaImageItem):
            self.imageItem.setGamma(gamma)

    def setImage(self, *args, **kwargs):
        if not hasattr(self, "_image_gamma"):
            if args and args[0] is None:
                return
            return super().setImage(*args, **kwargs)
        self.clearFlimImage()
        self._set_regular_gamma(self._image_gamma)
        return super().setImage(*args, **kwargs)

    def _on_flim_ranges_changed(self, _ranges):
        if self._hcl_source is not None:
            if any(self.ui.histogram.item._equalize.values()):
                self._update_histograms()
            self._apply_hcl_render(initial=False)

    def getDisplayedHMean(self):
        if self._hcl_source is None:
            return None

        h_raw = np.mod(self._hcl_source[:, :, 0] - self._hcl_h_shift, 1.0)
        mask = np.array(self._hcl_valid, copy=True)
        mask &= np.isfinite(h_raw)
        values = h_raw[mask]
        if values.size == 0:
            return None

        theta = 2.0 * np.pi * values
        c_sum = np.sum(np.cos(theta))
        s_sum = np.sum(np.sin(theta))
        mean_theta = np.arctan2(s_sum, c_sum)
        if mean_theta < 0.0:
            mean_theta += 2.0 * np.pi
        return mean_theta / (2.0 * np.pi)

    def _apply_hcl_render(self, initial):
        if self._hcl_source is None:
            return

        ranges = self.ui.histogram.get_flim_ranges()
        h_raw = np.mod(self._hcl_source[:, :, 0] - self._hcl_h_shift, 1.0)
        h_wrapped = wrap_phase_values(h_raw, ranges["H"])
        c_raw = self._hcl_source[:, :, 1]
        l_raw = self._hcl_source[:, :, 2]

        mask = np.array(self._hcl_valid, copy=True)
        mask &= np.isfinite(h_raw)
        mask &= np.isfinite(c_raw)
        mask &= np.isfinite(l_raw)

        h_span = max(ranges["H"][1] - ranges["H"][0], 1e-12)
        c_span = max(ranges["C"][1] - ranges["C"][0], 1e-12)
        l_span = max(ranges["L"][1] - ranges["L"][0], 1e-12)

        h = np.zeros_like(h_raw, dtype=float)
        c = np.zeros_like(c_raw, dtype=float)
        l = np.zeros_like(l_raw, dtype=float)

        h[mask] = (h_wrapped[mask] - ranges["H"][0]) / h_span
        c[mask] = np.clip((c_raw[mask] - ranges["C"][0]) / c_span, 0.0, 1.0)
        l[mask] = np.clip((l_raw[mask] - ranges["L"][0]) / l_span, 0.0, 1.0) * 100.0

        h_display = self.ui.histogram.item._map_hue_for_display(h)
        quality_render = np.ones_like(c) if self._force_quality_full else c
        rgb = render_lifetime_rgb(h_display, quality_render,
                                  self.ui.histogram.item._map_counts_for_display(l / 100.0),
                                  self._hcl_render_mode)
        rgb[~mask] = 0

        if initial:
            kwargs = dict(self._hcl_image_kwargs)
            kwargs.setdefault("levelMode", "rgba")
            kwargs["autoLevels"] = False
            super().setImage(rgb, **kwargs)
            self._apply_fixed_rgb_levels()
        else:
            self.image = rgb
            self.imageDisp = None
            self.imageItem.setImage(rgb, autoLevels=False)
            self._apply_fixed_rgb_levels()
        if self._hover_scene_position is not None:
            self._update_colorbar_hover(self._hover_scene_position)


HclHistogramLUTItem = FlimHistogramLUTItem
HclHistogramLUTWidget = FlimHistogramLUTWidget
HclImageView = FlimImageView
FlimHistogramLUTItem.set_hcl_visible = FlimHistogramLUTItem.set_flim_visible
FlimHistogramLUTItem.set_hcl_data = FlimHistogramLUTItem.set_flim_data
FlimHistogramLUTItem.clear_hcl_data = FlimHistogramLUTItem.clear_flim_data
FlimHistogramLUTItem.get_hcl_ranges = FlimHistogramLUTItem.get_flim_ranges
FlimImageView.setHclImage = FlimImageView.setFlimImage
FlimImageView.clearHclImage = FlimImageView.clearFlimImage
FlimImageView._on_hcl_ranges_changed = FlimImageView._on_flim_ranges_changed
