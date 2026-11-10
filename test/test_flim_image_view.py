import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent, QPointF
import pyqtgraph as pg

from brighteyes_mcs.ui.qt.flim_image_view import FlimImageView


@pytest.fixture
def view():
    app = QApplication.instance() or QApplication([])
    widget = FlimImageView()
    yield widget
    widget.clearFlimImage()
    scenes = (widget.scene, widget.ui.histogram.scene())
    for view_box in list(pg.ViewBox.AllViews):
        if view_box.scene() in scenes:
            view_box.childGroup.itemsChangedListeners = ()
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def sample_image():
    image = np.ones((10, 10, 3), dtype=float)
    image[:, :, 0] = 0.5
    image[:, :, 1] = np.linspace(0.2, 0.8, 100).reshape(10, 10)
    image[:, :, 2] = np.arange(1, 101).reshape(10, 10)
    return image


def test_repeated_lifetime_to_native_histogram_switches_do_not_overlap_grid_cells(view):
    from PySide6.QtCore import qInstallMessageHandler

    messages = []
    previous = qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    try:
        for _ in range(6):
            view.setFlimImage(sample_image(), render_mode="hsv", auto_counts=True)
            assert view.ui.histogram.item.layout.itemAt(0, 0) is view.ui.histogram.item._hl_colorbar_plot
            view.clearFlimImage()
            view.clear()
            view.setImage(np.arange(100).reshape(10, 10), levelMode="mono")
            assert view.ui.histogram.item.layout.itemAt(0, 0) is view.ui.histogram.item.axis
    finally:
        qInstallMessageHandler(previous)
    assert not any("already taken" in message for message in messages), messages


@pytest.mark.parametrize("offset", [0.25, 1.25, -0.75])
def test_hue_rotation_is_wrapped_and_preserves_lifetime_values(view, offset):
    image = np.ones((2, 2, 3))
    image[:, :, 0] = 0.5
    image[:, :, 2] = 100
    source = image.copy()
    view.setFlimImage(image, render_mode="hsv", auto_counts=True,
                      force_quality_full=True, hue_offset=offset)
    np.testing.assert_allclose(view.image[0, 0], [0.5, 0, 1])
    np.testing.assert_array_equal(image, source)
    assert view.getDisplayedHMean() == pytest.approx(0.5)
    colorbar = view.ui.histogram.item._hl_colorbar_image.image
    np.testing.assert_allclose(colorbar[0, -1], [0.5, 1, 0])


@pytest.mark.parametrize("gamma,expected", [(1, 0.25), (2, 0.5), (0.5, 0.0625)])
def test_value_gamma_preserves_black_and_white_and_maps_midtones(view, gamma, expected):
    image = np.ones((1, 3, 3))
    image[:, :, 0] = 0.25
    image[0, :, 2] = [0, 25, 100]
    view.setFlimImage(image, render_mode="hsv", auto_counts=True, percentiles=(0, 100),
                      force_quality_full=True, value_gamma=gamma)
    np.testing.assert_allclose(view.image.max(axis=-1), [[0, expected, 1]])
    colorbar = view.ui.histogram.item._hl_colorbar_image.image
    np.testing.assert_allclose(colorbar[:, 64].max(axis=-1), (64 / 191) ** (1 / gamma))


@pytest.mark.parametrize("mode", ["hsl", "hcl"])
def test_v_gamma_does_not_change_other_color_modes(view, mode):
    view.setFlimImage(sample_image(), render_mode=mode, auto_counts=True)
    before = view.image.copy()
    view.setFlimImage(sample_image(), render_mode=mode, auto_counts=True, value_gamma=2)
    np.testing.assert_array_equal(view.image, before)


@pytest.mark.parametrize("gamma", [0, -1, float("nan"), float("inf")])
def test_invalid_gamma_is_rejected(view, gamma):
    with pytest.raises(ValueError, match="gamma"):
        view.setFlimImage(sample_image(), value_gamma=gamma)


@pytest.mark.parametrize("gamma,expected", [(1, 64), (2, 128), (0.5, 16)])
def test_regular_image_gamma_uses_display_levels_and_preserves_raw_values(view, gamma, expected):
    source = np.array([[10, 35, 110]], dtype=float)
    view.setImage(source, levelMode="mono", autoLevels=False, levels=(10, 110))
    histogram = view.ui.histogram.item.plot.getData()
    view.setImageGamma(gamma)
    item = view.imageItem
    item.render()
    assert item.qimage.pixelColor(0, 0).red() == 0
    assert abs(item.qimage.pixelColor(0, 1).red() - expected) <= 1
    assert abs(item.qimage.pixelColor(0, 2).red() - 255) <= 1
    np.testing.assert_array_equal(view.image, source)
    np.testing.assert_array_equal(item.image, source)
    np.testing.assert_array_equal(item.levels, [10, 110])
    for before, after in zip(histogram, view.ui.histogram.item.plot.getData(), strict=True):
        np.testing.assert_array_equal(before, after)


def test_regular_gamma_maps_selected_color_gradient_and_tracks_manual_levels(view):
    source = np.array([[0, 25, 100]], dtype=float)
    view.setImage(source, levelMode="mono", autoLevels=False, levels=(0, 100))
    histogram = view.ui.histogram.item
    histogram.gradient.loadPreset("thermal")
    linear = histogram.getLookupTable(source, 256).copy()
    view.setImageGamma(2)
    gamma = histogram.getLookupTable(source, 256)
    np.testing.assert_allclose(gamma[64], linear[128], atol=2)
    view.ui.histogram.setLevels(0, 400)
    view.imageItem.render()
    # At the new upper limit, 100 maps to sqrt(100/400)=0.5.
    color = view.imageItem.qimage.pixelColor(0, 2)
    np.testing.assert_allclose([color.red(), color.green(), color.blue()], linear[128, :3], atol=2)
    view.setImageGamma(1)
    np.testing.assert_array_equal(histogram.getLookupTable(source, 256), linear)


@pytest.mark.parametrize("channels", [3, 4])
def test_regular_rgb_gamma_preserves_alpha_and_original_data(view, channels):
    source = np.array([[[0, 64, 255, 128]]], dtype=np.uint8)[..., :channels]
    view.setImageGamma(2)
    view.setImage(source, levelMode="rgba", autoLevels=False, levels=(0, 255))
    view.imageItem.render()
    color = view.imageItem.qimage.pixelColor(0, 0)
    np.testing.assert_allclose([color.red(), color.green(), color.blue()], [0, 128, 255], atol=1)
    assert color.alpha() == (128 if channels == 4 else 255)
    np.testing.assert_array_equal(view.imageItem.image, source)
    view.imageItem.render()
    assert view.imageItem.qimage.pixelColor(0, 0) == color


def test_switching_to_lifetime_does_not_apply_regular_gamma_twice(view):
    view.setImageGamma(2)
    image = np.ones((1, 3, 3))
    image[..., 0] = 0.25
    image[0, :, 2] = [0, 25, 100]
    view.setFlimImage(image, render_mode="hsv", auto_counts=True, percentiles=(0, 100),
                      force_quality_full=True, value_gamma=2)
    assert view.imageItem._display_gamma == 1
    np.testing.assert_allclose(view.image.max(axis=-1), [[0, 0.5, 1]])
    view.setImage(image[..., 2], levelMode="mono", autoLevels=False, levels=(0, 100))
    assert view.imageItem._display_gamma == 2
    view.imageItem.render()
    assert abs(view.imageItem.qimage.pixelColor(0, 1).red() - 128) <= 1


@pytest.mark.parametrize("gamma", [0, -1, float("nan"), float("inf")])
def test_regular_gamma_rejects_invalid_values(view, gamma):
    with pytest.raises(ValueError, match="gamma"):
        view.setImageGamma(gamma)


def test_percentile_scaling_tracks_new_frames_and_ignores_invalid_pixels(view):
    image = sample_image()
    image[-1, -1, 2] = 1e9
    valid = np.ones((10, 10), dtype=bool)
    valid[-1, -1] = False
    options = dict(valid=valid, render_mode="hsv", auto_counts=True,
                   auto_quality=True, percentiles=(5, 95))
    view.setFlimImage(image, **options)
    ranges = view.ui.histogram.get_flim_ranges()
    np.testing.assert_allclose(ranges["L"], np.percentile(image[:, :, 2][valid], (5, 95)))
    np.testing.assert_allclose(ranges["C"], np.percentile(image[:, :, 1][valid], (5, 95)))
    image[:, :, 2] *= 10
    view.setFlimImage(image, **options)
    np.testing.assert_allclose(view.ui.histogram.get_flim_ranges()["L"],
                               np.asarray(ranges["L"]) * 10)
    assert np.isfinite(view.image).all()
    np.testing.assert_array_equal(view.image[-1, -1], 0)


def test_manual_scaling_stays_fixed_between_frames(view):
    image = sample_image()
    view.setFlimImage(image, auto_counts=True)
    histogram = view.ui.histogram.item
    histogram._hcl_regions["L"].setRegion((20, 80))
    image[:, :, 2] *= 2
    view.setFlimImage(image, auto_counts=False)
    np.testing.assert_allclose(histogram.get_flim_ranges()["L"], (20, 80))


@pytest.mark.parametrize("mode", ["hsv", "hsl", "hcl"])
def test_auto_brightness_can_hold_zero_and_return_to_percentile_minimum(view, mode):
    image = sample_image()
    options = dict(render_mode=mode, auto_counts=True, percentiles=(5, 95))
    view.setFlimImage(image, auto_counts_zero=True, **options)
    np.testing.assert_allclose(view.ui.histogram.get_flim_ranges()["L"], (0, 95.05))
    assert np.isfinite(view.image).all()
    image[:, :, 2] *= 2
    view.setFlimImage(image, auto_counts_zero=True, **options)
    np.testing.assert_allclose(view.ui.histogram.get_flim_ranges()["L"], (0, 190.1))
    view.setFlimImage(image, auto_counts_zero=False, **options)
    np.testing.assert_allclose(view.ui.histogram.get_flim_ranges()["L"], (11.9, 190.1))


def test_autoscale_keeps_constant_images_visible_and_empty_images_black(view):
    image = np.ones((2, 2, 3))
    image[:, :, 0] = 0.5
    image[:, :, 2] = 100
    options = dict(render_mode="hsv", auto_counts=True, auto_quality=True)
    view.setFlimImage(image, **options)
    np.testing.assert_allclose(view.ui.histogram.get_flim_ranges()["L"], (0, 100))
    np.testing.assert_allclose(view.image.max(axis=-1), 1)
    image[:] = np.nan
    view.setFlimImage(image, **options)
    np.testing.assert_array_equal(view.image, 0)
    image[:] = 0
    view.setFlimImage(image, valid=np.zeros((2, 2), dtype=bool), **options)
    np.testing.assert_array_equal(view.image, 0)


def test_hue_wrap_follows_selected_arc_through_zero(view):
    image = sample_image()
    image[:, :5, 0] = 0.25
    image[:, 5:, 0] = 0.75
    image[:, :, 2] = 100
    options = dict(render_mode="hsv", hue_display_range=(0.8, 0.2),
                   auto_counts=True, hue_wrap=True, hue_wrap_mode="arc", force_quality_full=True)
    view.setFlimImage(image, **options)
    histogram = view.ui.histogram.item
    assert histogram._hcl_bounds["H"] == (0, 1)
    np.testing.assert_allclose(histogram._map_hue_for_display([0, 0.25, 0.5, 0.75, 1]),
                               [0.8, 0.9, 0, 0.1, 0.2], atol=1e-12)
    np.testing.assert_allclose(view.image[0, 0], [1, 0, 0.6], atol=1e-12)
    np.testing.assert_allclose(view.image[0, -1], [1, 0.6, 0], atol=1e-12)
    colorbar = histogram._hl_colorbar_image.image
    np.testing.assert_allclose(colorbar[0, -1], [0.8, 0, 1], atol=1e-12)
    np.testing.assert_allclose(colorbar[-1, -1], [0.8, 1, 0], atol=1e-12)
    assert colorbar[96, -1, 0] == 1  # The middle of the arc passes through red.
    assert np.max(colorbar[96, -1, 1:]) < 0.01
    assert np.isfinite(view.image).all()
    view.setFlimImage(image, hue_wrap=False, hue_display_range=(0.8, 0.2))
    np.testing.assert_allclose(histogram._map_hue_for_display([0, 0.5, 1]), [0.8, 0.5, 0.2])


@pytest.mark.parametrize("hue_range,expected_hue", [
    ((0.2, 0.6), [0.2, 0.3, 0.5, 0.6, 0.6, 0.6]),
    ((0.8, 0.2), [0.8, 0.9, 0.1, 0.2, 0.2, 0.2]),
    ((0.4, 0.4), [0.4] * 6),
    ((0, 1), [0, 0.25, 0.75, 1, 1, 1]),
])
def test_wrap_respects_hue_vis_endpoints_and_histogram_range(view, hue_range, expected_hue):
    from brighteyes_mcs.ui.qt.flim_image_view import hsv_to_rgb

    image = np.ones((1, 6, 3), dtype=float)
    image[0, :, 0] = [0.15, 0.25, 0.35, 0.45, 0.55, 0.65]
    image[:, :, 2] = 100
    options = dict(render_mode="hsv", auto_counts=True, force_quality_full=True,
                   hue_wrap=True, hue_wrap_mode="arc", hue_display_range=hue_range)
    view.setFlimImage(image, **options)
    view.ui.histogram.item._hcl_regions["H"].setRegion((0.2, 0.4))
    view.setFlimImage(image, **options)
    np.testing.assert_allclose(view.image[0], hsv_to_rgb(expected_hue, 1, 1), atol=1e-12)
    region = view.ui.histogram.get_flim_ranges()["H"]
    # Edits to Hue vis. apply to both the image and its cached colorbar.
    previous_colorbar = view.ui.histogram.item._hl_colorbar_image.image
    view.setFlimImage(image, **dict(options, hue_display_range=(0.1, 0.3)))
    assert view.ui.histogram.item._hl_colorbar_image.image is not previous_colorbar
    np.testing.assert_allclose(view.image[0], hsv_to_rgb(
        np.array([0.1, 0.15, 0.25, 0.3, 0.3, 0.3]), 1, 1,
    ), atol=1e-12)
    view.setFlimImage(image, **dict(options, hue_wrap=False, hue_display_range=(0.1, 0.3)))
    assert view.ui.histogram.get_flim_ranges()["H"] == region
    np.testing.assert_allclose(view.image[0], hsv_to_rgb(
        np.array([0.1, 0.15, 0.25, 0.3, 0.3, 0.3]), 1, 1,
    ), atol=1e-12)


@pytest.mark.parametrize("mode", ["hsv", "hsl", "hcl"])
def test_live_frames_render_once_and_reuse_colorbar(view, mode):
    import sys

    image = sample_image()
    with patch.object(sys, "excepthook") as uncaught, patch.object(
        view, "_apply_hcl_render", wraps=view._apply_hcl_render,
    ) as render:
        view.setFlimImage(image, render_mode=mode, auto_counts=True)
        assert render.call_count == 1
        colorbar = view.ui.histogram.item._hl_colorbar_image.image
        image[:, :, 2] *= 2
        view.setFlimImage(image, render_mode=mode, auto_counts=True)
        assert render.call_count == 2
        assert view.ui.histogram.item._hl_colorbar_image.image is colorbar
        view.ui.histogram.item._hcl_regions["H"].setRegion((0.2, 0.8))
        assert render.call_count > 2  # User edits still redraw immediately.
        uncaught.assert_not_called()


def test_switching_between_lifetime_and_intensity_has_no_qt_callback_errors(view):
    import sys

    with patch.object(sys, "excepthook") as uncaught:
        for mode in ("hsv", "hsl", "hcl"):
            view.setFlimImage(sample_image(), render_mode=mode, auto_counts=True)
            view.setImage(np.ones((10, 10)), levelMode="mono")
        uncaught.assert_not_called()


def test_repeat_range_wraps_without_changing_selected_colors(view):
    from brighteyes_mcs.ui.qt.flim_image_view import hsv_to_rgb

    image = np.ones((1, 4, 3))
    image[0, :, 0] = [0.15, 0.25, 0.35, 0.45]
    image[:, :, 2] = 100
    options = dict(render_mode="hsv", auto_counts=True, force_quality_full=True,
                   hue_wrap=True, hue_display_range=(0.2, 0.6))
    view.setFlimImage(image, **options)
    view.ui.histogram.item._hcl_regions["H"].setRegion((0.2, 0.4))
    view.setFlimImage(image, **options)
    np.testing.assert_allclose(view.image[0], hsv_to_rgb([0.5, 0.3, 0.5, 0.3], 1, 1), atol=1e-12)


def test_hue_equalization_expands_contrast_without_changing_histogram_units(view):
    image = np.ones((10, 100, 3))
    image[:, :, 0] = np.linspace(0.3, 0.4, 1000).reshape(10, 100)
    image[:, :, 2] = 100
    view.setFlimImage(image, render_mode="hsv", auto_counts=True, equalize_hue=True)
    histogram = view.ui.histogram.item
    displayed = histogram._map_hue_for_display(image[:, :, 0])
    assert np.ptp(displayed) > 0.95
    assert histogram.get_flim_ranges()["H"] == (0, 1)


def test_brightness_equalization_expands_dim_pixels(view):
    image = np.ones((10, 100, 3))
    image[:, :, 0] = 0.25
    image[:, :, 2] = np.exp(np.linspace(0, 5, 1000)).reshape(10, 100)
    options = dict(render_mode="hsv", auto_counts=True, percentiles=(0, 100), force_quality_full=True)
    view.setFlimImage(image, **options)
    before = np.median(view.image.max(axis=-1))
    view.setFlimImage(image, equalize_counts=True, **options)
    after = np.median(view.image.max(axis=-1))
    assert after > before + 0.2
    assert abs(after - 0.5) < 0.05


def test_slow_histogram_analysis_does_not_block_new_images_and_is_throttled(view, monkeypatch):
    import threading
    from brighteyes_mcs.ui.qt import flim_image_view as module

    entered, release = threading.Event(), threading.Event()
    original = module.analyze_lifetime_histograms
    calls = []

    def analyze(*args):
        calls.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(module, "analyze_lifetime_histograms", analyze)
    image = sample_image()
    try:
        view.setFlimImage(image, render_mode="hsv", auto_counts=True, analysis_interval=10,
                          hue_offset=0.25, value_gamma=2)
        assert entered.wait(2)
        future = view._analysis_future
        image[:, :, 0] = 0.25
        view.setFlimImage(image, render_mode="hsv", auto_counts=True, analysis_interval=10)
        np.testing.assert_array_equal(view._hcl_source[:, :, 0], 0.25)
        assert view._analysis_future is future
        assert calls == [calls[0]] and calls[0] != threading.get_ident()
    finally:
        release.set()
    future.result(timeout=2)
    view._poll_histograms()
    view.setFlimImage(image, render_mode="hsv", auto_counts=True, analysis_interval=10)
    assert len(calls) == 1
    assert view._analysis_future is None


@pytest.mark.parametrize("changed,expected", [
    ({"percentiles": (20, 80)}, (20.8, 80.2)),
    ({"auto_counts_zero": True}, (0, 99.01)),
])
def test_outdated_analysis_is_replaced_after_settings_change(view, monkeypatch, changed, expected):
    from concurrent.futures import Future
    from brighteyes_mcs.ui.qt import flim_image_view as module

    jobs = []

    class Executor:
        def submit(self, function, *args):
            future = Future()
            jobs.append((future, function, args))
            return future

    monkeypatch.setattr(module, "_HISTOGRAM_EXECUTOR", Executor())
    options = dict(render_mode="hsv", auto_counts=True, analysis_interval=10)
    view.setFlimImage(sample_image(), **options)
    view.setFlimImage(sample_image(), **changed, **options)
    assert len(jobs) == 1
    future, function, args = jobs[0]
    future.set_result(function(*args))
    view._poll_histograms()
    assert len(jobs) == 2
    future, function, args = jobs[1]
    future.set_result(function(*args))
    view._poll_histograms()
    np.testing.assert_allclose(view.ui.histogram.get_flim_ranges()["L"], expected)


def test_hue_and_gamma_update_image_and_colorbar_without_refitting(view, monkeypatch):
    from concurrent.futures import Future
    from brighteyes_mcs.ui.qt import flim_image_view as module

    jobs = []

    class Executor:
        def submit(self, function, *args):
            future = Future()
            jobs.append(future)
            return future

    monkeypatch.setattr(module, "_HISTOGRAM_EXECUTOR", Executor())
    image = np.ones((2, 2, 3))
    image[:, :, 0] = 0.5
    image[:, :, 2] = 0.25
    options = dict(render_mode="hsv", auto_counts=True, analysis_interval=10, force_quality_full=True)
    view.setFlimImage(image, **options)
    colorbar = view.ui.histogram.item._hl_colorbar_image.image
    view.setFlimImage(image, hue_offset=0.25, value_gamma=2, **options)
    assert len(jobs) == 1 and not jobs[0].done()
    np.testing.assert_allclose(view.image[0, 0], [0.25, 0, 0.5])
    assert view.ui.histogram.item._hl_colorbar_image.image is not colorbar


def test_equalization_is_frozen_until_manual_refresh_and_refreshes_independently(view, monkeypatch):
    from brighteyes_mcs.ui import lifetime_scaling

    original = lifetime_scaling.equalization_lut
    calls = []

    def calculate(values):
        calls.append(True)
        return original(values)

    monkeypatch.setattr(lifetime_scaling, "equalization_lut", calculate)
    image = sample_image()
    image[:, :, 0] = np.linspace(0.1, 0.9, 100).reshape(10, 10)
    options = dict(render_mode="hsv", auto_counts=True, equalize_hue=True, equalize_counts=True)
    view.setFlimImage(image, **options)
    item = view.ui.histogram.item
    h_lut, l_lut = item._equalization_luts["H"], item._equalization_luts["L"]
    assert h_lut is not None and l_lut is not None
    assert len(calls) == 2
    revision = item._equalization_revision
    image[:, :, 0] = np.linspace(0.2, 0.3, 100).reshape(10, 10)
    image[:, :, 2] *= 5
    for _ in range(3):
        view.setFlimImage(image, **options)
    assert item._equalization_luts["H"] is h_lut
    assert item._equalization_luts["L"] is l_lut
    assert item._equalization_revision == revision
    assert len(calls) == 2  # Histogram/percentile refresh never refits equalization.
    view.refreshEqualization("H")
    assert len(calls) == 3
    assert item._equalization_luts["H"] is not h_lut
    assert item._equalization_luts["L"] is l_lut
    view.setFlimImage(image, **dict(options, equalize_hue=False))
    view.setFlimImage(image, **options)
    assert len(calls) == 4  # Checking again explicitly fits it again.


def test_equalization_refresh_during_analysis_discards_outdated_fit(view, monkeypatch):
    from concurrent.futures import Future
    from brighteyes_mcs.ui.qt import flim_image_view as module

    jobs = []

    class Executor:
        def submit(self, function, *args):
            future = Future()
            jobs.append((future, function, args))
            return future

    monkeypatch.setattr(module, "_HISTOGRAM_EXECUTOR", Executor())
    view.setFlimImage(sample_image(), render_mode="hsv", auto_counts=True,
                      equalize_counts=True, analysis_interval=10)
    view.refreshEqualization("L")
    future, function, args = jobs[0]
    future.set_result(function(*args))
    view._poll_histograms()
    assert "L" not in view.ui.histogram.item._equalization_luts
    assert len(jobs) == 2
    future, function, args = jobs[1]
    future.set_result(function(*args))
    view._poll_histograms()
    assert view.ui.histogram.item._equalization_luts["L"] is not None
    assert not view.ui.histogram.item.pending_equalization()["L"]


def test_equalized_colorbar_has_regular_colors_and_nonlinear_lifetime_ticks(view):
    from brighteyes_mcs.ui.qt.flim_image_view import hsv_to_rgb

    image = np.ones((10, 100, 3))
    image[:, :, 0] = 0.25 + 0.4 * np.linspace(0, 1, 1000).reshape(10, 100) ** 3
    image[:, :, 2] = 100
    options = dict(render_mode="hsv", auto_counts=True, equalize_hue=True,
                   hue_display_range=(2 / 3, 0), h_display_max=25)
    view.setFlimImage(image, **options)
    item = view.ui.histogram.item
    gradient = item._hl_colorbar_image.image.copy()
    expected = hsv_to_rgb(np.linspace(2 / 3, 0, gradient.shape[0]), 1, 1)
    np.testing.assert_allclose(gradient[:, -1], expected)
    ticks = item._hl_colorbar_plot.getAxis("right")._tickLevels[0]
    np.testing.assert_allclose([pos for pos, _ in ticks], [0, 0.25, 0.5, 0.75, 1])
    labels = np.array([float(label) for _, label in ticks])
    np.testing.assert_allclose(labels[[0, -1]], [6.25, 16.25])
    assert not np.allclose(np.diff(labels), np.diff(labels)[0])
    image[:, :, 0] = 0.25 + 0.4 * np.linspace(0, 1, 1000).reshape(10, 100) ** 0.2
    view.setFlimImage(image, **options)
    view.refreshEqualization("H")
    np.testing.assert_array_equal(item._hl_colorbar_image.image, gradient)
    assert item._hl_colorbar_plot.getAxis("right")._tickLevels[0] != ticks


@pytest.mark.parametrize("axis_order", ["col-major", "row-major"])
@pytest.mark.parametrize("equalize", [False, True])
def test_hover_marker_tracks_transformed_pixel_lifetime(view, axis_order, equalize):
    view.imageItem.setOpts(axisOrder=axis_order)
    image = np.ones((2, 3, 3))
    image[:, :, 0] = [[0.2, 0.3, 0.4], [0.5, 0.6, 0.75]]
    image[:, :, 2] = 100
    view.setFlimImage(image, render_mode="hsv", auto_counts=True, equalize_hue=equalize,
                      h_display_max=20, h_shift=0.1, pos=(10, -7), scale=(2, 3))
    local = QPointF(1.5, 2.5) if axis_order == "col-major" else QPointF(2.5, 1.5)
    scene = view.imageItem.mapToScene(local)
    view.scene.sigMouseMoved.emit(scene)
    item = view.ui.histogram.item
    assert item._hl_hover_line.isVisible()
    assert item._hl_hover_phase == pytest.approx(0.65)
    assert item._hl_hover_line.label.format == "13.000 ns"
    assert item._hl_hover_line.label.textItem.toPlainText() == "13.000 ns"
    assert item._hl_hover_line.value() == pytest.approx(item.colorbar_lifetime_position(0.65))
    if not equalize:
        assert item._hl_hover_line.value() == pytest.approx(13)
    view.scene.sigMouseMoved.emit(view.imageItem.mapToScene(QPointF(-1, -1)))
    assert not item._hl_hover_line.isVisible()
    view.scene.sigMouseMoved.emit(scene)
    QCoreApplication.sendEvent(view.ui.graphicsView.viewport(), QEvent(QEvent.Type.Leave))
    assert not item._hl_hover_line.isVisible()


def test_hover_marker_hides_for_invalid_pixels_and_updates_with_new_frame(view):
    image = np.ones((2, 3, 3))
    image[:, :, 0] = 0.4
    image[:, :, 2] = 100
    valid = np.ones((2, 3), dtype=bool)
    valid[0, 0] = False
    options = dict(render_mode="hsv", auto_counts=True, h_display_max=25, valid=valid)
    view.setFlimImage(image, **options)
    view.scene.sigMouseMoved.emit(view.imageItem.mapToScene(QPointF(0.5, 0.5)))
    assert not view.ui.histogram.item._hl_hover_line.isVisible()
    view.scene.sigMouseMoved.emit(view.imageItem.mapToScene(QPointF(1.5, 1.5)))
    assert view.ui.histogram.item._hl_hover_line.value() == pytest.approx(10)
    image[1, 1, 0] = 0.6
    view.setFlimImage(image, **options)
    assert view.ui.histogram.item._hl_hover_line.value() == pytest.approx(15)
    view.clearFlimImage()
    assert not view.ui.histogram.item._hl_hover_line.isVisible()


def test_hover_only_moves_marker_without_analysis_or_image_conversion(view):
    image = sample_image()
    image[:, :, 0] = np.linspace(0.2, 0.7, 100).reshape(10, 10)
    view.setFlimImage(image, render_mode="hsv", equalize_hue=True, auto_counts=True)
    with patch.object(view, "_update_histograms") as analysis, patch.object(
        view, "_apply_hcl_render",
    ) as render:
        for x, y in ((1.5, 2.5), (3.5, 4.5), (6.5, 7.5)):
            view.scene.sigMouseMoved.emit(view.imageItem.mapToScene(QPointF(x, y)))
        analysis.assert_not_called()
        render.assert_not_called()
    assert view.ui.histogram.item._hl_hover_line.isVisible()

