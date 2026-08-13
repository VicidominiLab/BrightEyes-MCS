"""Per-user Windows shortcuts for a pip-installed BrightEyes-MCS environment."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

from .paths import resource_path, system_root as active_system_root


STATE_SCHEMA = 1
SHORTCUT_NAME = "BrightEyes-MCS.lnk"
PYTHON_SHORTCUT_NAME = "BrightEyes-MCS Python.lnk"
SYSTEM_ROOT_SHORTCUT_NAME = "BrightEyes-MCS System.lnk"


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
    python_prompt: bool = False,
    system_root_shortcut: bool = False,
    prefix: str | Path | None = None,
) -> None:
    environment = Path(sys.prefix if prefix is None else prefix).resolve()
    payload = _read_state()
    payload["environments"][environment_key(environment)] = {
        "prefix": str(environment),
        "handled": True,
        "desktop": bool(desktop),
        "python_prompt": bool(python_prompt),
        "system_root_shortcut": bool(system_root_shortcut),
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


def python_executable(executable: str | Path | None = None) -> Path:
    """Find ``python.exe`` for the environment running BrightEyes-MCS."""

    python = Path(sys.executable if executable is None else executable).absolute()
    if python.name.casefold() == "pythonw.exe":
        python = python.with_name("python.exe")
    if not python.is_file():
        raise FileNotFoundError(f"python.exe was not found at {python}.")
    return python


def activation_script(executable: str | Path | None = None) -> Path:
    """Return the standard Windows activation script beside ``python.exe``."""

    activate = python_executable(executable).with_name("activate.bat")
    if not activate.is_file():
        raise FileNotFoundError(
            f"activate.bat was not found beside the environment interpreter: {activate}"
        )
    return activate


def command_prompt_executable(executable: str | Path | None = None) -> Path:
    """Resolve the Windows command prompt used by the developer shortcut."""

    value = os.environ.get("COMSPEC") if executable is None else str(executable)
    if not value:
        value = shutil.which("cmd.exe")
    if not value:
        raise FileNotFoundError("cmd.exe could not be located.")
    command_prompt = Path(value).absolute()
    if not command_prompt.is_file():
        raise FileNotFoundError(f"cmd.exe was not found at {command_prompt}.")
    return command_prompt


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
    arguments: str,
    working_directory: Path,
    icon: Path,
    icon_index: int = 0,
    description: str,
) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    shortcut = shell.CreateShortcut(str(link_path))
    shortcut.TargetPath = str(launcher)
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = str(working_directory)
    shortcut.IconLocation = f"{icon},{icon_index}"
    shortcut.Description = description
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
    _save_shortcut(
        shell,
        link,
        launcher=launcher,
        arguments="-m brighteyes_mcs",
        working_directory=integration_dir(),
        icon=icon,
        description="BrightEyes-MCS microscope control software",
    )
    return link


def create_python_prompt_shortcut(
    *,
    executable: str | Path | None = None,
    command_prompt: str | Path | None = None,
    shell=None,
) -> Path:
    """Create a Desktop command prompt activated for this Python environment."""

    if os.name != "nt":
        raise OSError("BrightEyes-MCS shortcuts are supported only on Windows.")

    shell = _windows_shell() if shell is None else shell
    python = python_executable(executable)
    activate = activation_script(python)
    launcher = command_prompt_executable(command_prompt)
    link = Path(shell.SpecialFolders("Desktop")) / PYTHON_SHORTCUT_NAME
    _save_shortcut(
        shell,
        link,
        launcher=launcher,
        arguments=f'/K ""{activate}""',
        working_directory=python.parent.parent,
        icon=python,
        description="Command prompt for the BrightEyes-MCS Python environment",
    )
    return link


def create_system_root_shortcut(
    system_root_path: str | Path | None = None,
    *,
    shell=None,
) -> Path:
    """Create a Desktop shortcut that opens the selected microscope profile."""

    if os.name != "nt":
        raise OSError("BrightEyes-MCS shortcuts are supported only on Windows.")

    root = Path(active_system_root() if system_root_path is None else system_root_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"The BrightEyes-MCS system root does not exist: {root}")
    shell = _windows_shell() if shell is None else shell
    link = Path(shell.SpecialFolders("Desktop")) / SYSTEM_ROOT_SHORTCUT_NAME
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    folder_icon = windows_dir / "System32" / "shell32.dll"
    _save_shortcut(
        shell,
        link,
        launcher=root,
        arguments="",
        working_directory=root,
        icon=folder_icon,
        icon_index=3,
        description="BrightEyes-MCS microscope system folder",
    )
    return link


def create_desktop_shortcuts(
    *,
    include_application: bool = True,
    include_python_prompt: bool = True,
    include_system_root: bool = True,
    system_root_path: str | Path | None = None,
    executable: str | Path | None = None,
    command_prompt: str | Path | None = None,
    shell=None,
) -> list[Path]:
    """Create application, Python-prompt, and system-folder shortcuts."""

    shell = _windows_shell() if shell is None else shell
    links = []
    if include_application:
        links.append(create_desktop_shortcut(executable=executable, shell=shell))
    if include_python_prompt:
        links.append(
            create_python_prompt_shortcut(
                executable=executable,
                command_prompt=command_prompt,
                shell=shell,
            )
        )
    if include_system_root:
        links.append(
            create_system_root_shortcut(system_root_path, shell=shell)
        )
    return links


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


def remove_python_prompt_shortcut(*, shell=None) -> bool:
    """Remove the current user's BrightEyes-MCS Python prompt shortcut."""

    if os.name != "nt":
        return False
    shell = _windows_shell() if shell is None else shell
    link = Path(shell.SpecialFolders("Desktop")) / PYTHON_SHORTCUT_NAME
    if not link.exists():
        return False
    link.unlink()
    return True


def remove_system_root_shortcut(*, shell=None) -> bool:
    """Remove the current user's BrightEyes-MCS system-folder shortcut."""

    if os.name != "nt":
        return False
    shell = _windows_shell() if shell is None else shell
    link = Path(shell.SpecialFolders("Desktop")) / SYSTEM_ROOT_SHORTCUT_NAME
    if not link.exists():
        return False
    link.unlink()
    return True


__all__ = [
    "activation_script",
    "command_prompt_executable",
    "create_desktop_shortcut",
    "create_desktop_shortcuts",
    "create_python_prompt_shortcut",
    "create_system_root_shortcut",
    "environment_key",
    "integration_dir",
    "mark_setup_handled",
    "python_executable",
    "pythonw_executable",
    "remove_desktop_shortcut",
    "remove_python_prompt_shortcut",
    "remove_system_root_shortcut",
    "setup_was_handled",
]
