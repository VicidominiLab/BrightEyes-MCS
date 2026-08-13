"""Application resource, system-profile, and writable path policy."""

from __future__ import annotations

from configparser import ConfigParser, Error as ConfigParserError
from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import shutil


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CURRENT_SYSTEM_SECTION = "BrightEyes-MCS"
_PERCENT_VARIABLE = re.compile(r"%([^%]+)%")


@dataclass(frozen=True)
class SystemProfile:
    """Serializable selection of one microscope's files and directories."""

    root: str
    configuration_dir: str = "."
    default_configuration: str = "default.cfg"
    plugins_dir: str = "plugins_cfg"
    scripts_dir: str = "scripts"
    bitfiles_dir: str = "bitfiles"


def resource_path(relative: str | Path) -> Path:
    """Return an absolute path to an immutable packaged resource."""

    return PACKAGE_ROOT / Path(relative)


def user_config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "BrightEyes-MCS"
    return Path.home() / ".config" / "BrightEyes-MCS"


def current_system_path() -> Path:
    """Return the per-user pointer that selects the active microscope profile."""

    return user_config_dir() / "current_system"


def expand_environment_variables(value: str | Path) -> str:
    """Expand both Windows ``%NAME%`` and Unix ``$NAME``/``${NAME}`` notation."""

    text = str(value)

    def replace_percent(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), match.group(0))

    return os.path.expanduser(os.path.expandvars(_PERCENT_VARIABLE.sub(replace_percent, text)))


def _resolved_path(value: str | Path, *, base: Path) -> Path:
    path = Path(expand_environment_variables(value))
    if path.is_absolute():
        return path
    return base / path


def default_system_profile() -> SystemProfile:
    """Return the conventional per-user profile used on a new installation."""

    return SystemProfile(root=str(user_config_dir()))


def _legacy_profile(value: str, pointer: Path) -> SystemProfile:
    raw_path = Path(expand_environment_variables(value))
    if raw_path.is_absolute():
        selected = raw_path
    else:
        candidates = [
            pointer.parent / raw_path,
            Path.cwd() / raw_path,
            user_config_dir() / raw_path,
            PACKAGE_ROOT / raw_path,
        ]
        selected = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    if selected.suffix.casefold() == ".cfg" or selected.is_file():
        return SystemProfile(
            root=str(selected.parent),
            default_configuration=selected.name,
        )
    return SystemProfile(root=value)


def load_system_profile(pointer: str | Path | None = None) -> SystemProfile:
    """Load ``current_system``, including the historical two-line file format."""

    pointer_path = current_system_path() if pointer is None else Path(pointer)
    try:
        text = pointer_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return default_system_profile()

    parser = ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except ConfigParserError:
        parser = ConfigParser(interpolation=None)

    if parser.has_section(CURRENT_SYSTEM_SECTION):
        section = parser[CURRENT_SYSTEM_SECTION]
        fallback = default_system_profile()
        return SystemProfile(
            root=section.get("root", fallback.root).strip(),
            configuration_dir=section.get("configuration_dir", ".").strip(),
            default_configuration=section.get(
                "default_configuration", "default.cfg"
            ).strip(),
            plugins_dir=section.get("plugins_dir", "plugins_cfg").strip(),
            scripts_dir=section.get("scripts_dir", "scripts").strip(),
            bitfiles_dir=section.get("bitfiles_dir", "bitfiles").strip(),
        )

    values = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", ";"))
    ]
    if values:
        return _legacy_profile(values[0], pointer_path)
    return default_system_profile()


def write_system_profile(
    profile: SystemProfile,
    pointer: str | Path | None = None,
) -> Path:
    """Persist a profile selection in the current user's ``current_system``."""

    pointer_path = current_system_path() if pointer is None else Path(pointer)
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    parser = ConfigParser(interpolation=None)
    parser[CURRENT_SYSTEM_SECTION] = {
        "root": profile.root,
        "configuration_dir": profile.configuration_dir,
        "default_configuration": profile.default_configuration,
        "plugins_dir": profile.plugins_dir,
        "scripts_dir": profile.scripts_dir,
        "bitfiles_dir": profile.bitfiles_dir,
    }
    temporary = pointer_path.with_name(pointer_path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "# Selects the active BrightEyes-MCS microscope profile.\n"
            "# Paths accept %NAME%, $NAME, and ${NAME} environment variables.\n"
        )
        parser.write(stream)
    temporary.replace(pointer_path)
    return pointer_path


def system_root(profile: SystemProfile | None = None) -> Path:
    """Return the expanded active profile root."""

    selected = load_system_profile() if profile is None else profile
    return _resolved_path(selected.root, base=current_system_path().parent)


def profile_directory(kind: str, profile: SystemProfile | None = None) -> Path:
    """Resolve one configurable directory below (or outside) the profile root."""

    selected = load_system_profile() if profile is None else profile
    settings = {
        "configuration": selected.configuration_dir,
        "config": selected.configuration_dir,
        "plugins": selected.plugins_dir,
        "plugins_config": selected.plugins_dir,
        "scripts": selected.scripts_dir,
        "bitfiles": selected.bitfiles_dir,
        "firmware": selected.bitfiles_dir,
    }
    try:
        setting = settings[kind.casefold()]
    except KeyError as error:
        raise ValueError(f"Unknown system-profile directory: {kind}") from error
    return _resolved_path(setting, base=system_root(selected))


def default_configuration_path(profile: SystemProfile | None = None) -> Path:
    """Return the active profile's selected default ``.cfg`` file."""

    selected = load_system_profile() if profile is None else profile
    return _resolved_path(
        selected.default_configuration,
        base=profile_directory("configuration", selected),
    )


def validate_system_profile(profile: SystemProfile) -> list[str]:
    """Return user-facing validation errors without changing the filesystem."""

    errors = []
    root = system_root(profile)
    config_dir = profile_directory("configuration", profile)
    default_cfg = default_configuration_path(profile)
    if not root.is_dir():
        errors.append(f"System root does not exist: {root}")
    if not config_dir.is_dir():
        errors.append(f"Configuration folder does not exist: {config_dir}")
    if not default_cfg.is_file():
        errors.append(f"Default configuration does not exist: {default_cfg}")
    return errors


def generate_system_configuration(
    profile: SystemProfile,
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Create a profile tree and copy the packaged default configurations.

    Existing configuration files are preserved unless ``overwrite`` is true.
    The returned paths are the files that were copied by this call.
    """

    directories = {
        system_root(profile),
        profile_directory("configuration", profile),
        profile_directory("plugins", profile),
        profile_directory("scripts", profile),
        profile_directory("bitfiles", profile),
    }
    default_target = default_configuration_path(profile)
    directories.add(default_target.parent)
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []

    def copy_if_needed(source: Path, target: Path) -> None:
        if overwrite or not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target)

    copy_if_needed(resource_path("cfg/default.cfg"), default_target)
    bundled_plugins = resource_path("cfg/plugins_cfg")
    if bundled_plugins.is_dir():
        plugins_target = profile_directory("plugins", profile)
        for source in sorted(bundled_plugins.glob("*.cfg")):
            copy_if_needed(source, plugins_target / source.name)
    return copied


def _profile_alias(path: Path, profile: SystemProfile) -> Path | None:
    parts = path.parts
    if not parts:
        return None
    first = parts[0].casefold()
    remainder = parts[1:]
    if first == "cfg":
        if remainder and remainder[0].casefold() == "plugins_cfg":
            return profile_directory("plugins", profile).joinpath(*remainder[1:])
        return profile_directory("configuration", profile).joinpath(*remainder)
    aliases = {
        "plugins_cfg": "plugins",
        "scripts": "scripts",
        "bitfiles": "bitfiles",
        "firmware": "bitfiles",
    }
    if first in aliases:
        return profile_directory(aliases[first], profile).joinpath(*remainder)
    return None


def resolve_legacy_path(
    value: str | Path,
    *,
    base_file: str | Path | None = None,
) -> Path:
    """Resolve profile, absolute, cwd, user, and old package-relative paths."""

    path = Path(expand_environment_variables(value))
    if path.is_absolute():
        return path

    profile = load_system_profile()
    candidates: list[Path] = []
    if base_file:
        candidates.append(Path(base_file).resolve().parent / path)
    alias = _profile_alias(path, profile)
    if alias is not None:
        candidates.append(alias)
    candidates.extend(
        [
            system_root(profile) / path,
            profile_directory("configuration", profile) / path,
            Path.cwd() / path,
            user_config_dir() / path,
            PACKAGE_ROOT / path,
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def writable_config_path(value: str | Path) -> Path:
    """Resolve a configuration or plug-in path within the selected profile."""

    path = Path(expand_environment_variables(value))
    if path.is_absolute():
        return path
    profile = load_system_profile()
    alias = _profile_alias(path, profile)
    if alias is not None:
        return alias
    return profile_directory("configuration", profile) / path


def _copy_user_defaults() -> Path:
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
    return user_default


def ensure_user_configuration() -> Path:
    """Bootstrap per-user defaults and return the profile's selected config."""

    user_default = _copy_user_defaults()
    pointer = current_system_path()
    if pointer.exists():
        selected = default_configuration_path()
        return selected if selected.is_file() else user_default

    bundled_default = resource_path("cfg/default.cfg")
    selected_source = bundled_default
    legacy_pointer = resource_path("cfg/current_system")
    if legacy_pointer.exists():
        legacy_profile = load_system_profile(legacy_pointer)
        candidate = default_configuration_path(legacy_profile)
        if candidate.exists():
            selected_source = candidate

    selected = user_default
    if selected_source.resolve() != bundled_default.resolve():
        selected = user_config_dir() / selected_source.name
        if not selected.exists():
            shutil.copy2(selected_source, selected)

    write_system_profile(
        replace(default_system_profile(), default_configuration=selected.name)
    )
    return selected


def write_default_pointer(configuration_file: str | Path) -> Path:
    """Select a default config without discarding the rest of the profile."""

    profile = load_system_profile()
    configuration = Path(expand_environment_variables(configuration_file))
    if not configuration.is_absolute():
        configuration = resolve_legacy_path(configuration)
    config_dir = profile_directory("configuration", profile)
    try:
        stored = str(configuration.resolve().relative_to(config_dir.resolve()))
    except ValueError:
        stored = str(configuration)
    write_system_profile(replace(profile, default_configuration=stored))
    return current_system_path()


__all__ = [
    "SystemProfile",
    "current_system_path",
    "default_configuration_path",
    "default_system_profile",
    "ensure_user_configuration",
    "expand_environment_variables",
    "generate_system_configuration",
    "load_system_profile",
    "profile_directory",
    "resource_path",
    "resolve_legacy_path",
    "system_root",
    "user_config_dir",
    "validate_system_profile",
    "writable_config_path",
    "write_default_pointer",
    "write_system_profile",
]
