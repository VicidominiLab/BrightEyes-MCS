"""Cobolt laser lifecycle plug-in."""

from .cobolt_ctl import turn_on_laser, turn_off_laser
from brighteyes_mcs.plugins.api import PluginMetadata


PLUGIN = PluginMetadata(
    name="ao_system",
    display_name="AO Laser System",
    description="Control the Cobolt laser around acquisition runs.",
    allow_multiple=False,
)

def mycmd(context, s=None):
    turn_on_laser(context["port"], context["power"])


def setup(context):
    context["port"] = "COM3"
    context["power"] = 0.002
    context.on("beforeRun", lambda: mycmd(context))
