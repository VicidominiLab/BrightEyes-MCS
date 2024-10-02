
"""
The load_plugin.py is the default loader of the plugin that can be modified in order to implement the plugin.
Remind to add from .load_plugin import load_plugin in the __init__.py
The parameter plugin_manager allows to QWidget to the plugins
plugin_manager.addTab(context["widget"], "myplugin")
"""

from .plugin_form import myForm
from PySide2.QtWidgets import QWidget

def load_plugin(plugin_manager=None, context={}):
    widget = QWidget()
    form = myForm()

    context["widget"] = widget
    context["form"] = form

    form.setupUi(widget)
    form.console = plugin_manager.main_window.console_widget
    form.gridLayout_placeholder.addWidget(form.console)
    # plugin_manager.main_window.ui.gridLayout_Terminal.remove()

    idx = plugin_manager.main_window.ui.tabWidget.indexOf(
        plugin_manager.main_window.ui.tab_terminal
    )
    plugin_manager.main_window.ui.tabWidget.removeTab(idx)

    plugin_manager.addTab(widget, "ScriptLauncher")
    plugin_manager.register_trigger("acquisitionDone", form.after_acquisition)

    print("script_launcher loaded", context)
