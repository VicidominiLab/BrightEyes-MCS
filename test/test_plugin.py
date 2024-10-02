import os
import sys
# insert root directory into python module search path
sys.path.insert(1, os.getcwd())


import unittest
from unittest.mock import MagicMock, patch
from PySide2.QtCore import Slot
from brighteyes_mcs.libs.plugin_loader import PluginsManager

class TestPluginsManager(unittest.TestCase):

    def setUp(self):
        self.main_window_mock = MagicMock()
        self.plugins_manager = PluginsManager(self.main_window_mock)

    def signal_emitted_calls_registered_functions(self):
        func_mock = MagicMock()
        self.plugins_manager.register_trigger("beforeRun", func_mock)
        self.plugins_manager.signal_emitted("beforeRun")
        func_mock.assert_called_once()

    def signal_emitted_with_args_calls_registered_functions_with_args(self):
        func_mock = MagicMock()
        self.plugins_manager.register_trigger("beforeRun", func_mock)
        self.plugins_manager.signal_emitted("beforeRun arg1 arg2")
        func_mock.assert_called_once_with("arg1arg2")

    def plugin_list_returns_correct_plugins(self):
        with patch('brighteyes_mcs.libs.plugin_loader.listdir', return_value=['plugin1', 'plugin2', '__init__']):
            with patch('brighteyes_mcs.libs.plugin_loader.isdir', return_value=True):
                plugins = self.plugins_manager.plugin_list()
                self.assertEqual(plugins, ['plugin1', 'plugin2'])

    def plugin_loader_loads_plugin_correctly(self):
        with patch('brighteyes_mcs.libs.plugin_loader.__import__') as import_mock:
            self.plugins_manager.plugin_loader('test_plugin')
            import_mock.assert_called_with('brighteyes_mcs.plugins.test_plugin.load_plugin')

    def addTab_adds_tab_to_main_window(self):
        widget_mock = MagicMock()
        self.plugins_manager.addTab(widget_mock, "Test Tab")
        self.main_window_mock.ui.tabWidget.addTab.assert_called_once_with(widget_mock, "Test Tab")

    def register_trigger_adds_function_to_trigger_register(self):
        func_mock = MagicMock()
        self.plugins_manager.register_trigger("afterStop", func_mock)
        self.assertIn("afterStop", self.plugins_manager.trigger_register)
        self.assertIn(func_mock, self.plugins_manager.trigger_register["afterStop"])

    def instances_returns_plugin_instances(self):
        self.plugins_manager.plugin_instances = {"plugin1_0": {}, "plugin2_0": {}}
        instances = self.plugins_manager.instances()
        self.assertEqual(instances, ["plugin1_0", "plugin2_0"])

if __name__ == '__main__':
    unittest.main()