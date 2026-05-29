"""Plug-in entrypoint for the DFD preview widget."""

from .dfd_widget import DfdWidget


def load_plugin(plugin_manager=None, context=None):
    if context is None:
        context = {}

    widget = DfdWidget(plugin_manager.main_window)

    context["widget"] = widget
    context["form"] = widget

    plugin_manager.addTab(widget, "DFD Preview")
    plugin_manager.register_trigger("acquisitionDone", widget.after_acquisition)
    plugin_manager.register_trigger("configurationLoaded", widget.UpdateTable)

    print("dfd loaded", context)
