"""Small, stable surface available to plug-in implementations."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from typing import Any, Callable


PLUGIN_API_VERSION = "2.0"
PluginCallback = Callable[..., Any]


@dataclass(frozen=True)
class PluginMetadata:
    """Human-facing information declared by a plug-in module."""

    name: str
    display_name: str
    description: str = ""
    allow_multiple: bool = True


class PluginContext(MutableMapping[str, Any]):
    """Services and per-instance state supplied to ``setup(context)``."""

    def __init__(self, manager, state=None, services=None):
        self._manager = manager
        self._state = {} if state is None else state
        self._services = {} if services is None else dict(services)

    @property
    def api_version(self) -> str:
        return PLUGIN_API_VERSION

    @property
    def main_window(self):
        """Qt window escape hatch for plug-ins that genuinely need it."""

        return self._manager.main_window

    def service(self, name: str, default=None):
        """Return an application service by name."""

        return self._services.get(name, default)

    def add_tab(self, widget, caption: str):
        return self._manager.add_tab(widget, caption)

    def on(self, event: str, callback: PluginCallback):
        """Run ``callback`` whenever the named application event is emitted."""

        return self._manager.on(event, callback)

    def __getitem__(self, key: str) -> Any:
        return self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._state[key] = value

    def __delitem__(self, key: str) -> None:
        del self._state[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._state)

    def __len__(self) -> int:
        return len(self._state)


__all__ = ["PLUGIN_API_VERSION", "PluginContext", "PluginMetadata"]
