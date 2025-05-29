from .print_dec import print_dec
from os import listdir
from os.path import isfile, join, isdir
from PySide6.QtCore import Slot


class PluginsManager:
    """
    Manages the plugins for the main window application.

    Attributes:
        main_window (QMainWindow): The main window of the application.
        plugin_instances (dict): Dictionary to store plugin instances.
        trigger_register (dict): Dictionary to store registered triggers.
    """

    def __init__(self, main_window):
        """
        Initialize the PluginsManager.

        Args:
            main_window (QMainWindow): The main window of the application.
        """
        self.main_window = main_window
        self.plugin_instances = {}
        self.main_window.plugin_signals.signal.connect(self.signal_emitted)
        self.trigger_register = {}

    @Slot()
    def signal_emitted(self, string):
        """
        Slot to handle emitted signals.

        Args:
            string (str): The emitted signal string.
        """
        print("call", string)
        print(self.trigger_register)
        string_splitted = string.split(" ")
        if len(string_splitted) > 0:
            trigger_name = string_splitted[0]
            str_args = None
            if len(string_splitted) > 1:
                str_args = "".join(string_splitted[1:])

            if trigger_name in self.trigger_register:
                for i in self.trigger_register[trigger_name]:
                    func = i
                    print("try to call ", i, " func:", func)
                    if str_args is not None:
                        func(str_args)
                    else:
                        func()

    def plugin_list(self):
        """
        Get the list of available plugins.

        Returns:
            list: List of available plugins.
        """
        mypath = "plugins/"
        l = [f for f in listdir(mypath) if isdir(join(mypath, f))]
        list_dir = []
        for i in l:
            if not i.startswith("__"):
                list_dir.append(i)
        return list_dir

    def plugin_loader(self, plugin_name):
        """
        Load a plugin by name.

        Args:
            plugin_name (str): The name of the plugin to load.
        """
        n = 0
        while plugin_name + "_%d" % n in self.plugin_instances:
            n = n + 1
        plugin_instance_name = plugin_name + "_%d" % n

        print_dec(plugin_name, " instance: ", plugin_instance_name)

        self.plugin_instances.update({plugin_instance_name: {}})

        m = __import__("brighteyes_mcs.plugins." + plugin_name + ".load_plugin")
        loader = getattr(getattr(getattr(m, "plugins"), plugin_name), "load_plugin")
        print_dec(
            "loading plugin: brighteyes_mcs.plugins." + plugin_name + ".load_plugin"
        )
        loader(self, self.plugin_instances[plugin_instance_name])
        print_dec(
            "loaded plugin: brighteyes_mcs.plugins." + plugin_name + ".load_plugin()"
        )

    def instances(self):
        """
        Get the instances of loaded plugins.

        Returns:
            dict: Dictionary of plugin instances.
        """
        return list(self.plugin_instances)

    def addTab(self, widget, caption):
        """
        Add a tab to the main window.

        Args:
            widget (QWidget): The widget to add as a tab.
            caption (str): The caption for the tab.
        """
        self.main_window.ui.tabWidget.addTab(widget, caption)

    def register_trigger(self, trigger_name, func):
        """
        Register a trigger with a function.

        Args:
            trigger_name (str): The name of the trigger.
            func (callable): The function to call when the trigger is emitted.
        """

        # self.main_window.plugin_signals.signal_beforeRun.co
        # self.main_window.plugin_signals.signal_justbeforeRun
        # self.main_window.plugin_signals.signal_afterStop
        # self.main_window.plugin_signals.signal_afterFinalize
        if trigger_name in self.trigger_register:
            self.trigger_register[trigger_name].append(func)
        else:
            self.trigger_register[trigger_name] = [func]

        print(self.trigger_register)
