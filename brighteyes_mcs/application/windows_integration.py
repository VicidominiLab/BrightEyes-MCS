"""Per-user Windows shortcuts for a pip-installed BrightEyes-MCS environment."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

from .paths import resource_path


STATE_SCHEMA = 1
SHORTCUT_NAME = "BrightEyes-MCS.lnk"


def integration_dir() -> Path:
    """Return the per-user directory for shortcut state and persistent assets."""

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "BrightEyes-MCS" / "integration"
    return Path.home() / ".local" / "share" / "BrightEyes-MCS" / "integration"


def state_path() -> Path:
    return integration_dir() / "shortcuts.json"


def environment_key(prefix: str | Path | None = None) -> str:
    """Return a stable identifier for one Python or virtual environment."""

    environment = Path(sys.prefix if prefix is None else prefix).resolve()
    normalized = os.path.normcase(str(environment))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def _read_state() -> dict[str, Any]:
    path = state_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"schema": STATE_SCHEMA, "environments": {}}
    if payload.get("schema") != STATE_SCHEMA or not isinstance(payload.get("environments"), dict):
        return {"schema": STATE_SCHEMA, "environments": {}}
    return payload


def _write_state(payload: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def setup_was_handled(prefix: str | Path | None = None) -> bool:
    record = _read_state()["environments"].get(environment_key(prefix), {})
    return bool(record.get("handled"))


def mark_setup_handled(
    *,
    desktop: bool,
    prefix: str | Path | None = None,
) -> None:
    environment = Path(sys.prefix if prefix is None else prefix).resolve()
    payload = _read_state()
    payload["environments"][environment_key(environment)] = {
        "prefix": str(environment),
        "handled": True,
        "desktop": bool(desktop),
    }
    _write_state(payload)


def pythonw_executable(executable: str | Path | None = None) -> Path:
    """Find pythonw.exe beside the interpreter running this environment."""

    python = Path(sys.executable if executable is None else executable).absolute()
    if python.name.casefold() == "pythonw.exe":
        return python
    candidate = python.with_name("pythonw.exe")
    if not candidate.is_file():
        raise FileNotFoundError(f"pythonw.exe was not found beside {python}.")
    return candidate


def persistent_icon() -> Path:
    """Copy the packaged icon to a path that survives package upgrades."""

    source = resource_path("images/icon.ico")
    destination = integration_dir() / "BrightEyes-MCS.ico"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or source.read_bytes() != destination.read_bytes():
        shutil.copy2(source, destination)
    return destination


def _windows_shell():
    from win32com.client import Dispatch

    return Dispatch("WScript.Shell")


def _save_shortcut(
    shell,
    link_path: Path,
    *,
    launcher: Path,
    icon: Path,
) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    shortcut = shell.CreateShortcut(str(link_path))
    shortcut.TargetPath = str(launcher)
    shortcut.Arguments = "-m brighteyes_mcs"
    shortcut.WorkingDirectory = str(integration_dir())
    shortcut.IconLocation = f"{icon},0"
    shortcut.Description = "BrightEyes-MCS microscope control software"
    shortcut.Save()


def create_desktop_shortcut(
    *,
    executable: str | Path | None = None,
    shell=None,
) -> Path:
    """Create a Desktop shortcut to ``pythonw.exe -m brighteyes_mcs``."""

    if os.name != "nt":
        raise OSError("BrightEyes-MCS shortcuts are supported only on Windows.")

    shell = _windows_shell() if shell is None else shell
    launcher = pythonw_executable(executable)
    icon = persistent_icon()
    link = Path(shell.SpecialFolders("Desktop")) / SHORTCUT_NAME
    _save_shortcut(shell, link, launcher=launcher, icon=icon)
    return link


def remove_desktop_shortcut(*, shell=None) -> bool:
    """Remove the current user's BrightEyes-MCS Desktop shortcut if present."""

    if os.name != "nt":
        return False
    shell = _windows_shell() if shell is None else shell
    link = Path(shell.SpecialFolders("Desktop")) / SHORTCUT_NAME
    if not link.exists():
        return False
    link.unlink()
    return True


__all__ = [
    "create_desktop_shortcut",
    "environment_key",
    "integration_dir",
    "mark_setup_handled",
    "pythonw_executable",
    "remove_desktop_shortcut",
    "setup_was_handled",
]
