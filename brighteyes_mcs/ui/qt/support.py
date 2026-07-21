"""Small Qt types used by the main window wiring."""

import pyqtgraph as pg
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDoubleSpinBox


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


__all__ = ["DoubleClickDoubleSpinBox", "PluginSignals", "RectROIWithoutHandles"]
