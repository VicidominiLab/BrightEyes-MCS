
"""Plug-in entrypoint for the channel delay skew editor."""

from .channel_delay_skew_widget import ChannelDelaySkewWidget
from brighteyes_mcs.plugins.api import PluginMetadata
from brighteyes_mcs.logging_setup import logger


PLUGIN = PluginMetadata(
    name="channel_delay_skew",
    display_name="Channel Delay Skew",
    description="Edit and inspect per-channel timing corrections.",
    allow_multiple=False,
)


def setup(context):
    widget = ChannelDelaySkewWidget(main_window=context.main_window)

    context["widget"] = widget
    context["form"] = widget

    context.add_tab(widget, "Channel Delay Skew")
    logger.debug("%s %s", "channel_delay_skew loaded", context)
    context.on("acquisitionDone", widget.acquisitionDone)
    context.on("configurationLoaded", widget.UpdateTable)
    return widget
