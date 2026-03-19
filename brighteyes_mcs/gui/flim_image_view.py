"""Custom ImageView with FLIM-aware histogram controls."""

from PySide6 import QtCore, QtWidgets
import numpy as np
import pyqtgraph as pg


_FIXED_RGB_LEVELS = [[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]


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
        self._hcl_display_max = {"H": 1.0, "C": 1.0, "L": 1.0}
        self._suspend_hcl_range_signal = False
        self._color_lifetime_widgets_attached = False
        self._native_histogram_widgets_attached = True
        self._render_mode = "hcl"
        self._hue_display_range = (0.0, 1.0)
        self._hl_colorbar_plot = None
        self._hl_colorbar_image = None
        self._hl_hist_curve = None
        self._hl_hist_values = np.asarray([], dtype=float)
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
        self._hl_colorbar_plot.getAxis("right").setWidth(56)
        self._hl_colorbar_image = pg.ImageItem(axisOrder="row-major")
        self._hl_colorbar_plot.addItem(self._hl_colorbar_image)
        self._hl_hist_curve = pg.PlotCurveItem(
            pen=pg.mkPen(color=(255, 255, 255, 220), width=2)
        )
        self._hl_colorbar_plot.addItem(self._hl_hist_curve)
        self._hl_colorbar_plot.setVisible(False)
        self._update_hl_colorbar()

    def _build_hcl_controls(self):
        base_row = 4
        for idx, key in enumerate(("H", "C", "L")):
            label = pg.LabelItem(justify="left")
            label.setText(f"{key} range")
            plot = pg.PlotItem()
            plot.hideAxis("left")
            plot.setMouseEnabled(x=False, y=False)
            plot.setMaximumHeight(55)
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
        self._hue_display_range = (start, stop)
        self._update_hl_colorbar()

    def _map_hue_for_display(self, h):
        start, stop = self._hue_display_range
        h = np.asarray(h, dtype=float)
        if stop >= start:
            return np.mod(start + h * (stop - start), 1.0)
        # Reverse the displayed colorscale when the GUI hue range is reversed.
        return np.mod(stop + (1.0 - h) * (start - stop), 1.0)

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
        self._attach_native_histogram_widgets()
        self._set_native_histogram_visible(True)
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

    def _update_hl_colorbar(self, width=192, height=192):
        if self._hl_colorbar_image is None:
            return

        h = np.tile(np.linspace(0.0, 1.0, height, dtype=float)[:, None], (1, width))
        h_display = self._map_hue_for_display(h)
        counts_norm = np.tile(np.linspace(0.0, 1.0, width, dtype=float), (height, 1))
        quality = np.ones((height, width), dtype=float)
        rgb = render_lifetime_rgb(h_display, quality, counts_norm, self._render_mode)
        self._hl_colorbar_image.setImage(rgb, autoLevels=False)
        self._hl_colorbar_image.setLevels(_FIXED_RGB_LEVELS)

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

        self._hl_colorbar_image.setRect(QtCore.QRectF(l_low, h_low, l_high - l_low, h_high - h_low))
        top_axis = self._hl_colorbar_plot.getAxis("top")
        right_axis = self._hl_colorbar_plot.getAxis("right")
        top_axis.setLabel("counts")
        right_axis.setLabel("lifetime [ns]")
        top_axis.setTicks([[
            (l_low, f"{l_low:.3g}"),
            (0.5 * (l_low + l_high), f"{0.5 * (l_low + l_high):.3g}"),
            (l_high, f"{l_high:.3g}"),
        ]])
        right_axis.setTicks([[
            (h_low, f"{h_low:.3f}"),
            (0.5 * (h_low + h_high), f"{0.5 * (h_low + h_high):.3f}"),
            (h_high, f"{h_high:.3f}"),
        ]])

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
                if np.max(hist) > 0:
                    hist_norm = hist / np.max(hist)
                    x_hist = l_low + hist_norm * (l_high - l_low)
                    self._hl_hist_curve.setData(x_hist, centers_ns)
                else:
                    self._hl_hist_curve.setData([], [])

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

    def set_flim_data(self, h, c, l, valid=None, h_display_max=None):
        if valid is None:
            valid = np.ones_like(h, dtype=bool)
        datasets = {"H": h, "C": c, "L": l}
        self._hl_hist_values = np.asarray(h, dtype=float)[np.asarray(valid, dtype=bool)]
        if h_display_max is not None:
            self._hcl_display_max["H"] = max(float(h_display_max), 1e-12)
        self.set_flim_visible(True)

        self._suspend_hcl_range_signal = True
        try:
            for key, values in datasets.items():
                arr = np.asarray(values, dtype=float)
                mask = np.asarray(valid, dtype=bool) & np.isfinite(arr)
                arr = arr[mask]
                if key == "H":
                    low, high = 0.0, 1.0
                elif key == "C":
                    low, high = 0.0, 1.0
                elif arr.size == 0:
                    low, high = self._hcl_ranges[key]
                    xs = np.array([low, high], dtype=float)
                    ys = np.zeros(2, dtype=float)
                else:
                    low = float(np.nanmin(arr))
                    high = float(np.nanmax(arr))
                    if low == high:
                        high = low + 1e-9
                    ys, edges = np.histogram(arr, bins=100, range=(low, high))
                    xs = 0.5 * (edges[:-1] + edges[1:])
                if key == "H":
                    if arr.size == 0:
                        xs = np.array([low, high], dtype=float)
                        ys = np.zeros(2, dtype=float)
                    else:
                        arr_wrapped = wrap_phase_values(arr, self._hcl_ranges.get("H", (0.0, 1.0)))
                        ys, edges = np.histogram(arr_wrapped, bins=100, range=(low, high))
                        xs = 0.5 * (edges[:-1] + edges[1:])
                elif key == "C":
                    if arr.size == 0:
                        xs = np.array([low, high], dtype=float)
                        ys = np.zeros(2, dtype=float)
                    else:
                        ys, edges = np.histogram(arr, bins=100, range=(low, high))
                        xs = 0.5 * (edges[:-1] + edges[1:])

                self._hcl_bounds[key] = (low, high)
                self._hcl_curves[key].setData(xs, ys)
                current = self._hcl_ranges.get(key, (low, high))
                current = (max(low, current[0]), min(high, current[1]))
                if current[0] >= current[1]:
                    current = (0.0, 1.0) if key == "H" else (low, high)
                self._hcl_ranges[key] = current
                self._hcl_regions[key].setBounds((low, high))
                reset_region = (0.0, 1.0) if key == "H" else (low, high)
                self._hcl_regions[key].set_reset_region(reset_region)
                if tuple(self._hcl_regions[key].getRegion()) != tuple(current):
                    self._hcl_regions[key].setRegion(current)
                self._update_axis_representation(key)
            self._update_hl_colorbar()
        finally:
            self._suspend_hcl_range_signal = False

        self._emit_hcl_ranges_changed()

    def clear_flim_data(self):
        self.deactivate_color_lifetime_mode()

    def get_flim_ranges(self):
        return dict(self._hcl_ranges)

    def _emit_hcl_ranges_changed(self):
        if self._suspend_hcl_range_signal:
            return
        for key, region in self._hcl_regions.items():
            self._hcl_ranges[key] = tuple(region.getRegion())
        self.sigFlimRangesChanged.emit(self.get_flim_ranges())


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
        super().__init__(*args, **kwargs)
        old_hist = self.ui.histogram
        self.ui.gridLayout.removeWidget(old_hist)
        old_hist.setParent(None)
        old_hist.deleteLater()

        self.ui.histogram = FlimHistogramLUTWidget(self.ui.layoutWidget, levelMode="rgba")
        self.ui.gridLayout.addWidget(self.ui.histogram, 0, 1, 1, 2)
        self.ui.histogram.setImageItem(self.imageItem)
        self.ui.histogram.sigFlimRangesChanged.connect(self._on_flim_ranges_changed)

        self._hcl_source = None
        self._hcl_valid = None
        self._hcl_image_kwargs = {}
        self._hcl_h_shift = 0.0
        self._hcl_render_mode = "hcl"
        self._hcl_hue_display_range = (0.0, 1.0)
        self._force_quality_full = False

    def _apply_fixed_rgb_levels(self):
        self.ui.histogram.item.setLevels(rgba=_FIXED_RGB_LEVELS)
        self.imageItem.setLevels(_FIXED_RGB_LEVELS)

    def setFlimImage(
        self,
        hcl,
        valid=None,
        h_display_max=None,
        h_shift=0.0,
        render_mode="hcl",
        hue_display_range=None,
        force_quality_full=False,
        **kwargs,
    ):
        if hasattr(self.ui.histogram.item, "activate_color_lifetime_mode"):
            self.ui.histogram.item.activate_color_lifetime_mode()
        self._hcl_source = np.asarray(hcl, dtype=float)
        self._hcl_valid = (
            np.asarray(valid, dtype=bool)
            if valid is not None
            else np.ones(self._hcl_source.shape[:2], dtype=bool)
        )
        self._hcl_h_shift = float(h_shift) % 1.0
        self._hcl_render_mode = str(render_mode).lower()
        if hue_display_range is None or len(hue_display_range) != 2:
            hue_display_range = (0.0, 1.0)
        self._hcl_hue_display_range = tuple(map(float, hue_display_range))
        self._force_quality_full = bool(force_quality_full)
        self._hcl_image_kwargs = dict(kwargs)
        if hasattr(self.ui.histogram.item, "set_render_mode"):
            self.ui.histogram.item.set_render_mode(self._hcl_render_mode)
        if hasattr(self.ui.histogram.item, "set_hue_display_range"):
            self.ui.histogram.item.set_hue_display_range(self._hcl_hue_display_range)
        h_for_display = np.mod(self._hcl_source[:, :, 0] - self._hcl_h_shift, 1.0)
        self.ui.histogram.set_flim_data(
            h_for_display,
            self._hcl_source[:, :, 1],
            self._hcl_source[:, :, 2],
            self._hcl_valid,
            h_display_max=h_display_max,
        )
        self._apply_hcl_render(initial=True)

    def clearFlimImage(self):
        self._hcl_source = None
        self._hcl_valid = None
        if hasattr(self.ui.histogram, "clear_flim_data"):
            self.ui.histogram.clear_flim_data()
        if hasattr(self.ui.histogram.item, "deactivate_color_lifetime_mode"):
            self.ui.histogram.item.deactivate_color_lifetime_mode()

    def setImage(self, *args, **kwargs):
        self.clearFlimImage()
        return super().setImage(*args, **kwargs)

    def _on_flim_ranges_changed(self, _ranges):
        if self._hcl_source is not None:
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

        h[mask] = np.clip((h_wrapped[mask] - ranges["H"][0]) / h_span, 0.0, 1.0)
        c[mask] = np.clip((c_raw[mask] - ranges["C"][0]) / c_span, 0.0, 1.0)
        l[mask] = np.clip((l_raw[mask] - ranges["L"][0]) / l_span, 0.0, 1.0) * 100.0

        h_display = self.ui.histogram.item._map_hue_for_display(h)
        quality_render = np.ones_like(c) if self._force_quality_full else c
        rgb = render_lifetime_rgb(h_display, quality_render, l / 100.0, self._hcl_render_mode)
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
