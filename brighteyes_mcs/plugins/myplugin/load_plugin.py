from .plugin_form import myForm
from PySide2.QtWidgets import QWidget


def load_plugin(plugin_manager=None, context={}):
    context["widget"] = QWidget()
    context["form"] = myForm()

    context["form"].setupUi(context["widget"])

    plugin_manager.addTab(context["widget"], "myplugin")
    print("myplugin loaded", context)
