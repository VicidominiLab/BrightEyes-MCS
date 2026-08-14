
"""Interactive script-launcher plug-in."""

from .plugin_form import myForm
from PySide6.QtWidgets import QWidget
from brighteyes_mcs.plugins.api import PluginMetadata
from brighteyes_mcs.logging_setup import logger


PLUGIN = PluginMetadata(
    name="script_launcher",
    display_name="Script Launcher",
    description="Run interactive scripts against the active application.",
    allow_multiple=False,
)


def setup(context):
    widget = QWidget()
    form = myForm()

    context["widget"] = widget
    context["form"] = form

    form.setupUi(widget)
    form.console = context.main_window.console_widget
    form.gridLayout_placeholder.addWidget(form.console)
    # plugin_manager.main_window.ui.gridLayout_Terminal.remove()

    idx = context.main_window.ui.tabWidget.indexOf(
        context.main_window.ui.tab_terminal
    )
    context.main_window.ui.tabWidget.removeTab(idx)

    context.add_tab(widget, "ScriptLauncher")
    context.on("acquisitionDone", form.after_acquisition)
    context.on("configurationLoaded", form.refresh_scripts)

    logger.debug("%s %s", "script_launcher loaded", context)
    return widget
