"""Small Qt types used by the main window wiring."""

import pyqtgraph as pg
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QStyle, QStyleOptionComboBox, QStylePainter


class ElidedComboBox(QComboBox):
    """Keep full item values while shortening the closed selector's display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentTextChanged.connect(self.setToolTip)

    def paintEvent(self, event):
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.CC_ComboBox, option)
        rect = self.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, self)
        option.currentText = self.fontMetrics().elidedText(option.currentText, Qt.ElideRight, rect.width())
        painter.drawControl(QStyle.CE_ComboBoxLabel, option)


class DoubleClickDoubleSpinBox(QDoubleSpinBox):
    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        event.accept()


class RectROIWithoutHandles(pg.RectROI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for handle in self.getHandles():
            self.removeHandle(handle)


class PluginSignals(QObject):
    signal = Signal(str)


__all__ = ["DoubleClickDoubleSpinBox", "ElidedComboBox", "PluginSignals", "RectROIWithoutHandles"]
