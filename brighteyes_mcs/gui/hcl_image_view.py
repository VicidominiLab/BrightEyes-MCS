"""Custom ImageView with HCL-aware histogram controls."""

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


class ResettableLinearRegionItem(pg.LinearRegionItem):
    def __init__(self, values, *args, **kwargs):
        super().__init__(values, *args, **kwargs)
        self._reset_region = tuple(values)

    def set_reset_region(self, values):
        self._reset_region = tuple(values)

    def mouseDoubleClickEvent(self, ev):
        self.setRegion(self._reset_region)
        ev.accept()


class HclHistogramLUTItem(pg.HistogramLUTItem):
    sigHclRangesChanged = QtCore.Signal(object)

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
        self._build_hcl_controls()
        self.set_hcl_visible(False)

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

            self.layout.addItem(label, base_row + idx * 2, 0, 1, 3)
            self.layout.addItem(plot, base_row + idx * 2 + 1, 0, 1, 3)
            self._hcl_labels[key] = label
            self._hcl_plots[key] = plot
            self._hcl_curves[key] = curve
            self._hcl_regions[key] = region
            self._update_axis_representation(key)

    def _update_axis_representation(self, key):
        plot = self._hcl_plots[key]
        axis = plot.getAxis("bottom")
        display_max = float(self._hcl_display_max.get(key, 1.0))
        tick_values = [0.0, 0.5, 1.0]

        if key == "H":
            tick_labels = [
                f"{0.0:.3f}",
                f"{0.5 * display_max:.3f}",
                f"{display_max:.3f}",
            ]
            axis.setLabel("lifetime [ns]")
            self._hcl_labels[key].setText(f"{key} range (0..{display_max:.3f} ns)")
        elif key == "C":
            tick_labels = ["0.0", "0.5", "1.0"]
            axis.setLabel("quality")
            self._hcl_labels[key].setText(f"{key} range")
        else:
            low, high = self._hcl_bounds.get(key, (0.0, 1.0))
            mid = 0.5 * (low + high)
            tick_labels = [f"{low:.3g}", f"{mid:.3g}", f"{high:.3g}"]
            axis.setLabel("counts")
            self._hcl_labels[key].setText(f"{key} range")

        axis.setTicks([list(zip(tick_values, tick_labels))])

    def set_hcl_visible(self, visible):
        for key in ("H", "C", "L"):
            self._hcl_labels[key].setVisible(visible)
            self._hcl_plots[key].setVisible(visible)

    def set_hcl_data(self, h, c, l, valid=None, h_display_max=None):
        if valid is None:
            valid = np.ones_like(h, dtype=bool)
        datasets = {"H": h, "C": c, "L": l}
        if h_display_max is not None:
            self._hcl_display_max["H"] = max(float(h_display_max), 1e-12)
        self.set_hcl_visible(True)

        self._suspend_hcl_range_signal = True
        try:
            for key, values in datasets.items():
                arr = np.asarray(values, dtype=float)
                mask = np.asarray(valid, dtype=bool) & np.isfinite(arr)
                arr = arr[mask]
                if key in {"H", "C"}:
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
                if key in {"H", "C"}:
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
                    current = (low, high)
                self._hcl_ranges[key] = current
                self._hcl_regions[key].setBounds((low, high))
                self._hcl_regions[key].set_reset_region((low, high))
                if tuple(self._hcl_regions[key].getRegion()) != tuple(current):
                    self._hcl_regions[key].setRegion(current)
                self._update_axis_representation(key)
        finally:
            self._suspend_hcl_range_signal = False

        self._emit_hcl_ranges_changed()

    def clear_hcl_data(self):
        self.set_hcl_visible(False)

    def get_hcl_ranges(self):
        return dict(self._hcl_ranges)

    def _emit_hcl_ranges_changed(self):
        if self._suspend_hcl_range_signal:
            return
        for key, region in self._hcl_regions.items():
            self._hcl_ranges[key] = tuple(region.getRegion())
        self.sigHclRangesChanged.emit(self.get_hcl_ranges())


class HclHistogramLUTWidget(pg.GraphicsView):
    sigHclRangesChanged = QtCore.Signal(object)

    def __init__(self, parent=None, *args, **kwargs):
        background = kwargs.pop("background", "default")
        super().__init__(parent, useOpenGL=False, background=background)
        self.item = HclHistogramLUTItem(*args, **kwargs)
        self.setCentralItem(self.item)
        self.item.sigHclRangesChanged.connect(self.sigHclRangesChanged.emit)

        self.orientation = kwargs.get("orientation", "vertical")
        if self.orientation == "vertical":
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Expanding)
            self.setMinimumWidth(120)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
            self.setMinimumHeight(120)

    def __getattr__(self, attr):
        return getattr(self.item, attr)


class HclImageView(pg.ImageView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        old_hist = self.ui.histogram
        self.ui.gridLayout.removeWidget(old_hist)
        old_hist.setParent(None)
        old_hist.deleteLater()

        self.ui.histogram = HclHistogramLUTWidget(self.ui.layoutWidget, levelMode="rgba")
        self.ui.gridLayout.addWidget(self.ui.histogram, 0, 1, 1, 2)
        self.ui.histogram.setImageItem(self.imageItem)
        self.ui.histogram.sigHclRangesChanged.connect(self._on_hcl_ranges_changed)

        self._hcl_source = None
        self._hcl_valid = None
        self._hcl_image_kwargs = {}
        self._hcl_h_shift = 0.0

    def _apply_fixed_rgb_levels(self):
        self.ui.histogram.item.setLevels(rgba=_FIXED_RGB_LEVELS)
        self.imageItem.setLevels(_FIXED_RGB_LEVELS)

    def setHclImage(self, hcl, valid=None, h_display_max=None, h_shift=0.0, **kwargs):
        self._hcl_source = np.asarray(hcl, dtype=float)
        self._hcl_valid = (
            np.asarray(valid, dtype=bool)
            if valid is not None
            else np.ones(self._hcl_source.shape[:2], dtype=bool)
        )
        self._hcl_h_shift = float(h_shift) % 1.0
        self._hcl_image_kwargs = dict(kwargs)
        h_for_display = np.mod(self._hcl_source[:, :, 0] - self._hcl_h_shift, 1.0)
        self.ui.histogram.set_hcl_data(
            h_for_display,
            self._hcl_source[:, :, 1],
            self._hcl_source[:, :, 2],
            self._hcl_valid,
            h_display_max=h_display_max,
        )
        self._apply_hcl_render(initial=True)

    def clearHclImage(self):
        self._hcl_source = None
        self._hcl_valid = None
        if hasattr(self.ui.histogram, "clear_hcl_data"):
            self.ui.histogram.clear_hcl_data()

    def setImage(self, *args, **kwargs):
        self.clearHclImage()
        return super().setImage(*args, **kwargs)

    def _on_hcl_ranges_changed(self, _ranges):
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

        ranges = self.ui.histogram.get_hcl_ranges()
        h_raw = np.mod(self._hcl_source[:, :, 0] - self._hcl_h_shift, 1.0)
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

        h[mask] = np.clip((h_raw[mask] - ranges["H"][0]) / h_span, 0.0, 1.0)
        c[mask] = np.clip((c_raw[mask] - ranges["C"][0]) / c_span, 0.0, 1.0)
        l[mask] = np.clip((l_raw[mask] - ranges["L"][0]) / l_span, 0.0, 1.0) * 100.0

        rgb = lch_to_srgb(l, c * 100.0, h)
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
