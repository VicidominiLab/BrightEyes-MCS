"""Minimal plug-in template."""

from brighteyes_mcs.plugins.api import PluginMetadata


PLUGIN = PluginMetadata(
    name="example",
    display_name="Example",
    description="Describe the capability shown to users.",
    allow_multiple=True,
)


def setup(context):
    """Create one plug-in instance and optionally return its main object."""

    context["started"] = True
    return None
