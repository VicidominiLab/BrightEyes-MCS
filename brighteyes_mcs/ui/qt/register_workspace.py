"""Group the three register editors without replacing their source pages."""

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget


class RegisterWorkspace:
    def __init__(self, outer_tabs, sources):
        self.outer_tabs = outer_tabs
        self.sources = sources
        self.editor_page = QWidget(outer_tabs)
        self.editor_tabs = QTabWidget(self.editor_page)
        editor_layout = QVBoxLayout(self.editor_page)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.editor_tabs)
        for name, page, _ in sources:
            outer_tabs.removeTab(outer_tabs.indexOf(page))
            self.editor_tabs.addTab(page, name)
        outer_tabs.insertTab(0, self.editor_page, "Registry editor")
        outer_tabs.setCurrentWidget(self.editor_page)
