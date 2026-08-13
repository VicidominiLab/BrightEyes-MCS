from types import SimpleNamespace
from unittest.mock import patch

from brighteyes_mcs.ui.qt.graphics_shutdown import disable_viewbox_item_change_callbacks


def test_shutdown_disables_viewbox_child_change_callbacks():
    first = SimpleNamespace(
        childGroup=SimpleNamespace(itemsChangedListeners=(object(),))
    )
    second = SimpleNamespace(
        childGroup=SimpleNamespace(itemsChangedListeners=(object(), object()))
    )
    pyqtgraph = SimpleNamespace(ViewBox=SimpleNamespace(AllViews=[first, second]))

    with patch.dict("sys.modules", {"pyqtgraph": pyqtgraph}):
        assert disable_viewbox_item_change_callbacks() == 2

    assert first.childGroup.itemsChangedListeners == ()
    assert second.childGroup.itemsChangedListeners == ()
