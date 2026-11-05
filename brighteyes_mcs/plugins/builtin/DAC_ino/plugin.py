"""Four-channel Arduino DAC tab, following the myplugin entrypoint."""

from PySide6.QtWidgets import QWidget

from brighteyes_mcs.plugins.api import PluginMetadata
from .plugin_form import myForm


PLUGIN = PluginMetadata(
    name="DAC_ino",
    display_name="Arduino DAC",
    description="Control four 0–5 V DAC outputs over a USB-to-TTL converter.",
    allow_multiple=False,
)


def setup(context):
    context["widget"] = QWidget()
    context["form"] = myForm()
    context["form"].setupUi(context["widget"])
    context.add_tab(context["widget"], "DAC_ino")
    return context["widget"]
