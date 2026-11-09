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
    window = context.main_window
    config_file = window.plugin_configuration_files.setdefault("DAC_ino", "cfg/plugins_cfg/DAC_ino.cfg")
    if "DAC_ino" not in window.plugin_configuration:
        window._load_plugin_config_file("DAC_ino", config_file)
    context["form"].bind_configuration(window)
    context.on("configurationLoaded", context["form"].apply_configuration)
    context.on_run(context["form"].before_run, context["form"].after_run)
    context.add_tab(context["widget"], "DAC_ino")
    return context["widget"]
