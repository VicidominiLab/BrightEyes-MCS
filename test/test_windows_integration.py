from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from brighteyes_mcs.application.bootstrap import _startup_options, main
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


def test_module_help_lists_launcher_options_without_starting_qt(capsys):
    result = main(["brighteyes_mcs", "--help"])

    output = capsys.readouterr().out
    assert result == 0
    assert "usage: python -m brighteyes_mcs" in output
    assert "--setup" in output
    assert "--no-first-run" in output
    assert "does not create a brighteyes-mcs.exe" in " ".join(output.split())


def test_first_run_state_is_recorded_per_python_environment(tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    first_prefix = tmp_path / "venv-one"
    second_prefix = tmp_path / "venv-two"

    with patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}):
        assert not windows_integration.setup_was_handled(first_prefix)
        assert not windows_integration.setup_was_handled(second_prefix)

        windows_integration.mark_setup_handled(
            desktop=True,
            python_prompt=True,
            system_root_shortcut=True,
            prefix=first_prefix,
        )

        assert windows_integration.setup_was_handled(first_prefix)
        assert not windows_integration.setup_was_handled(second_prefix)
        payload = json.loads(windows_integration.state_path().read_text(encoding="utf-8"))
        record = payload["environments"][windows_integration.environment_key(first_prefix)]
        assert record["desktop"] is True
        assert record["python_prompt"] is True
        assert record["system_root_shortcut"] is True


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


def test_desktop_shortcuts_include_activated_python_prompt_by_default(tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    scripts = tmp_path / "BrightEyes environment" / "Scripts"
    scripts.mkdir(parents=True)
    python = scripts / "python.exe"
    pythonw = scripts / "pythonw.exe"
    activate = scripts / "activate.bat"
    command_prompt = tmp_path / "Windows" / "System32" / "cmd.exe"
    command_prompt.parent.mkdir(parents=True)
    for path in (python, pythonw, activate, command_prompt):
        path.touch()
    shell = FakeShell(tmp_path / "KnownFolders")

    with patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}):
        links = windows_integration.create_desktop_shortcuts(
            executable=python,
            command_prompt=command_prompt,
            system_root_path=tmp_path,
            shell=shell,
        )

    assert links == [
        tmp_path / "KnownFolders" / "Desktop" / "BrightEyes-MCS.lnk",
        tmp_path / "KnownFolders" / "Desktop" / "BrightEyes-MCS Python.lnk",
        tmp_path / "KnownFolders" / "Desktop" / "BrightEyes-MCS System.lnk",
    ]
    assert len(shell.shortcuts) == 3
    application, prompt, system = shell.shortcuts
    assert application.TargetPath == str(pythonw.resolve())
    assert prompt.TargetPath == str(command_prompt.resolve())
    assert prompt.Arguments == f'/K ""{activate.resolve()}""'
    assert prompt.WorkingDirectory == str(scripts.parent.resolve())
    assert prompt.IconLocation == f"{python.resolve()},0"
    assert prompt.Description == "Command prompt for the BrightEyes-MCS Python environment"
    assert prompt.saved is True
    assert system.TargetPath == str(tmp_path.resolve())
    assert system.Arguments == ""
    assert system.WorkingDirectory == str(tmp_path.resolve())
    assert system.IconLocation.endswith(r"System32\shell32.dll,3")
    assert system.Description == "BrightEyes-MCS microscope system folder"
    assert system.saved is True


def test_desktop_shortcuts_can_skip_python_prompt(tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    python = scripts / "python.exe"
    (scripts / "pythonw.exe").touch()
    python.touch()
    shell = FakeShell(tmp_path / "KnownFolders")

    with patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}):
        links = windows_integration.create_desktop_shortcuts(
            executable=python,
            include_python_prompt=False,
            include_system_root=False,
            shell=shell,
        )

    assert len(links) == 1
    assert len(shell.shortcuts) == 1


def test_system_root_shortcut_requires_an_existing_folder(tmp_path):
    shell = FakeShell(tmp_path / "KnownFolders")

    try:
        windows_integration.create_system_root_shortcut(
            tmp_path / "missing-system",
            shell=shell,
        )
    except FileNotFoundError as error:
        assert "system root does not exist" in str(error)
    else:
        raise AssertionError("A missing system root should fail shortcut creation.")
