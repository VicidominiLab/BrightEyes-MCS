from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from brighteyes_mcs.application.bootstrap import _startup_options
from brighteyes_mcs.application import windows_integration


class FakeShortcut:
    def __init__(self, path: str):
        self.path = Path(path)
        self.saved = False

    def Save(self):
        self.saved = True


class FakeShell:
    def __init__(self, root: Path):
        self.root = root
        self.shortcuts: list[FakeShortcut] = []

    def SpecialFolders(self, name: str):
        return str(self.root / name)

    def CreateShortcut(self, path: str):
        shortcut = FakeShortcut(path)
        self.shortcuts.append(shortcut)
        return shortcut


def test_startup_options_are_removed_before_qt_receives_arguments():
    argv, force_setup, skip_setup = _startup_options(
        ["brighteyes_mcs", "debug", "--setup", "--no-first-run"]
    )

    assert argv == ["brighteyes_mcs", "debug"]
    assert force_setup is True
    assert skip_setup is True


def test_first_run_state_is_recorded_per_python_environment(tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    first_prefix = tmp_path / "venv-one"
    second_prefix = tmp_path / "venv-two"

    with patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}):
        assert not windows_integration.setup_was_handled(first_prefix)
        assert not windows_integration.setup_was_handled(second_prefix)

        windows_integration.mark_setup_handled(desktop=True, prefix=first_prefix)

        assert windows_integration.setup_was_handled(first_prefix)
        assert not windows_integration.setup_was_handled(second_prefix)
        payload = json.loads(windows_integration.state_path().read_text(encoding="utf-8"))
        record = payload["environments"][windows_integration.environment_key(first_prefix)]
        assert record["desktop"] is True


def test_desktop_shortcut_targets_pythonw_module_and_persistent_icon(tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    python = scripts / "python.exe"
    pythonw = scripts / "pythonw.exe"
    python.touch()
    pythonw.touch()
    shell = FakeShell(tmp_path / "KnownFolders")

    with patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}):
        link = windows_integration.create_desktop_shortcut(
            executable=python,
            shell=shell,
        )

    assert link == tmp_path / "KnownFolders" / "Desktop" / "BrightEyes-MCS.lnk"
    assert len(shell.shortcuts) == 1
    for shortcut in shell.shortcuts:
        assert shortcut.TargetPath == str(pythonw.resolve())
        assert shortcut.Arguments == "-m brighteyes_mcs"
        assert shortcut.WorkingDirectory == str(local_app_data / "BrightEyes-MCS" / "integration")
        assert shortcut.IconLocation.endswith("BrightEyes-MCS.ico,0")
        assert shortcut.saved is True
    assert (local_app_data / "BrightEyes-MCS" / "integration" / "BrightEyes-MCS.ico").is_file()


def test_pythonw_must_exist_beside_the_environment_interpreter(tmp_path):
    python = tmp_path / "python.exe"
    python.touch()

    try:
        windows_integration.pythonw_executable(python)
    except FileNotFoundError as error:
        assert "pythonw.exe was not found" in str(error)
    else:
        raise AssertionError("A missing pythonw.exe should fail shortcut creation.")
