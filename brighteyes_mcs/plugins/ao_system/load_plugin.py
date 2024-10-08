"""
The load_plugin.py is the default loader of the plugin that can be modified in order to implement the plugin.
Remind to add from .load_plugin import load_plugin in the __init__.py
"""

from .cobolt_ctl import turn_on_laser, turn_off_laser

def mycmd(context, s=None):
    turn_on_laser(context["port"], context["power"])


def load_plugin(plugin_manager=None, context={}):
    context["port"] = "COM3"
    context["power"] = 0.002
    print(context)
    plugin_manager.register_trigger("beforeRun", lambda: mycmd(context))
