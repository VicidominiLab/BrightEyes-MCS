"""Compact lifetime-display controls shared by the acquisition backends."""

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSlider, QStyle, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from .support import DoubleClickDoubleSpinBox


class LifetimeControls(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.setObjectName("lifetimeControls")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.ui = ui = window.ui
        self.window = window
        ui.comboBox_lifetime_estimator = QComboBox(self)
        ui.comboBox_lifetime_estimator.setObjectName("comboBox_lifetime_estimator")
        ui.comboBox_lifetime_estimator.addItem("Circular mean (3 windows)", "circular")
        ui.comboBox_lifetime_estimator.addItem("Exponential Poisson (3 windows)", "exponential")
        ui.comboBox_lifetime_estimator.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        ui.comboBox_lifetime_estimator.setMinimumContentsLength(16)
        ui.comboBox_lifetime_estimator.setToolTip(
            "Large-preview lifetime method. Exponential Poisson fits a single decay using the "
            "global DFD peak and actual window widths. Assumes negligible background and a narrow "
            "instrument response. Range: 1/8 DFD bin to one laser period; unresolved fits are black. "
            "NI requires DFD trace updates for the peak reference. "
            "S/C measures estimated precision (disable Full S/C = 1 to show it). "
            "Changes apply to incoming pixels during acquisition."
        )
        self.setStyleSheet("""
            QWidget#lifetimeControls QTabWidget::pane {
                border: 1px solid palette(mid); border-radius: 5px;
            }
            QWidget#lifetimeControls QTabBar::tab { padding: 5px 12px; }
            QWidget#lifetimeControls QDoubleSpinBox { min-height: 24px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        self.source_row = QWidget(self)
        source = QHBoxLayout(self.source_row)
        source.setContentsMargins(12, 0, 12, 0)
        source.addWidget(QLabel("DFD source"))
        ui.comboBox_lifetime_channel = QComboBox(self.source_row)
        ui.comboBox_lifetime_channel.setObjectName("comboBox_lifetime_channel")
        ui.comboBox_lifetime_channel.addItem("Sum", None)
        for channel in range(49):
            ui.comboBox_lifetime_channel.addItem(f"Ch {channel}", channel)
        ui.comboBox_lifetime_channel.setToolTip(
            "Use one detector channel or the sum of detector channels selected by the fingerprint mask."
        )
        source.addWidget(ui.comboBox_lifetime_channel)
        source.addWidget(QLabel("Lifetime estimator"))
        source.addWidget(ui.comboBox_lifetime_estimator)
        source.addStretch(1)
        layout.addWidget(self.source_row)
        ui.comboBox_spad_channels.currentTextChanged.connect(self._sync_source_channels)
        self._sync_source_channels()
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("lifetimeControlTabs")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout.addWidget(self.tabs)

        hue = self._tab("Hue")
        ui.label_lifetime_hue_range = QLabel("Color range")
        hue.addWidget(ui.label_lifetime_hue_range, 0, 0)
        ui.doubleSpinBox_lifetime_hue_min = self._spin("hue_min", 0, 1, 2 / 3, 4, 0.01)
        ui.doubleSpinBox_lifetime_hue_max = self._spin("hue_max", 0, 1, 0, 4, 0.01)
        hue.addWidget(self._row(ui.doubleSpinBox_lifetime_hue_min, QLabel("to"),
                               ui.doubleSpinBox_lifetime_hue_max), 0, 1, 1, 2)
        ui.checkBox_lifetime_equalize_hue = QCheckBox("Equalize H")
        ui.checkBox_lifetime_equalize_hue.setToolTip(
            "Expand lifetime contrast. Calculated once when enabled; use the refresh button to update."
        )
        ui.toolButton_lifetime_equalize_hue_update = self._equalization_update(
            ui.checkBox_lifetime_equalize_hue, "H",
        )
        hue.addWidget(self._row(ui.checkBox_lifetime_equalize_hue,
                               ui.toolButton_lifetime_equalize_hue_update), 0, 3)
        hue.addWidget(QLabel("Hue shift"), 1, 0)
        ui.doubleSpinBox_lifetime_hue_shift = self._spin("hue_shift", -360, 360, 0, 1, 1, "°")
        ui.doubleSpinBox_lifetime_hue_shift.setWrapping(True)
        ui.doubleSpinBox_lifetime_hue_shift.setToolTip("Rotate display colors modulo 360°, independently of lifetime correction")
        ui.slider_lifetime_hue_shift = QSlider(Qt.Orientation.Horizontal)
        ui.slider_lifetime_hue_shift.setRange(0, 3599)
        hue.addWidget(ui.slider_lifetime_hue_shift, 1, 1, 1, 2)
        hue.addWidget(ui.doubleSpinBox_lifetime_hue_shift, 1, 3)
        ui.checkBox_lifetime_hue_wrap = QCheckBox("Wrap H")
        ui.checkBox_lifetime_hue_wrap.setToolTip("Repeat the selected color range, or follow an arc through 0/1")
        ui.comboBox_lifetime_wrap_mode = QComboBox()
        ui.comboBox_lifetime_wrap_mode.addItems(["Repeat range", "Across 0/1"])
        hue.addWidget(ui.checkBox_lifetime_hue_wrap, 2, 0)
        hue.addWidget(ui.comboBox_lifetime_wrap_mode, 2, 1, 1, 2)

        tone = self._tab("Brightness & saturation")
        tone.addWidget(QLabel("Brightness"), 0, 0)
        ui.checkBox_lifetime_auto_counts = QCheckBox("Autoscale V/L")
        ui.checkBox_lifetime_auto_counts.setChecked(True)
        ui.checkBox_lifetime_auto_counts_zero = QCheckBox("From 0")
        ui.checkBox_lifetime_auto_counts_zero.setToolTip(
            "Keep zero intensity at 0% brightness; autoscale only the upper V/L limit."
        )
        ui.checkBox_lifetime_auto_counts.toggled.connect(ui.checkBox_lifetime_auto_counts_zero.setEnabled)
        ui.checkBox_lifetime_equalize_counts = QCheckBox("Equalize V/L")
        ui.checkBox_lifetime_equalize_counts.setToolTip(
            "Expand brightness contrast. Calculated once when enabled; use the refresh button to update."
        )
        tone.addWidget(self._row(ui.checkBox_lifetime_auto_counts,
                                ui.checkBox_lifetime_auto_counts_zero), 0, 1)
        ui.toolButton_lifetime_equalize_counts_update = self._equalization_update(
            ui.checkBox_lifetime_equalize_counts, "L",
        )
        tone.addWidget(self._row(ui.checkBox_lifetime_equalize_counts,
                                ui.toolButton_lifetime_equalize_counts_update), 0, 2, 1, 2)
        ui.widget_preview_gamma = QWidget(window)
        gamma = QHBoxLayout(ui.widget_preview_gamma)
        gamma.setContentsMargins(0, 0, 0, 0)
        ui.label_lifetime_gamma = QLabel("Gamma")
        ui.label_lifetime_gamma.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        gamma.addWidget(ui.label_lifetime_gamma)
        ui.doubleSpinBox_lifetime_value_gamma = self._spin("value_gamma", 0.1, 5, 1, 2, 0.1)
        ui.doubleSpinBox_lifetime_value_gamma.setMaximumWidth(85)
        ui.doubleSpinBox_lifetime_value_gamma.setToolTip(
            "Display output = input^(1/gamma). Above 1 brightens shadows; 1 is neutral. "
            "Regular images use the histogram levels; lifetime HSV applies gamma to V after equalization."
        )
        ui.slider_lifetime_value_gamma = QSlider(Qt.Orientation.Horizontal)
        ui.slider_lifetime_value_gamma.setRange(10, 500)
        ui.slider_lifetime_value_gamma.setValue(100)
        ui.slider_lifetime_value_gamma.setMinimumWidth(60)
        ui.slider_lifetime_value_gamma.setMaximumWidth(120)
        gamma.addWidget(ui.slider_lifetime_value_gamma, 1)
        gamma.addWidget(ui.doubleSpinBox_lifetime_value_gamma)
        tone.addWidget(QLabel("Saturation"), 1, 0)
        ui.checkBox_lifetime_force_quality_full = QCheckBox("Full S/C = 1")
        ui.checkBox_lifetime_force_quality_full.setChecked(True)
        ui.checkBox_lifetime_auto_quality = QCheckBox("Autoscale S/C")
        ui.checkBox_lifetime_auto_quality.setToolTip("Disable Full S/C = 1 to use saturation scaling")
        tone.addWidget(ui.checkBox_lifetime_force_quality_full, 1, 1)
        tone.addWidget(ui.checkBox_lifetime_auto_quality, 1, 2, 1, 2)

        analysis = self._tab("Histogram & correction")
        analysis.addWidget(QLabel("Percentiles"), 0, 0)
        ui.doubleSpinBox_lifetime_percentile_low = self._spin("percentile_low", 0, 100, 1, 1, 1, " %")
        ui.doubleSpinBox_lifetime_percentile_high = self._spin("percentile_high", 0, 100, 99, 1, 1, " %")
        analysis.addWidget(self._row(ui.doubleSpinBox_lifetime_percentile_low, QLabel("to"),
                                    ui.doubleSpinBox_lifetime_percentile_high), 0, 1, 1, 3)
        analysis.addWidget(QLabel("Histogram update"), 1, 0)
        ui.doubleSpinBox_lifetime_analysis_interval = self._spin("analysis_interval", 0.2, 10, 1, 1, 0.1, " s")
        ui.doubleSpinBox_lifetime_analysis_interval.setToolTip("Background analysis interval; images keep updating using cached results")
        analysis.addWidget(ui.doubleSpinBox_lifetime_analysis_interval, 1, 1)
        ui.label_delta_tau_ns = QLabel("Lifetime correction")
        ui.doubleSpinBox_delta_tau_ns = DoubleClickDoubleSpinBox(self)
        ui.doubleSpinBox_delta_tau_ns.setDecimals(4)
        ui.doubleSpinBox_delta_tau_ns.setRange(0, 1e6)
        ui.doubleSpinBox_delta_tau_ns.setSingleStep(0.1)
        ui.doubleSpinBox_delta_tau_ns.setSuffix(" ns")
        ui.doubleSpinBox_delta_tau_ns.setMaximumWidth(125)
        ui.pushButton_delta_tau_auto = QPushButton("Auto fit")
        ui.pushButton_delta_tau_auto.setToolTip("Correct lifetime from the cumulative fit; HSV runs once after 20% of the first frame")
        analysis.addWidget(ui.label_delta_tau_ns, 2, 0)
        analysis.addWidget(self._row(ui.doubleSpinBox_delta_tau_ns, ui.pushButton_delta_tau_auto), 2, 1, 1, 3)

        for widget in (ui.doubleSpinBox_lifetime_hue_min, ui.doubleSpinBox_lifetime_hue_max,
                       ui.doubleSpinBox_lifetime_percentile_low, ui.doubleSpinBox_lifetime_percentile_high,
                       ui.doubleSpinBox_lifetime_analysis_interval):
            widget.valueChanged.connect(window.lifetimeDisplaySettingsChanged)
        for widget in (ui.checkBox_lifetime_hue_wrap, ui.checkBox_lifetime_force_quality_full,
                       ui.checkBox_lifetime_auto_counts, ui.checkBox_lifetime_auto_quality,
                       ui.checkBox_lifetime_auto_counts_zero,
                       ui.checkBox_lifetime_equalize_hue, ui.checkBox_lifetime_equalize_counts):
            widget.toggled.connect(window.lifetimeDisplaySettingsChanged)
        ui.comboBox_lifetime_wrap_mode.currentTextChanged.connect(window.lifetimeDisplaySettingsChanged)
        ui.comboBox_lifetime_channel.currentTextChanged.connect(window.lifetimeDisplaySettingsChanged)
        ui.comboBox_lifetime_estimator.currentIndexChanged.connect(window.lifetimeEstimatorChanged)
        ui.doubleSpinBox_lifetime_hue_shift.valueChanged.connect(self._hue_shift_changed)
        ui.slider_lifetime_hue_shift.valueChanged.connect(lambda value: ui.doubleSpinBox_lifetime_hue_shift.setValue(value / 10))
        ui.doubleSpinBox_lifetime_value_gamma.valueChanged.connect(self._gamma_changed)
        ui.slider_lifetime_value_gamma.valueChanged.connect(lambda value: ui.doubleSpinBox_lifetime_value_gamma.setValue(value / 100))
        ui.doubleSpinBox_delta_tau_ns.valueChanged.connect(window.colorLifetimeDeltaTauChanged)
        ui.pushButton_delta_tau_auto.clicked.connect(window.colorLifetimeDeltaTauUseHistogramMean)

    def _sync_source_channels(self, *_args):
        count = int(self.ui.comboBox_spad_channels.currentText())
        for index in range(1, 50):
            self.ui.comboBox_lifetime_channel.model().item(index).setEnabled(index <= count)

    def set_lifetime_mode(self, active, dfd_source_active=False):
        self.tabs.setVisible(active)
        self.source_row.setVisible(dfd_source_active)
        self.setVisible(active or dfd_source_active)

    def _tab(self, title):
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(12, 9, 12, 9)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        grid.setColumnStretch(2, 1)
        self.tabs.addTab(page, title.replace("&", "&&"))
        return grid

    def _equalization_update(self, checkbox, channel):
        button = QToolButton(self)
        button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        button.setAutoRaise(True)
        button.setFixedSize(24, 24)
        label = "H" if channel == "H" else "V/L"
        button.setToolTip(f"Recalculate {label} equalization from the current image")
        button.setAccessibleName(f"Update {label} equalization")
        button.setEnabled(checkbox.isChecked())
        checkbox.toggled.connect(button.setEnabled)
        button.clicked.connect(lambda: self.window.refreshLifetimeEqualization(channel))
        return button

    def _spin(self, name, low, high, value, decimals, step, suffix=""):
        spin = QDoubleSpinBox(self)
        spin.setObjectName("doubleSpinBox_lifetime_" + name)
        spin.setRange(low, high)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setMinimumWidth(78)
        spin.setMaximumWidth(110)
        return spin

    def _row(self, *widgets):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return row

    def _hue_shift_changed(self, value):
        wrapped = value % 360
        with QSignalBlocker(self.ui.doubleSpinBox_lifetime_hue_shift):
            self.ui.doubleSpinBox_lifetime_hue_shift.setValue(wrapped)
        with QSignalBlocker(self.ui.slider_lifetime_hue_shift):
            self.ui.slider_lifetime_hue_shift.setValue(round(wrapped * 10))
        self.window.lifetimeDisplaySettingsChanged()

    def _gamma_changed(self, value):
        with QSignalBlocker(self.ui.slider_lifetime_value_gamma):
            self.ui.slider_lifetime_value_gamma.setValue(round(value * 100))
        self.window.lifetimeDisplaySettingsChanged()
