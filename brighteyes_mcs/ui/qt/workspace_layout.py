"""Compact dock forms and keep wide tools independent of the live preview."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)


def _row(*widgets):
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return row


def _empty(layout):
    while layout.count():
        layout.takeAt(0)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
    for column in range(layout.columnCount()):
        layout.setColumnStretch(column, 0)
        layout.setColumnMinimumWidth(column, 0)


def scroll_tool_contents(page):
    """Keep the page itself and all widget references; scroll only its contents."""
    if page.layout() is None or page.property("compactToolScroll"):
        return
    content = QWidget()
    content.setObjectName(page.objectName() + "_contents")
    content.setLayout(page.layout())
    area = QScrollArea(page)
    area.setObjectName(page.objectName() + "_scroll")
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidgetResizable(True)
    area.setWidget(content)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(area)
    page.setProperty("compactToolScroll", True)


def compact_trace_controls(ui):
    grid = ui.gridLayout_62
    _empty(grid)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    grid.setColumnStretch(1, 1)
    ui.gridLayout_70.removeItem(ui.verticalSpacer_2)
    ui.gridLayout_70.removeWidget(ui.groupBox_26)
    ui.groupBox_26.hide()
    ui.gridLayout_70.setRowStretch(1, 1)
    grid.addWidget(ui.pushButton_trace, 0, 0)
    grid.addWidget(_row(ui.checkBox_trace_on, ui.checkBox_trace_autorange), 0, 1)
    for row, label, value in (
        (1, ui.label_73, ui.doubleSpinBox_binsize),
        (2, ui.label_74, ui.doubleSpinBox_maxlength),
        (3, ui.label_76, ui.label_trace_total_bins),
    ):
        grid.addWidget(label, row, 0)
        grid.addWidget(value, row, 1, alignment=Qt.AlignmentFlag.AlignLeft)
    for spin in (ui.doubleSpinBox_binsize, ui.doubleSpinBox_maxlength,
                 ui.doubleSpinBox_trace_dfd_start_percent, ui.doubleSpinBox_trace_dfd_end_percent):
        spin.setMaximumWidth(125)
    ui.label_plot_channel.setWordWrap(True)
    ui.label_plot_channel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    grid.addWidget(ui.label_plot_channel, 4, 0, 1, 2)
    grid.addWidget(_row(ui.checkBox_trace_dfd_time_axis, ui.checkBox_trace_dfd_align_peak), 5, 0, 1, 2)
    grid.addWidget(ui.label_trace_dfd_fit_levels, 6, 0)
    grid.addWidget(_row(ui.doubleSpinBox_trace_dfd_start_percent, QLabel("to"),
                        ui.doubleSpinBox_trace_dfd_end_percent), 6, 1)


def _compact_left_controls(ui):
    # Detector selection sits above the smaller channel/DFD fields, rather
    # than widening their columns to accommodate the longest detector name.
    ui.comboBox_detector_model.setMinimumContentsLength(12)
    grid = ui.gridLayout_105
    _empty(grid)
    grid.addWidget(ui.label_detector_model, 0, 0)
    grid.addWidget(ui.comboBox_detector_model, 0, 1, 1, 2)
    grid.addWidget(ui.checkBox_fifo_digital, 1, 0)
    grid.addWidget(ui.checkBox_fifo_analog, 2, 0)
    grid.addWidget(ui.groupBox_13, 1, 1, 2, 1)
    grid.addWidget(ui.groupBox_12, 1, 2, 2, 1)
    grid = ui.gridLayout_108
    _empty(grid)
    grid.addWidget(ui.groupBox_11, 0, 0, 2, 1)
    grid.addWidget(ui.groupBox_9, 0, 1)
    grid.addWidget(ui.groupBox_16, 1, 1)
    grid.addWidget(ui.groupBox_18, 2, 0, 1, 2)
    grid.addWidget(ui.groupBox_10, 3, 0, 1, 2)
    ui.gridLayout_89.addWidget(ui.pushButton_14, 0, 0)
    ui.gridLayout_89.addWidget(ui.pushButton_externalProgram, 0, 1)
    ui.label_FPGA_status.setWordWrap(True)
    ui.label_FPGA_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    for name in ("spinBox_timeresolution", "spinBox_waitForLaser", "spinBox_waitAfterFrame"):
        getattr(ui, name).setMaximumWidth(140)
    ui.gridLayout_9.removeItem(ui.verticalSpacer_11)
    ui.gridLayout_6.removeItem(ui.verticalSpacer_17)

    grid = ui.gridLayout_5
    _empty(grid)
    for row, label, spin, size_label, size_value, text in (
        (0, ui.label_nx, ui.spinBox_nx, ui.label_105, ui.label_pixelsize_x, "X size"),
        (1, ui.label_ny, ui.spinBox_ny, ui.label_104, ui.label_pixelsize_y, "Y size"),
        (2, ui.label_nframe, ui.spinBox_nframe, ui.label_101, ui.label_pixelsize_z, "Z size"),
    ):
        size_label.setToolTip(size_label.text())
        size_label.setText(text)
        grid.addWidget(label, row, 0)
        grid.addWidget(spin, row, 1)
        grid.addWidget(_row(size_label, size_value), row, 2)
    grid.addWidget(ui.label_nrepetition, 3, 0)
    grid.addWidget(ui.spinBox_nrepetition, 3, 1)
    grid.addWidget(ui.pushButton_18, 3, 2)
    ui.gridLayout_109.removeItem(ui.horizontalSpacer_29)
    ui.gridLayout_17.removeItem(ui.verticalSpacer_24)
    ui.gridLayout_17.removeItem(ui.horizontalSpacer_4)


def _compact_right_controls(ui):
    # The micro-image controls no longer compete horizontally with the image
    # and its histogram; the dock can fit without an internal horizontal bar.
    ui.gridLayout_3434.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
    ui.gridLayout_68.setContentsMargins(4, 4, 4, 4)
    grid = ui.gridLayout_47
    grid.setVerticalSpacing(4)
    grid.removeItem(ui.gridLayout_microimage)
    grid.removeItem(ui.verticalSpacer_15)
    grid.addLayout(ui.gridLayout_microimage, 0, 0, 1, 2)
    grid.addWidget(ui.label_microimage, 1, 0)
    grid.addWidget(ui.comboBox_fingerprint, 1, 1)
    grid.addWidget(ui.pushButton_4, 2, 0)
    grid.addWidget(ui.checkBox_autoscale_fingerprint, 2, 1)


def configure_workspace_layout(ui):
    compact_trace_controls(ui)
    _compact_left_controls(ui)
    _compact_right_controls(ui)
    for index in range(ui.tabWidget.count()):
        page = ui.tabWidget.widget(index)
        if page is not ui.tab_preview:
            scroll_tool_contents(page)
    # Hidden advanced pages must not set the minimum width of an entire
    # tabified dock column. Only those dense tools get local scrolling.
    for name in ("dockWidget_activatefifo", "dockWidget_laser", "dockWidget_adv2",
                 "dockWidget_filename", "dockWidget_listfile", "dockWidget_pos_aux",
                 "dockWidget_scan_preset", "dockWidget_AnalogCfg", "dockWidget_analogOut"):
        scroll_tool_contents(getattr(ui, name).widget())


def size_default_docks(window, ui):
    """Allocate the dock columns after startup has maximized the window."""
    window.resizeDocks([ui.dockWidget_preview, ui.dockWidget_trace], [340, 380], Qt.Horizontal)
    window.resizeDocks(
        [ui.dockWidget_fingerprint, ui.dockWidget_trace, ui.dockWidget_statistics, ui.dockWidget_panorama],
        [210, 260, 205, 175], Qt.Vertical,
    )
