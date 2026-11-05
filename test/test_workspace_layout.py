"""Dock width and tab isolation regressions, without acquisition hardware."""

import os
from pathlib import Path
from xml.etree import ElementTree

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QScrollArea, QVBoxLayout, QWidget

from brighteyes_mcs.ui.qt.main_window_design import Ui_MainWindowDesign
from brighteyes_mcs.ui.qt.workspace_layout import configure_workspace_layout, scroll_tool_contents


@pytest.fixture
def panel():
    app = QApplication.instance() or QApplication([])
    original_font = app.font()
    if os.name == "nt":
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
        app.setFont(QFont("Segoe UI", 9))
    window = QMainWindow()
    source = Path(__file__).resolve().parents[1] / "brighteyes_mcs/ui/qt/main_window_design.ui"
    for connection in ElementTree.parse(source).findall(".//connections/connection"):
        if connection.findtext("receiver") == "MainWindowDesign":
            name = connection.findtext("slot").split("(")[0]
            if not hasattr(window, name):
                setattr(window, name, lambda *args: None)
    ui = Ui_MainWindowDesign()
    ui.setupUi(window)
    configure_workspace_layout(ui)
    yield app, window, ui
    window.close()
    window.deleteLater()
    app.setFont(original_font)


def test_trace_conf_no_longer_widens_trace_when_its_tab_is_hidden(panel):
    app, window, ui = panel
    window.setCentralWidget(QWidget())
    for dock in window.findChildren(type(ui.dockWidget_trace)):
        if dock not in (ui.dockWidget_trace, ui.dockWidget_traceConf):
            dock.hide()
    window.tabifyDockWidget(ui.dockWidget_trace, ui.dockWidget_traceConf)
    ui.doubleSpinBox_binsize.setDecimals(7)
    ui.label_plot_channel.setText("Ch. selected: LIFETIME_HSV — Ch 24")
    window.resize(1200, 900)
    window.show()
    ui.dockWidget_traceConf.raise_()
    app.processEvents()
    assert ui.dockWidget_traceConf.minimumSizeHint().width() < 360
    window.resizeDocks([ui.dockWidget_traceConf], [380], Qt.Orientation.Horizontal)
    app.processEvents()
    assert ui.dockWidget_traceConf.width() <= 380
    ui.dockWidget_trace.raise_()
    app.processEvents()
    assert ui.dockWidget_trace.width() <= 380
    # Lengthening a channel description cannot widen the numeric form columns.
    ui.label_plot_channel.setText("Ch. selected: LIFETIME_HSV — " + "reference configuration " * 8)
    app.processEvents()
    assert ui.dockWidget_traceConf.minimumSizeHint().width() < 360
    assert ui.dockWidget_trace.width() <= 380


def test_dense_tools_scroll_locally_without_replacing_their_tab_objects(panel):
    _, _, ui = panel
    assert ui.tab_preview.findChild(QScrollArea) is None
    assert ui.tabWidget.indexOf(ui.tab_config) >= 0
    assert ui.tab_config.findChild(QScrollArea) is not None
    assert ui.tab_fcs.findChild(QScrollArea) is not None
    assert ui.dockWidget_adv2.widget().minimumSizeHint().width() < 200


def test_plugin_page_keeps_its_widgets_accessible_without_inflating_other_tabs(panel):
    app, _, ui = panel
    page = QWidget()
    page.setObjectName("widePlugin")
    layout = QVBoxLayout(page)
    label = QLabel("Channel timing " * 100)
    layout.addWidget(label)
    assert page.minimumSizeHint().width() > 1200
    scroll_tool_contents(page)
    ui.tabWidget.addTab(page, "Wide plugin")
    ui.tabWidget.setCurrentWidget(page)
    ui.tabWidget.resize(600, 400)
    ui.tabWidget.show()
    app.processEvents()
    area = page.findChild(QScrollArea)
    assert ui.tabWidget.currentWidget() is page
    assert area.widget().isAncestorOf(label)
    assert page.minimumSizeHint().width() < 200
    assert area.horizontalScrollBar().maximum() > 0
    scroll_tool_contents(page)
    assert page.findChildren(QScrollArea) == [area]
