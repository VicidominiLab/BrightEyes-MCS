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
    context.on_run(before_run, after_run)
    return None


def before_run(mode):
    """Prepare hardware for 'preview' or 'acquisition'; raise to abort startup.

    Return only after confirmation. Use bounded waits that process Qt serial
    events when necessary. This runs once per continuous preview session.
    """


def after_run(mode):
    """Restore idle hardware on completion, Stop, or partial startup failure."""
