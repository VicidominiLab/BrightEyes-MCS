import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from brighteyes_mcs.application.plugin_service import PluginManager
from brighteyes_mcs.plugins.api import PluginMetadata


class TestPluginManager(unittest.TestCase):
    def setUp(self):
        self.main_window = MagicMock()
        self.manager = PluginManager(self.main_window)

    def test_emit_calls_registered_callback(self):
        callback = MagicMock()
        self.manager.on("beforeRun", callback)

        self.manager.emit("beforeRun")

        callback.assert_called_once_with()

    def test_emit_preserves_event_payload(self):
        callback = MagicMock()
        self.manager.on("beforeRun", callback)

        self.manager.emit("beforeRun arg1 arg2")

        callback.assert_called_once_with("arg1 arg2")

    def test_available_plugins_only_returns_valid_entrypoint_packages(self):
        plugins = self.manager.available_plugins()

        self.assertIn("dfd", plugins)
        self.assertIn("channel_delay_skew", plugins)
        self.assertNotIn("__pycache__", plugins)

    def test_load_calls_single_context_entrypoint(self):
        setup = MagicMock(return_value="plugin-object")
        module = SimpleNamespace(
            PLUGIN=PluginMetadata("test_plugin", "Test Plugin"),
            setup=setup,
        )
        with patch(
            "brighteyes_mcs.application.plugin_service.import_module",
            return_value=module,
        ) as importer:
            instance_id = self.manager.load("test_plugin")

        importer.assert_called_once_with(
            "brighteyes_mcs.plugins.builtin.test_plugin.plugin"
        )
        setup.assert_called_once()
        self.assertEqual(instance_id, "test_plugin_0")
        self.assertEqual(self.manager.instances[instance_id]["plugin"], "plugin-object")

    def test_add_tab_delegates_to_main_window(self):
        widget = MagicMock()
        self.main_window.addCentralTab = MagicMock(return_value=7)

        result = self.manager.add_tab(widget, "Test Tab")

        self.main_window.addCentralTab.assert_called_once_with(widget, "Test Tab")
        self.assertEqual(result, 7)

    def test_load_once_reuses_existing_instance(self):
        self.manager.instances["plugin_0"] = {}

        self.assertEqual(self.manager.load_once("plugin"), "plugin_0")


if __name__ == "__main__":
    unittest.main()
