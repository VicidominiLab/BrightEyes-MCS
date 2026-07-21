"""Minimal Qt tab plug-in example."""

from .plugin_form import myForm
from PySide6.QtWidgets import QWidget
from ...api import PluginMetadata


PLUGIN = PluginMetadata(
    name="myplugin",
    display_name="Example Plugin",
    description="Minimal example showing how to add a Qt tab.",
)


def setup(context):
    context["widget"] = QWidget()
    context["form"] = myForm()

    context["form"].setupUi(context["widget"])

    context.add_tab(context["widget"], "myplugin")
    return context["widget"]
