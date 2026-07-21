import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from brighteyes_mcs.plugins.api import (
    PLUGIN_API_VERSION,
    PluginContext,
    PluginMetadata,
)


class TestPluginContext(unittest.TestCase):
    def test_context_exposes_state_services_tabs_and_events(self):
        manager = SimpleNamespace(
            main_window=object(), add_tab=MagicMock(), on=MagicMock()
        )
        state = {}
        acquisition = object()
        context = PluginContext(
            manager, state, services={"acquisition": acquisition}
        )

        context["widget"] = "widget"
        context.add_tab("widget", "Plugin")
        context.on("done", len)

        self.assertEqual(context.api_version, PLUGIN_API_VERSION)
        self.assertEqual(state["widget"], "widget")
        self.assertIs(context.service("acquisition"), acquisition)
        manager.add_tab.assert_called_once_with("widget", "Plugin")
        manager.on.assert_called_once_with("done", len)

    def test_metadata_has_readable_defaults(self):
        metadata = PluginMetadata("example", "Example")

        self.assertEqual(metadata.description, "")
        self.assertTrue(metadata.allow_multiple)


if __name__ == "__main__":
    unittest.main()
