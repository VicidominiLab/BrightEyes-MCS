"""Discovery, loading, and event dispatch for isolated plug-ins."""

from __future__ import annotations

from collections import defaultdict
import hashlib
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from typing import Callable

from PySide6.QtCore import Slot

from ..application.paths import profile_directory, resource_path
from brighteyes_mcs.logging_setup import logger
from ..plugins.api import PluginContext, PluginMetadata


BUILTIN_PLUGIN_PACKAGE = "brighteyes_mcs.plugins.builtin"


class PluginLoadError(RuntimeError):
    """Raised when a plug-in does not satisfy the entrypoint contract."""


class PluginManager:
    """Load independent plug-in instances and dispatch application events."""

    def __init__(
        self,
        main_window,
        plugin_directory: Path | None = None,
        user_plugin_directory: Path | None = None,
    ):
        self.main_window = main_window
        self.plugin_directory = Path(
            plugin_directory or resource_path("plugins/builtin")
        )
        self._user_plugin_directory = (
            None
            if user_plugin_directory is None
            else Path(user_plugin_directory)
        )
        self.instances: dict[str, dict] = {}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self.main_window.plugin_signals.signal.connect(self.emit)

    def available_plugins(self) -> list[str]:
        """Return plug-ins from the package and active user profile.

        A user plug-in with the same directory name as a bundled plug-in
        overrides the bundled implementation.
        """

        names = self._plugins_in(self.plugin_directory)
        names.update(self._plugins_in(self.user_plugin_directory))
        return sorted(names)

    @property
    def user_plugin_directory(self) -> Path:
        """Return the configured or currently active profile plug-ins folder."""

        if self._user_plugin_directory is not None:
            return self._user_plugin_directory
        return profile_directory("plugin_packages")

    def load(self, plugin_name: str) -> str:
        """Create one plug-in instance and return its unique instance id."""

        if not plugin_name.isidentifier() or plugin_name.startswith("_"):
            raise PluginLoadError(f"Invalid plug-in name: {plugin_name!r}")

        module, module_name = self._load_plugin_module(plugin_name)
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

    @staticmethod
    def _plugins_in(directory: Path) -> set[str]:
        if not directory.is_dir():
            return set()
        return {
            child.name
            for child in directory.iterdir()
            if child.is_dir()
            and child.name.isidentifier()
            and not child.name.startswith("_")
            and (child / "plugin.py").is_file()
        }

    def _load_plugin_module(self, plugin_name: str):
        user_entrypoint = self.user_plugin_directory / plugin_name / "plugin.py"
        if user_entrypoint.is_file():
            module_name = self._user_module_name(plugin_name, user_entrypoint)
            cached = sys.modules.get(module_name)
            if cached is not None:
                return cached, module_name

            # Treat plugin.py as the root of an isolated package. This lets a
            # profile plug-in use local imports such as ``from .widget import``
            # without adding the user directory to global sys.path.
            spec = spec_from_file_location(
                module_name,
                user_entrypoint,
                submodule_search_locations=[str(user_entrypoint.parent)],
            )
            if spec is None or spec.loader is None:
                raise PluginLoadError(
                    f"Could not create an import specification for {user_entrypoint}"
                )
            module = module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(module_name, None)
                raise
            return module, module_name

        module_name = f"{BUILTIN_PLUGIN_PACKAGE}.{plugin_name}.plugin"
        return import_module(module_name), module_name

    @staticmethod
    def _user_module_name(plugin_name: str, entrypoint: Path) -> str:
        location = str(entrypoint.resolve()).encode("utf-8")
        digest = hashlib.sha256(location).hexdigest()[:12]
        return f"_brighteyes_mcs_user_plugin_{digest}_{plugin_name}"

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
        add_central_tab = getattr(self.main_window, "addCentralTab", None)
        if callable(add_central_tab):
            return add_central_tab(widget, caption)
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
