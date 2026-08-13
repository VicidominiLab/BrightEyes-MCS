"""Compatibility cleanup for PyQtGraph objects during Qt shutdown."""

from __future__ import annotations


def disable_viewbox_item_change_callbacks() -> int:
    """Prevent PyQtGraph ViewBoxes from auto-ranging while Qt deletes scenes.

    PySide may delete plot children before their parent ViewBox. PyQtGraph's
    ChildGroup callback otherwise asks the ViewBox to inspect a child whose C++
    object is already gone, producing an exception from ``__moduleShutdown``.
    This is called only during final application shutdown.
    """

    import pyqtgraph as pg

    disabled = 0
    for view_box in list(pg.ViewBox.AllViews):
        try:
            view_box.childGroup.itemsChangedListeners = ()
        except (AttributeError, RuntimeError):
            continue
        disabled += 1
    return disabled


__all__ = ["disable_viewbox_item_change_callbacks"]
