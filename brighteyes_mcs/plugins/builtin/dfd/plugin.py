"""Plug-in entrypoint for the DFD preview widget."""

from .dfd_widget import DfdWidget
from ...api import PluginMetadata


PLUGIN = PluginMetadata(
    name="dfd",
    display_name="DFD Preview",
    description="Visualize and configure digital frequency-domain data.",
    allow_multiple=False,
)


def setup(context):
    widget = DfdWidget(context.main_window)

    context["widget"] = widget
    context["form"] = widget

    context.add_tab(widget, "DFD Preview")
    context.on("acquisitionDone", widget.after_acquisition)
    context.on("configurationLoaded", widget.UpdateTable)
    return widget
