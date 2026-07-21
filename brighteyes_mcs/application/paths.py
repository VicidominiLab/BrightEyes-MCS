"""Application path policy, including migration from package-local settings."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def resource_path(relative: str | Path) -> Path:
    """Return an absolute path to an immutable packaged resource."""

    return PACKAGE_ROOT / Path(relative)


def user_config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "BrightEyes-MCS"
    return Path.home() / ".config" / "BrightEyes-MCS"


def _user_relative(path: Path) -> Path:
    if path.parts and path.parts[0].lower() == "cfg":
        return Path(*path.parts[1:])
    return path


def resolve_legacy_path(value: str | Path, *, base_file: str | Path | None = None) -> Path:
    """Resolve absolute, cwd-relative, user-config, and old package-relative paths."""

    path = Path(value)
    if path.is_absolute():
        return path
    candidates = []
    if base_file:
        candidates.append(Path(base_file).resolve().parent / path)
    candidates.extend(
        [
            Path.cwd() / path,
            user_config_dir() / _user_relative(path),
            PACKAGE_ROOT / path,
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def writable_config_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return user_config_dir() / _user_relative(path)


def ensure_user_configuration() -> Path:
    """Create user-owned defaults once and return the selected configuration file."""

    destination = user_config_dir()
    plugins_destination = destination / "plugins_cfg"
    plugins_destination.mkdir(parents=True, exist_ok=True)

    bundled_default = resource_path("cfg/default.cfg")
    user_default = destination / "default.cfg"
    if not user_default.exists():
        shutil.copy2(bundled_default, user_default)

    bundled_plugins = resource_path("cfg/plugins_cfg")
    if bundled_plugins.exists():
        for source in bundled_plugins.glob("*.cfg"):
            target = plugins_destination / source.name
            if not target.exists():
                shutil.copy2(source, target)

    pointer = destination / "current_system"
    if pointer.exists():
        lines = pointer.read_text(encoding="utf-8").splitlines()
        if len(lines) > 1:
            selected = resolve_legacy_path(lines[1], base_file=pointer)
            if selected.exists():
                return selected

    selected_source = bundled_default
    legacy_pointer = resource_path("cfg/current_system")
    if legacy_pointer.exists():
        lines = legacy_pointer.read_text(encoding="utf-8").splitlines()
        if len(lines) > 1:
            candidate = resolve_legacy_path(lines[1], base_file=legacy_pointer)
            if candidate.exists():
                selected_source = candidate

    selected = user_default
    if selected_source.resolve() != bundled_default.resolve():
        selected = destination / selected_source.name
        if not selected.exists():
            shutil.copy2(selected_source, selected)

    write_default_pointer(selected)
    return selected


def write_default_pointer(configuration_file: str | Path) -> Path:
    pointer = user_config_dir() / "current_system"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(
        "# the line below provides the default configuration file\n" + str(configuration_file),
        encoding="utf-8",
    )
    return pointer
