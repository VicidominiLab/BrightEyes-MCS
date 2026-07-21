"""Discovery, loading, and event dispatch for isolated plug-ins."""

from __future__ import annotations

from collections import defaultdict
from importlib import import_module
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Slot

from ..application.paths import resource_path
from brighteyes_mcs.logging_setup import logger
from ..plugins.api import PluginContext, PluginMetadata


BUILTIN_PLUGIN_PACKAGE = "brighteyes_mcs.plugins.builtin"


class PluginLoadError(RuntimeError):
    """Raised when a plug-in does not satisfy the entrypoint contract."""


class PluginManager:
    """Load independent plug-in instances and dispatch application events."""

    def __init__(self, main_window, plugin_directory: Path | None = None):
        self.main_window = main_window
        self.plugin_directory = Path(
            plugin_directory or resource_path("plugins/builtin")
        )
        self.instances: dict[str, dict] = {}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self.main_window.plugin_signals.signal.connect(self.emit)

    def available_plugins(self) -> list[str]:
        """Return sorted plug-in packages containing a ``plugin.py`` entrypoint."""

        if not self.plugin_directory.exists():
            return []
        return sorted(
            child.name
            for child in self.plugin_directory.iterdir()
            if child.is_dir()
            and not child.name.startswith("_")
            and (child / "plugin.py").is_file()
        )

    def load(self, plugin_name: str) -> str:
        """Create one plug-in instance and return its unique instance id."""

        if not plugin_name.isidentifier() or plugin_name.startswith("_"):
            raise PluginLoadError(f"Invalid plug-in name: {plugin_name!r}")

        module_name = f"{BUILTIN_PLUGIN_PACKAGE}.{plugin_name}.plugin"
        module = import_module(module_name)
        setup = getattr(module, "setup", None)
        if not callable(setup):
            raise PluginLoadError(f"{module_name} must define setup(context)")

        metadata = getattr(
            module,
            "PLUGIN",
            PluginMetadata(plugin_name, plugin_name.replace("_", " ").title()),
        )
        if not isinstance(metadata, PluginMetadata):
            raise PluginLoadError(f"{module_name}.PLUGIN must be PluginMetadata")
        if not metadata.allow_multiple and self.is_loaded(plugin_name):
            raise PluginLoadError(f"Plug-in {plugin_name!r} allows only one instance")

        instance_id = self._next_instance_id(plugin_name)
        state: dict = {"metadata": metadata}
        self.instances[instance_id] = state
        context = PluginContext(self, state, services=self._services())

        try:
            plugin_object = setup(context)
        except Exception:
            del self.instances[instance_id]
            raise

        if plugin_object is not None:
            state["plugin"] = plugin_object
        logger.debug("%s %s %s %s", "loaded plugin", plugin_name, "as", instance_id)
        return instance_id

    def load_once(self, plugin_name: str) -> str:
        """Return the existing instance id, or load the plug-in once."""

        existing = self.instance_ids(plugin_name)
        return existing[0] if existing else self.load(plugin_name)

    def is_loaded(self, plugin_name: str) -> bool:
        return bool(self.instance_ids(plugin_name))

    def instance_ids(self, plugin_name: str | None = None) -> list[str]:
        if plugin_name is None:
            return list(self.instances)
        prefix = f"{plugin_name}_"
        return [name for name in self.instances if name.startswith(prefix)]

    def add_tab(self, widget, caption: str):
        return self.main_window.ui.tabWidget.addTab(widget, caption)

    def on(self, event: str, callback: Callable):
        callbacks = self._callbacks[event]
        if callback not in callbacks:
            callbacks.append(callback)
        return callback

    @Slot(str)
    def emit(self, message: str) -> None:
        """Dispatch ``event`` or ``event payload`` messages from the Qt signal."""

        event, separator, payload = message.partition(" ")
        for callback in tuple(self._callbacks.get(event, ())):
            if separator:
                callback(payload)
            else:
                callback()

    def _next_instance_id(self, plugin_name: str) -> str:
        index = 0
        while f"{plugin_name}_{index}" in self.instances:
            index += 1
        return f"{plugin_name}_{index}"

    def _services(self) -> dict:
        return {
            "acquisition": getattr(self.main_window, "mcs_manager", None),
            "configuration": getattr(
                self.main_window, "configuration_controller", None
            ),
        }


__all__ = ["PluginLoadError", "PluginManager"]
