"""Plug-in entrypoint for the channel delay skew editor."""

from .channel_delay_skew_widget import ChannelDelaySkewWidget


def load_plugin(plugin_manager=None, context=None):
    if context is None:
        context = {}

    widget = ChannelDelaySkewWidget(main_window=plugin_manager.main_window)

    context["widget"] = widget
    context["form"] = widget

    plugin_manager.addTab(widget, "Channel Delay Skew")
    print("channel_delay_skew loaded", context)
    #plugin_manager.register_trigger("beforeRun", lambda: mycmd(context))
    plugin_manager.register_trigger("acquisitionDone", widget.acquisitionDone)
