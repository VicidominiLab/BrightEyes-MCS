"""The three-source editor preserves filtering, writes and existing Status tools."""

import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget, QTreeView, QVBoxLayout, QWidget

from brighteyes_mcs.ui.qt.register_browser import RegisterBrowser
from brighteyes_mcs.ui.qt.register_workspace import RegisterWorkspace


pytestmark = pytest.mark.qt
SOURCE_NAMES = ("Read Conf. FPGA", "Conf. FPGA dict.", "Conf. GUI dict.")


@pytest.fixture
def workspace():
    app = QApplication.instance() or QApplication([])
    outer = QTabWidget()
    sources = []
    writers = []
    for number, name in enumerate(SOURCE_NAMES):
        page = QWidget()
        layout = QVBoxLayout(page)
        writer = MagicMock(side_effect=lambda path, value: value)
        browser = RegisterBrowser(QTreeView(), lambda path, value: (True, "Writable"),
                                   writer, lambda: None, page)
        layout.addWidget(browser)
        browser.update_data({"gain": number + 1, "array": [1, 2, 3]})
        outer.addTab(page, name)
        sources.append((name, page, browser))
        writers.append(writer)
    circular, monitor = QWidget(), QWidget()
    outer.addTab(circular, "Circular")
    outer.addTab(monitor, "Monitor")
    controller = RegisterWorkspace(outer, sources)
    outer.resize(1000, 700)
    outer.show()
    app.processEvents()
    yield outer, controller, writers, circular, monitor
    outer.close()
    outer.deleteLater()
    app.processEvents()


def test_editor_hierarchy_preserves_three_sources_and_existing_tools(workspace):
    outer, controller, _, circular, monitor = workspace
    assert [outer.tabText(i) for i in range(outer.count())] == ["Registry editor", "Circular", "Monitor"]
    assert [controller.editor_tabs.tabText(i) for i in range(3)] == list(SOURCE_NAMES)
    assert outer.currentWidget() is controller.editor_page
    assert outer.widget(1) is circular and outer.widget(2) is monitor
    for number, (_, page, browser) in enumerate(controller.sources):
        assert controller.editor_tabs.widget(number) is page
        assert browser.model.rows[("gain",)][1].text() == str(number + 1)


def test_each_source_keeps_its_own_filter_and_writer(workspace):
    _, controller, writers, _, _ = workspace
    first, second = controller.sources[0][2], controller.sources[1][2]
    first.search.setText("gain")
    controller.editor_tabs.setCurrentIndex(1)
    second.search.setText("array")
    assert first.proxy.rowCount() == 1 and second.proxy.rowCount() == 1
    index = second.model.rows[("array", 1)][1].index()
    assert second.model.setData(index, "42")
    writers[1].assert_called_once_with(("array", 1), 42)
    writers[0].assert_not_called()
    writers[2].assert_not_called()
    controller.editor_tabs.setCurrentIndex(0)
    assert first.search.text() == "gain"
    assert first.model.rows[("gain",)][1].text() == "1"
