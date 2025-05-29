"""
The load_plugin.py is the default loader of the plugin that can be modified in order to implement the plugin.
Remind to add from .load_plugin import load_plugin in the __init__.py
The parameter plugin_manager allows to QWidget to the plugins
plugin_manager.addTab(context["widget"], "myplugin")
"""

from .plugin_form import myForm
from PySide6.QtWidgets import QWidget


def load_plugin(plugin_manager=None, context={}):
    context["widget"] = QWidget()
    context["form"] = myForm()

    context["form"].setupUi(context["widget"])

    plugin_manager.addTab(context["widget"], "myplugin")
    print("myplugin loaded", context)
