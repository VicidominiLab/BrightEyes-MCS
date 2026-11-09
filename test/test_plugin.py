import unittest
from pathlib import Path
import sys
import tempfile
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

    def test_run_hooks_pair_in_reverse_order_and_finish_once(self):
        calls = []
        for name in ("a", "b"):
            self.manager.on_run(
                lambda mode, n=name: calls.append((n, "before", mode)),
                lambda mode, n=name: calls.append((n, "after", mode)),
            )
        self.manager.prepare_run(True)
        self.manager.finish_run()
        self.manager.finish_run()
        self.assertEqual(calls, [
            ("a", "before", "preview"), ("b", "before", "preview"),
            ("b", "after", "preview"), ("a", "after", "preview"),
        ])

    def test_failed_before_rolls_back_partial_setup_and_other_plugins(self):
        calls = []
        self.manager.on_run(lambda mode: None, lambda mode: calls.append("a"))

        def fail(mode):
            raise RuntimeError("setup failed")

        self.manager.on_run(fail, lambda mode: calls.append("b"))
        self.manager.on_run(lambda mode: calls.append("never"), lambda mode: None)
        with self.assertRaisesRegex(RuntimeError, "setup failed"):
            self.manager.prepare_run()
        self.assertEqual(calls, ["b", "a"])
        self.assertIsNone(self.manager._run_mode)

    def test_stop_during_setup_cancels_and_cleans_up(self):
        after = MagicMock()
        self.manager.on_run(lambda mode: self.manager.cancel_run_preparation(), after)
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            self.manager.prepare_run()
        after.assert_called_once_with("acquisition")

    def test_cleanup_failure_does_not_skip_other_plugins(self):
        after = MagicMock()
        self.manager.on_run(lambda mode: None, after)
        self.manager.on_run(lambda mode: None, MagicMock(side_effect=RuntimeError("DAC offline")))
        self.manager.prepare_run()
        self.manager.finish_run()
        after.assert_called_once_with("acquisition")

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

    def test_user_plugins_are_discovered_and_support_local_imports(self):
        with tempfile.TemporaryDirectory() as temporary:
            user_plugins = Path(temporary) / "plugins"
            plugin = user_plugins / "external_example"
            plugin.mkdir(parents=True)
            (plugin / "helper.py").write_text("VALUE = 42\n", encoding="utf-8")
            entrypoint = plugin / "plugin.py"
            entrypoint.write_text(
                "from brighteyes_mcs.plugins.api import PluginMetadata\n"
                "from .helper import VALUE\n\n"
                "PLUGIN = PluginMetadata(\n"
                "    name='external_example',\n"
                "    display_name='External Example',\n"
                "    allow_multiple=False,\n"
                ")\n\n"
                "def setup(context):\n"
                "    context['value'] = VALUE\n",
                encoding="utf-8",
            )
            manager = PluginManager(
                self.main_window,
                user_plugin_directory=user_plugins,
            )

            plugins = manager.available_plugins()
            self.assertIn("external_example", plugins)
            self.assertIn("script_launcher", plugins)

            instance_id = manager.load("external_example")
            self.assertEqual(manager.instances[instance_id]["value"], 42)

            module_name = manager._user_module_name("external_example", entrypoint)
            sys.modules.pop(module_name + ".helper", None)
            sys.modules.pop(module_name, None)

    def test_user_plugin_overrides_bundled_plugin_with_the_same_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            user_plugins = Path(temporary) / "plugins"
            plugin = user_plugins / "script_launcher"
            plugin.mkdir(parents=True)
            entrypoint = plugin / "plugin.py"
            entrypoint.write_text(
                "from brighteyes_mcs.plugins.api import PluginMetadata\n\n"
                "PLUGIN = PluginMetadata(\n"
                "    name='script_launcher',\n"
                "    display_name='Profile Script Launcher',\n"
                ")\n\n"
                "def setup(context):\n"
                "    context['source'] = 'profile'\n",
                encoding="utf-8",
            )
            manager = PluginManager(
                self.main_window,
                user_plugin_directory=user_plugins,
            )

            instance_id = manager.load("script_launcher")

            self.assertEqual(manager.instances[instance_id]["source"], "profile")
            module_name = manager._user_module_name("script_launcher", entrypoint)
            sys.modules.pop(module_name, None)

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
