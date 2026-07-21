from __future__ import annotations

import argparse
import base64
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable
import tkinter as tk


APP_NAME = "BrightEyes-MCS Installer"
REPO_FOLDER_NAME = "BrightEyes-MCS"
REPO_URL = "https://github.com/VicidominiLab/BrightEyes-MCS.git"
REPO_API_URL = "https://api.github.com/repos/VicidominiLab/BrightEyes-MCS"
GIT_FOR_WINDOWS_URL = "https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"
GIT_FOR_WINDOWS_PAGE_URL = "https://git-scm.com/download/win"
PYTHON_313_INSTALLER_URL = "https://www.python.org/ftp/python/3.13.14/python-3.13.14-amd64.exe"
PYTHON_313_PAGE_URL = "https://www.python.org/downloads/release/python-31314/"
NI_R_SERIES_MRIO_URL = "https://www.ni.com/en/support/downloads/drivers/download.ni-r-series-multifunction-rio.html"
FIRMWARE_REPO = "VicidominiLab/BrightEyes-MCSLL"
FIRMWARE_API_URL = f"https://api.github.com/repos/{FIRMWARE_REPO}"
FIRMWARE_ZIP_URL = f"https://github.com/{FIRMWARE_REPO}/archive/refs/heads/{{branch}}.zip"
MAX_LICENSE_BYTES = 256 * 1024
GITHUB_API_CACHE_TTL_SECONDS = 10 * 60
PRESERVED_PATHS = [
    Path("brighteyes_mcs/cfg"),
    Path("brighteyes_mcs/bitfiles"),
    Path("brighteyes_mcs_installer.exe"),
]
_GITHUB_API_CACHE: dict[str, tuple[float, object]] = {}
_GITHUB_RATE_LIMIT_WARNINGS: set[str] = set()
_GITHUB_API_RATE_LIMITED_UNTIL = 0.0

LICENSE_NOTICE = """BrightEyes-MCS
License: GNU General Public License version 3 (GPLv3)
Source and full license text: https://github.com/VicidominiLab/BrightEyes-MCS

This installer is distributed with BrightEyes-MCS under the GPLv3. The GPLv3 permits
copying, redistribution, and modification under its terms. BrightEyes-MCS is provided
without warranty.

Python runtime
License: Python Software Foundation License
License text: https://docs.python.org/3/license.html

Tcl/Tk runtime used by tkinter
License: Tcl/Tk license
License text: https://www.tcl-lang.org/software/tcltk/license.html

PyInstaller bootloader/runtime
License: GPLv2-or-later with a special exception for distributing bundled programs
License text: https://pyinstaller.org/en/stable/license.html
"""


@dataclass
class PythonCandidate:
    label: str
    command: str
    version: tuple[int, int, int] | None


@dataclass
class CommitCandidate:
    sha: str
    short_sha: str
    date: str
    message: str


class InstallerError(RuntimeError):
    pass


def user_configuration_dir() -> Path:
    """Return the user-owned configuration directory used by the application."""

    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "BrightEyes-MCS"
    return Path.home() / ".config" / "BrightEyes-MCS"


def creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def log_print(message: str) -> None:
    print(message, flush=True)


def run_capture(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags(),
    )


def run_logged(
    command: list[str],
    cwd: Path | None,
    log: Callable[[str], None],
    env: dict[str, str] | None = None,
) -> None:
    rendered = " ".join(f'"{part}"' if " " in part else part for part in command)
    log("Running: " + rendered)
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags(),
    )
    assert process.stdout is not None
    for line in process.stdout:
        log(line.rstrip())
    return_code = process.wait()
    if return_code != 0:
        raise InstallerError(f"Command failed with exit code {return_code}: {rendered}")


def python_version(command: str) -> tuple[int, int, int] | None:
    try:
        result = run_capture(
            [
                command,
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')",
            ]
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        return tuple(int(part) for part in result.stdout.strip().split(".")[:3])
    except ValueError:
        return None


def is_python_313(version: tuple[int, int, int] | None) -> bool:
    return bool(version and version[0] == 3 and version[1] == 13)


def is_venv_python(command: str) -> bool:
    path = Path(command)
    parts = {part.lower() for part in path.parts}
    return bool({".venv", "venv", "env", ".env"} & parts)


def path_from_py_launcher_line(line: str) -> str | None:
    match = re.search(r"([A-Za-z]:\\.*python(?:\.exe)?)\s*$", line, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def discover_python_candidates() -> list[PythonCandidate]:
    seen: set[str] = set()
    candidates: list[PythonCandidate] = []

    py_launcher = shutil.which("py")
    if py_launcher:
        result = run_capture([py_launcher, "-0p"])
        for line in result.stdout.splitlines():
            path_text = path_from_py_launcher_line(line.strip())
            if path_text and Path(path_text).exists() and path_text.lower() not in seen:
                seen.add(path_text.lower())
                candidates.append(PythonCandidate(path_text, path_text, python_version(path_text)))

    where = shutil.which("where")
    if where:
        result = run_capture([where, "python.exe"])
        for line in result.stdout.splitlines():
            path_text = line.strip()
            if Path(path_text).exists() and path_text.lower() not in seen:
                seen.add(path_text.lower())
                candidates.append(PythonCandidate(path_text, path_text, python_version(path_text)))

    current = Path(sys.executable)
    if current.exists() and str(current).lower() not in seen:
        version = python_version(str(current))
        if version:
            candidates.append(PythonCandidate(str(current), str(current), version))

    candidates.sort(key=lambda candidate: (not is_python_313(candidate.version), is_venv_python(candidate.command)))
    return candidates


def best_python_313() -> str | None:
    for candidate in discover_python_candidates():
        if is_python_313(candidate.version):
            return candidate.command
    return None


def download_file(url: str, destination: Path, log: Callable[[str], None]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = response.headers.get("Content-Length")
            total_bytes = int(total) if total and total.isdigit() else None
            downloaded = 0
            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 128)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes:
                        log(f"Download progress: {int(downloaded * 100 / total_bytes)}%")
    except urllib.error.URLError as exc:
        raise InstallerError(f"Download failed: {exc}") from exc


def open_python_installer(log: Callable[[str], None]) -> None:
    installer_path = Path(tempfile.gettempdir()) / Path(urllib.parse.urlparse(PYTHON_313_INSTALLER_URL).path).name
    log("Downloading Python 3.13 installer from python.org...")
    download_file(PYTHON_313_INSTALLER_URL, installer_path, log)
    log("Opening Python 3.13 installer.")
    subprocess.Popen([str(installer_path)], creationflags=creationflags())


def confirm_python_download() -> bool:
    print("Python 3.13 installer will be downloaded from:")
    print(PYTHON_313_INSTALLER_URL)
    answer = input("Continue with the download? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def open_git_installer(log: Callable[[str], None]) -> None:
    installer_path = Path(tempfile.gettempdir()) / Path(urllib.parse.urlparse(GIT_FOR_WINDOWS_URL).path).name
    log("Downloading Git for Windows installer from GitHub...")
    download_file(GIT_FOR_WINDOWS_URL, installer_path, log)
    log("Opening Git for Windows installer.")
    subprocess.Popen([str(installer_path)], creationflags=creationflags())


def ensure_git_available() -> None:
    if shutil.which("git"):
        return
    raise InstallerError(
        "Git for Windows was not found in PATH.\n"
        "Install it from:\n"
        + GIT_FOR_WINDOWS_URL
    )


def create_virtual_environment(project_dir: Path, python_command: str, log: Callable[[str], None]) -> Path:
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        log("Using existing .venv.")
        return venv_python
    log("Creating .venv with Python 3.13...")
    run_logged([python_command, "-m", "venv", ".venv"], project_dir, log)
    if not venv_python.exists():
        raise InstallerError("Virtual environment creation completed, but .venv Python was not found.")
    return venv_python


def install_requirements(
    project_dir: Path,
    venv_python: Path,
    log: Callable[[str], None],
    upgrade_requirements: bool = False,
) -> None:
    requirements = project_dir / "requirements.txt"
    if not requirements.exists():
        raise InstallerError(f"requirements.txt was not found in {project_dir}.")
    run_logged([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], project_dir, log)
    command = [str(venv_python), "-m", "pip", "install"]
    if upgrade_requirements:
        command.append("-U")
    run_logged([*command, "-r", "requirements.txt"], project_dir, log)


def check_compiled_extensions(project_dir: Path, venv_python: Path, log: Callable[[str], None]) -> None:
    test_file = project_dir / "test" / "check_compiled_extensions.py"
    if not test_file.exists():
        log("Compiled extension check skipped; test/check_compiled_extensions.py was not found.")
        return
    run_logged([str(venv_python), str(test_file)], project_dir, log)


def powershell_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def create_shortcut(link_path: Path, target: Path, icon: str, working_dir: Path, log: Callable[[str], None]) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    script = "\n".join(
        [
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut({powershell_quote(str(link_path))})",
            f"$shortcut.TargetPath = {powershell_quote(str(target))}",
            f"$shortcut.WorkingDirectory = {powershell_quote(str(working_dir))}",
            f"$shortcut.IconLocation = {powershell_quote(icon)}",
            "$shortcut.Save()",
        ]
    )
    run_logged(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        working_dir,
        log,
    )


def desktop_path() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"


def create_links(project_dir: Path, venv_python: Path, log: Callable[[str], None]) -> None:
    run_bat = project_dir / "run.bat"
    enter_bat = project_dir / "enter_in_venv.bat"
    icon = project_dir / "brighteyes_mcs" / "images" / "icon.ico"
    icon_text = str(icon) if icon.exists() else f"{venv_python},0"
    python_icon = f"{venv_python},0"

    folder = desktop_path()
    create_shortcut(folder / "BrightEyesMCS.lnk", run_bat, icon_text, project_dir, log)
    create_shortcut(folder / "Python (.venv BrightEyesMCS).lnk", enter_bat, python_icon, project_dir, log)


def github_api_headers() -> dict[str, str]:
    headers = {
        "User-Agent": APP_NAME,
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_rate_limit_message(exc: urllib.error.HTTPError) -> str:
    reset_time = github_rate_limit_reset_time(exc)
    return "GitHub API rate limit used up. " + github_rate_limit_reset_message(reset_time)


def github_rate_limit_reset_time(exc: urllib.error.HTTPError) -> float | None:
    reset = exc.headers.get("X-RateLimit-Reset")
    if reset and reset.isdigit():
        return float(reset)
    return None


def github_rate_limit_reset_message(reset_time: float | None) -> str:
    if not reset_time:
        return "Reset time is unknown."

    remaining = max(0, int(reset_time - time.time()))
    minutes, seconds = divmod(remaining, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        duration = f"in {hours} h {minutes} min"
    elif minutes:
        duration = f"in {minutes} min {seconds} s"
    else:
        duration = f"in {seconds} s"

    reset_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(reset_time))
    return f"Reset {duration}, at {reset_text} local time."


def is_github_rate_limit_error(exc: urllib.error.HTTPError) -> bool:
    if exc.code not in {403, 429}:
        return False
    remaining = exc.headers.get("X-RateLimit-Remaining")
    return remaining == "0" or "rate limit" in str(exc).lower()


def read_github_json(url: str, log: Callable[[str], None], description: str) -> object | None:
    global _GITHUB_API_RATE_LIMITED_UNTIL

    now = time.time()
    cached = _GITHUB_API_CACHE.get(url)
    if cached and now - cached[0] < GITHUB_API_CACHE_TTL_SECONDS:
        return cached[1]
    if _GITHUB_API_RATE_LIMITED_UNTIL > now:
        if "rate-limit" not in _GITHUB_RATE_LIMIT_WARNINGS:
            _GITHUB_RATE_LIMIT_WARNINGS.add("rate-limit")
            log(
                "GitHub API rate limit already used up. "
                f"{github_rate_limit_reset_message(_GITHUB_API_RATE_LIMITED_UNTIL)} "
                "Using cached/default data. GITHUB_TOKEN or GH_TOKEN is optional and only increases the limit."
            )
        return cached[1] if cached else None

    request = urllib.request.Request(url, headers=github_api_headers())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if is_github_rate_limit_error(exc):
            _GITHUB_API_RATE_LIMITED_UNTIL = github_rate_limit_reset_time(exc) or now + 60
            fallback = "using cached data" if cached else "using built-in defaults"
            if "rate-limit" not in _GITHUB_RATE_LIMIT_WARNINGS:
                _GITHUB_RATE_LIMIT_WARNINGS.add("rate-limit")
                log(
                    f"{github_rate_limit_message(exc)} Could not read {description}; {fallback}. "
                    "GITHUB_TOKEN or GH_TOKEN is optional and only increases the limit."
                )
            return cached[1] if cached else None
        if cached:
            log(f"Could not read {description}; using cached data: {exc}")
            return cached[1]
        log(f"Could not read {description}: {exc}")
        return None
    except Exception as exc:
        if cached:
            log(f"Could not read {description}; using cached data: {exc}")
            return cached[1]
        log(f"Could not read {description}: {exc}")
        return None

    _GITHUB_API_CACHE[url] = (now, data)
    return data


def github_default_branch(api_url: str, fallback: str, log: Callable[[str], None]) -> str:
    data = read_github_json(api_url, log, "default branch")
    if isinstance(data, dict):
        branch = data.get("default_branch")
        if branch:
            return str(branch)
    return fallback


def list_github_branches(api_url: str, log: Callable[[str], None]) -> list[str]:
    data = read_github_json(api_url + "/branches?per_page=100", log, "branch list")
    if not isinstance(data, list):
        return []
    return [str(item.get("name")) for item in data if item.get("name")]


def list_github_commits(api_url: str, branch: str, log: Callable[[str], None], limit: int = 20) -> list[CommitCandidate]:
    branch = branch.strip() or "main"
    query = urllib.parse.urlencode({"sha": branch, "per_page": str(limit)})
    data = read_github_json(api_url + "/commits?" + query, log, f"commit list for {branch}")
    if not isinstance(data, list):
        return []

    commits: list[CommitCandidate] = []
    for item in data:
        sha = str(item.get("sha", ""))
        commit = item.get("commit") or {}
        author = commit.get("author") or {}
        message = str(commit.get("message", "")).splitlines()[0] if commit.get("message") else ""
        date = str(author.get("date", ""))[:10]
        if sha:
            commits.append(CommitCandidate(sha=sha, short_sha=sha[:8], date=date, message=message))
    return commits


def read_github_text_file(api_url: str, path: str, ref: str, log: Callable[[str], None]) -> str:
    ref = ref.strip() or "main"
    query = urllib.parse.urlencode({"ref": ref})
    quoted_path = urllib.parse.quote(path.strip("/"))
    data = read_github_json(api_url + f"/contents/{quoted_path}?" + query, log, f"{path} from {ref}")
    if not isinstance(data, dict):
        return (
            f"Could not load {path} from {FIRMWARE_REPO} branch '{ref}'.\n\n"
            "GitHub API data is unavailable. If this is due to rate limiting, wait for the limit to reset "
            "and try refreshing later. Optionally, set GITHUB_TOKEN or GH_TOKEN before opening the installer "
            "to use a higher authenticated limit."
        )

    if data.get("encoding") != "base64" or "content" not in data:
        return f"Could not load {path} from {FIRMWARE_REPO} branch '{ref}': unexpected GitHub response."

    try:
        raw = base64.b64decode(str(data["content"]), validate=False)
    except Exception as exc:
        return f"Could not decode {path} from {FIRMWARE_REPO} branch '{ref}'.\n\n{exc}"

    if len(raw) > MAX_LICENSE_BYTES:
        raw = raw[:MAX_LICENSE_BYTES] + b"\n\n[license text truncated]\n"
    return raw.decode("utf-8", errors="replace")


def download_firmware(project_dir: Path, branch: str, log: Callable[[str], None]) -> None:
    branch = branch.strip() or "main"
    target_dir = project_dir / "brighteyes_mcs" / "bitfiles"
    target_dir.mkdir(parents=True, exist_ok=True)
    encoded_branch = urllib.parse.quote(branch, safe="")

    with tempfile.TemporaryDirectory(prefix="brighteyes_mcs_firmware_") as temp_name:
        archive_path = Path(temp_name) / "firmware.zip"
        log(f"Downloading firmware branch '{branch}' from {FIRMWARE_REPO}...")
        download_file(FIRMWARE_ZIP_URL.format(branch=encoded_branch), archive_path, log)
        copied = 0
        with zipfile.ZipFile(archive_path) as archive:
            for file_info in archive.infolist():
                if file_info.is_dir():
                    continue
                file_name = Path(file_info.filename).name
                if not file_name:
                    continue
                with archive.open(file_info) as source, (target_dir / file_name).open("wb") as output:
                    shutil.copyfileobj(source, output)
                copied += 1
    if copied == 0:
        raise InstallerError("The firmware archive did not contain files.")
    log(f"Firmware files copied to {target_dir}.")


def git_command(project_dir: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["git", "-c", f"safe.directory={project_dir.as_posix()}", *args]
    result = run_capture(command, cwd=project_dir)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise InstallerError(f"git {' '.join(args)} failed.\n{detail}")
    return result


def git_output(project_dir: Path, *args: str, check: bool = True) -> str:
    return git_command(project_dir, *args, check=check).stdout.strip()


def status_entries(project_dir: Path) -> list[tuple[str, str]]:
    output = git_output(project_dir, "status", "--porcelain", "--untracked-files=all")
    return [(line[:2], line[3:].strip()) for line in output.splitlines() if line]


def is_preserved_path(path_text: str) -> bool:
    normalized = path_text.strip().strip('"').replace("\\", "/")
    for preserved in PRESERVED_PATHS:
        preserved_text = preserved.as_posix()
        if normalized == preserved_text or normalized.startswith(preserved_text + "/"):
            return True
    return False


def backup_preserved_paths(project_dir: Path, log: Callable[[str], None]) -> tuple[Path, list[Path]]:
    backup_dir = Path(tempfile.mkdtemp(prefix="brighteyes_mcs_cfg_"))
    copied: list[Path] = []
    for relative in PRESERVED_PATHS:
        source = project_dir / relative
        if not source.exists():
            continue
        destination = backup_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        copied.append(relative)
    if copied:
        log("Backed up local cfg/firmware files to " + str(backup_dir))
    return backup_dir, copied


def restore_preserved_paths(project_dir: Path, backup_dir: Path, copied: list[Path], log: Callable[[str], None]) -> None:
    for relative in copied:
        source = backup_dir / relative
        destination = project_dir / relative
        if not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
    if copied:
        log("Restored local cfg/firmware files.")


def remove_preserved_paths(project_dir: Path) -> None:
    for relative in PRESERVED_PATHS:
        target = project_dir / relative
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def current_branch(project_dir: Path) -> str | None:
    branch = git_output(project_dir, "branch", "--show-current", check=False)
    return branch or None


def remote_default_branch(project_dir: Path) -> str | None:
    text = git_output(project_dir, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    if "/" in text:
        return text.split("/", 1)[1]
    return text or None


def update_from_git(
    project_dir: Path,
    branch: str | None,
    commit: str | None,
    stash_local: bool,
    log: Callable[[str], None],
) -> None:
    if not (project_dir / ".git").exists():
        raise InstallerError(f"{project_dir} is not a git checkout.")
    ensure_git_available()

    blocking = [(code, path) for code, path in status_entries(project_dir) if not is_preserved_path(path)]
    if blocking and not stash_local:
        preview = "\n".join(f"  {code} {path}" for code, path in blocking[:10])
        raise InstallerError("Local changes outside cfg/firmware were found. Commit them or use --stash-local.\n" + preview)
    if blocking and stash_local:
        run_logged(["git", "stash", "push", "--include-untracked", "-m", "BrightEyes-MCS installer stash"], project_dir, log)

    backup_dir, copied = backup_preserved_paths(project_dir, log)
    try:
        run_logged(["git", "-c", f"safe.directory={project_dir.as_posix()}", "fetch", "--all", "--prune"], project_dir, log)
        remove_preserved_paths(project_dir)
        selected_branch = (branch or current_branch(project_dir) or remote_default_branch(project_dir) or "main").strip()
        if selected_branch:
            remote_branch = f"origin/{selected_branch}"
            if git_command(project_dir, "rev-parse", "--verify", "--quiet", remote_branch, check=False).returncode == 0:
                run_logged(["git", "-c", f"safe.directory={project_dir.as_posix()}", "checkout", "-B", selected_branch, remote_branch], project_dir, log)
            else:
                run_logged(["git", "-c", f"safe.directory={project_dir.as_posix()}", "checkout", selected_branch], project_dir, log)
        if selected_branch:
            run_logged(["git", "-c", f"safe.directory={project_dir.as_posix()}", "pull", "--ff-only", "origin", selected_branch], project_dir, log)
        if commit:
            run_logged(["git", "-c", f"safe.directory={project_dir.as_posix()}", "checkout", commit], project_dir, log)
    finally:
        restore_preserved_paths(project_dir, backup_dir, copied, log)
        shutil.rmtree(backup_dir, ignore_errors=True)


def source_tree_exists(project_dir: Path) -> bool:
    return (project_dir / "requirements.txt").exists() and (project_dir / "brighteyes_mcs").exists()


def source_or_checkout_exists(project_dir: Path) -> bool:
    return source_tree_exists(project_dir) or (project_dir / ".git").exists()


def project_source_dir(selected_folder: Path) -> Path:
    if selected_folder.name.lower() == REPO_FOLDER_NAME.lower() or source_or_checkout_exists(selected_folder):
        return selected_folder
    return selected_folder / REPO_FOLDER_NAME


def prepare_source(
    project_dir: Path,
    branch: str | None,
    commit: str | None,
    stash_local: bool,
    log: Callable[[str], None],
) -> None:
    branch = (branch or "").strip() or "main"
    commit = (commit or "").strip() or None

    if (project_dir / ".git").exists():
        update_from_git(project_dir, branch, commit, stash_local, log)
        return

    if source_tree_exists(project_dir):
        if commit or branch != "main":
            log("Source folder is not a git checkout; branch/commit selection is ignored.")
        return

    ensure_git_available()
    project_dir.parent.mkdir(parents=True, exist_ok=True)
    if project_dir.exists() and any(project_dir.iterdir()):
        raise InstallerError(f"{project_dir} is not empty and is not a BrightEyes-MCS source tree.")

    log(f"Cloning BrightEyes-MCS branch '{branch}'...")
    run_logged(["git", "clone", "--branch", branch, REPO_URL, str(project_dir)], None, log)
    if commit:
        run_logged(["git", "-c", f"safe.directory={project_dir.as_posix()}", "checkout", commit], project_dir, log)


def select_python(command: str | None) -> str:
    if command:
        version = python_version(command)
        if not is_python_313(version):
            found = ".".join(str(part) for part in version) if version else "unknown"
            raise InstallerError(
                f"Python 3.13 is required. Selected Python version: {found}.\n"
                "Install it from:\n"
                + PYTHON_313_INSTALLER_URL
            )
        return command
    discovered = best_python_313()
    if not discovered:
        raise InstallerError(
            "Python 3.13 was not found. Install it from:\n" + PYTHON_313_INSTALLER_URL
        )
    return discovered


def install_project(
    project_dir: Path,
    python_command: str | None,
    create_desktop_links: bool,
    firmware_branch: str | None,
    source_branch: str | None,
    source_commit: str | None,
    stash_local: bool,
    log: Callable[[str], None],
    upgrade_requirements: bool = False,
) -> None:
    project_dir = project_dir.resolve()
    if source_branch is not None or source_commit is not None or not source_tree_exists(project_dir):
        prepare_source(project_dir, source_branch, source_commit, stash_local, log)
    selected_python = select_python(python_command)
    venv_python = create_virtual_environment(project_dir, selected_python, log)
    install_requirements(project_dir, venv_python, log, upgrade_requirements)
    check_compiled_extensions(project_dir, venv_python, log)
    config_dir = user_configuration_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    log(f"User configuration is preserved in {config_dir}.")
    if create_desktop_links:
        create_links(project_dir, venv_python, log)
    if firmware_branch is not None:
        download_firmware(project_dir, firmware_branch, log)


def cli_install(args: argparse.Namespace) -> None:
    install_project(
        Path(args.path),
        args.python,
        not args.no_links,
        None if args.no_firmware else args.firmware_branch,
        args.source_branch,
        args.source_commit,
        args.stash_local,
        log_print,
    )


def cli_update(args: argparse.Namespace) -> None:
    project_dir = Path(args.path).resolve()
    update_from_git(project_dir, args.branch, args.commit, args.stash_local, log_print)
    install_project(
        project_dir,
        args.python,
        not args.no_links,
        None if args.no_firmware else args.firmware_branch,
        None,
        None,
        args.stash_local,
        log_print,
        upgrade_requirements=True,
    )


def cli_links(args: argparse.Namespace) -> None:
    project_dir = Path(args.path).resolve()
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        raise InstallerError("The .venv Python was not found. Run install first.")
    create_links(project_dir, venv_python, log_print)


def cli_firmware(args: argparse.Namespace) -> None:
    download_firmware(Path(args.path).resolve(), args.firmware_branch, log_print)


def cli_python_link(_args: argparse.Namespace) -> None:
    if not confirm_python_download():
        log_print("Python 3.13 download cancelled.")
        return
    open_python_installer(log_print)


def cli_pythons(_args: argparse.Namespace) -> None:
    candidates = discover_python_candidates()
    if not candidates:
        print("No Python installations found.")
        print("Python 3.13 installer:", PYTHON_313_INSTALLER_URL)
        return
    for index, candidate in enumerate(candidates, start=1):
        version = ".".join(str(part) for part in candidate.version) if candidate.version else "unknown"
        marker = "  [recommended]" if is_python_313(candidate.version) else ""
        print(f"{index}. {version}  {candidate.command}{marker}")
    if not any(is_python_313(candidate.version) for candidate in candidates):
        print()
        print("Python 3.13 was not found. Installer:", PYTHON_313_INSTALLER_URL)


class InstallerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.minsize(940, 760)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.python_candidates = discover_python_candidates()
        self.source_commit_items: list[CommitCandidate] = []
        self.is_busy = False

        self.project_dir_var = tk.StringVar(value=str(desktop_path() / "BrightEyes"))
        self.python_var = tk.StringVar(value=best_python_313() or "")
        self.source_branch_var = tk.StringVar(value="main")
        self.source_commit_var = tk.StringVar(value="")
        self.firmware_branch_var = tk.StringVar(value="main")
        self.create_links_var = tk.BooleanVar(value=True)
        self.stash_local_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="")
        self.project_dir_var.trace_add("write", self.on_project_dir_changed)

        self._build_ui()
        self.after(100, self._drain_log_queue)
        self.after(250, self.refresh_source_branches)
        self.after(300, self.refresh_firmware_branches)
        self.refresh_status()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(4, weight=1)

        ttk.Label(root, text="BrightEyes-MCS installer", font=("", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )

        ttk.Label(root, text="Destination Folder").grid(row=1, column=0, sticky="w")
        ttk.Entry(root, textvariable=self.project_dir_var).grid(row=1, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(root, text="Browse", command=self.browse_project_dir).grid(row=1, column=2, sticky="e")
        ttk.Label(root, textvariable=self.status_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(root, text="Refresh", command=self.refresh_status).grid(row=2, column=2, sticky="e", pady=(6, 0))

        notebook = ttk.Notebook(root)
        notebook.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(12, 0))

        prereq = ttk.Frame(notebook, padding=12)
        setup = ttk.Frame(notebook, padding=12)
        firmware = ttk.Frame(notebook, padding=12)
        licenses = ttk.Frame(notebook, padding=12)
        notebook.add(prereq, text="Prerequisites")
        notebook.add(setup, text="Install/Update")
        notebook.add(firmware, text="Firmware")
        notebook.add(licenses, text="Licenses")

        prereq.columnconfigure(1, weight=1)
        ttk.Label(prereq, text="Python 3.13").grid(row=0, column=0, sticky="w")
        values = [self._python_label(candidate) for candidate in self.python_candidates]
        self.python_box = ttk.Combobox(prereq, values=values, state="normal")
        self.python_box.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.python_box.bind("<<ComboboxSelected>>", self.select_python_from_label)
        if self.python_var.get():
            self.python_box.set(self.python_label_for_command(self.python_var.get()))
        ttk.Button(prereq, text="Check Python", command=self.refresh_python_candidates).grid(
            row=0, column=2, sticky="e"
        )
        python_link = ttk.Label(
            prereq,
            text=f"Python link: {PYTHON_313_PAGE_URL}",
            foreground="blue",
            cursor="hand2",
        )
        python_link.grid(row=1, column=1, sticky="w", padx=(8, 8), pady=(8, 0))
        python_link.bind("<Button-1>", lambda _event: self.open_url(PYTHON_313_PAGE_URL))
        self.install_python_gui_button = ttk.Button(
            prereq,
            text="Download and Install Python 3.13",
            command=self.install_python_button,
        )
        self.install_python_gui_button.grid(row=1, column=2, sticky="e", pady=(8, 0))
        ttk.Label(prereq, text="Git for Windows").grid(row=2, column=0, sticky="w", pady=(16, 0))
        git_link = ttk.Label(
            prereq,
            text=f"Git link: {GIT_FOR_WINDOWS_PAGE_URL}",
            foreground="blue",
            cursor="hand2",
        )
        git_link.grid(row=2, column=1, sticky="w", padx=(8, 8), pady=(16, 0))
        git_link.bind("<Button-1>", lambda _event: self.open_url(GIT_FOR_WINDOWS_PAGE_URL))
        self.install_git_gui_button = ttk.Button(
            prereq,
            text="Download and Install Git",
            command=self.install_git_button,
        )
        self.install_git_gui_button.grid(row=2, column=2, sticky="e", pady=(16, 0))
        ttk.Button(prereq, text="Refresh checks", command=self.refresh_status).grid(
            row=3, column=2, sticky="e", pady=(16, 0)
        )
        ttk.Label(
            prereq,
            text="Warning: to run BrightEyes-MCS properly, install the NI driver - NI R Series Multifunction RIO.",
            wraplength=680,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(18, 0))
        ni_link = ttk.Label(
            prereq,
            text=NI_R_SERIES_MRIO_URL,
            foreground="blue",
            cursor="hand2",
        )
        ni_link.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ni_link.bind("<Button-1>", lambda _event: self.open_url(NI_R_SERIES_MRIO_URL))

        source = ttk.LabelFrame(setup, text="BrightEyes-MCS source", padding=10)
        source.grid(row=0, column=0, sticky="ew")
        setup.columnconfigure(0, weight=1)
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Branch").grid(row=0, column=0, sticky="w")
        self.source_branch_box = ttk.Combobox(source, textvariable=self.source_branch_var, state="normal", width=28)
        self.source_branch_box.grid(row=0, column=1, sticky="w", padx=(8, 8))
        self.source_branch_box.bind("<<ComboboxSelected>>", self.on_source_branch_changed)
        ttk.Button(source, text="Refresh branches", command=self.refresh_source_branches).grid(row=0, column=2, padx=(0, 8))
        ttk.Label(source, text="Commit").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(source, textvariable=self.source_commit_var).grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(source, text="Use branch head", command=self.clear_source_commit).grid(row=1, column=2, padx=(0, 8), pady=(8, 0))
        ttk.Button(source, text="Refresh commits", command=self.refresh_source_commits).grid(row=1, column=3, pady=(8, 0))
        ttk.Label(source, text="Recent commits").grid(row=2, column=0, sticky="nw", pady=(8, 0))
        commit_frame = ttk.Frame(source)
        commit_frame.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        commit_frame.columnconfigure(0, weight=1)
        self.source_commit_list = tk.Listbox(commit_frame, height=6, exportselection=False)
        self.source_commit_list.grid(row=0, column=0, sticky="ew")
        self.source_commit_list.bind("<<ListboxSelect>>", self.on_source_commit_selected)
        commit_scroll = ttk.Scrollbar(commit_frame, command=self.source_commit_list.yview)
        commit_scroll.grid(row=0, column=1, sticky="ns")
        self.source_commit_list.configure(yscrollcommand=commit_scroll.set)

        options = ttk.LabelFrame(setup, text="Options", padding=10)
        options.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(options, text="Create links on desktop", variable=self.create_links_var).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(options, text="Stash non-cfg local changes on update", variable=self.stash_local_var).grid(
            row=0, column=1, sticky="w", padx=(16, 0)
        )

        actions = ttk.LabelFrame(setup, text="Actions", padding=10)
        actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.install_button = ttk.Button(actions, text="Install BrightEyes-MCS", command=self.install_button_clicked)
        self.install_button.grid(row=0, column=0)
        self.update_button = ttk.Button(actions, text="Update BrightEyes-MCS", command=self.update_button_clicked)
        self.update_button.grid(row=0, column=1, padx=(8, 0))
        self.links_button = ttk.Button(actions, text="Create links now", command=self.links_button_clicked)
        self.links_button.grid(row=0, column=2, padx=(8, 0))

        firmware.columnconfigure(1, weight=1)
        firmware.rowconfigure(3, weight=1)
        ttk.Label(firmware, text="Firmware branch").grid(row=0, column=0, sticky="w")
        self.branch_box = ttk.Combobox(firmware, textvariable=self.firmware_branch_var, state="normal", width=28)
        self.branch_box.grid(row=0, column=1, sticky="w", padx=(8, 8))
        self.branch_box.bind("<<ComboboxSelected>>", self.on_firmware_branch_changed)
        ttk.Button(firmware, text="Refresh branches", command=self.refresh_firmware_branches).grid(
            row=0, column=2, sticky="e"
        )
        ttk.Label(
            firmware,
            text="By clicking Download firmware now, you confirm that you have read and accept the firmware license shown below.",
            wraplength=680,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.firmware_button = ttk.Button(firmware, text="Download firmware now", command=self.firmware_button_clicked)
        self.firmware_button.grid(row=1, column=2, sticky="e", pady=(12, 0))
        ttk.Label(firmware, text="Firmware LICENSE.md").grid(row=2, column=0, sticky="w", pady=(16, 0))
        ttk.Button(firmware, text="Refresh license", command=self.refresh_firmware_license).grid(
            row=2, column=2, sticky="e", pady=(16, 0)
        )
        firmware_license_frame = ttk.Frame(firmware)
        firmware_license_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        firmware_license_frame.columnconfigure(0, weight=1)
        firmware_license_frame.rowconfigure(0, weight=1)
        self.firmware_license_text = tk.Text(firmware_license_frame, height=10, wrap="word", state="disabled")
        self.firmware_license_text.grid(row=0, column=0, sticky="nsew")
        firmware_license_scrollbar = ttk.Scrollbar(firmware_license_frame, command=self.firmware_license_text.yview)
        firmware_license_scrollbar.grid(row=0, column=1, sticky="ns")
        self.firmware_license_text.configure(yscrollcommand=firmware_license_scrollbar.set)
        self.configure_markdown_text(self.firmware_license_text)

        licenses.columnconfigure(0, weight=1)
        licenses.rowconfigure(0, weight=1)
        license_text = tk.Text(licenses, height=18, wrap="word")
        license_text.grid(row=0, column=0, sticky="nsew")
        license_scrollbar = ttk.Scrollbar(licenses, command=license_text.yview)
        license_scrollbar.grid(row=0, column=1, sticky="ns")
        license_text.configure(yscrollcommand=license_scrollbar.set)
        license_text.insert("1.0", LICENSE_NOTICE)
        license_text.configure(state="disabled")

        log_frame = ttk.Frame(root)
        log_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=16, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def open_url(self, url: str) -> None:
        webbrowser.open_new_tab(url)

    def configure_markdown_text(self, widget: tk.Text) -> None:
        widget.tag_configure("h1", font=("", 13, "bold"), spacing1=6, spacing3=4)
        widget.tag_configure("h2", font=("", 12, "bold"), spacing1=5, spacing3=3)
        widget.tag_configure("h3", font=("", 11, "bold"), spacing1=4, spacing3=2)
        widget.tag_configure("bold", font=("", 10, "bold"))
        widget.tag_configure("bullet", lmargin1=18, lmargin2=34)
        widget.tag_configure("code", font=("Consolas", 9), background="#f2f2f2", lmargin1=8, lmargin2=8)

    def insert_markdown_inline(self, widget: tk.Text, text: str, tags: tuple[str, ...] = ()) -> None:
        position = 0
        for match in re.finditer(r"\*\*(.+?)\*\*", text):
            if match.start() > position:
                widget.insert("end", text[position : match.start()], tags)
            widget.insert("end", match.group(1), tags + ("bold",))
            position = match.end()
        if position < len(text):
            widget.insert("end", text[position:], tags)

    def insert_markdown_text(self, widget: tk.Text, markdown: str) -> None:
        in_code_block = False
        for raw_line in markdown.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                widget.insert("end", raw_line + "\n", ("code",))
                continue

            heading = re.match(r"^(#{1,3})\s+(.+)$", line)
            if heading:
                level = len(heading.group(1))
                self.insert_markdown_inline(widget, heading.group(2).strip(), (f"h{level}",))
                widget.insert("end", "\n", (f"h{level}",))
                continue

            bullet = re.match(r"^\s*[-*+]\s+(.+)$", line)
            if bullet:
                widget.insert("end", "* ", ("bullet",))
                self.insert_markdown_inline(widget, bullet.group(1).strip(), ("bullet",))
                widget.insert("end", "\n", ("bullet",))
                continue

            strong_line = re.match(r"^\*\*(.+)\*\*$", stripped)
            if strong_line:
                widget.insert("end", strong_line.group(1).strip() + "\n", ("bold",))
                continue

            self.insert_markdown_inline(widget, raw_line)
            widget.insert("end", "\n")

    def _python_label(self, candidate: PythonCandidate) -> str:
        version = ".".join(str(part) for part in candidate.version) if candidate.version else "unknown"
        suffix = "  [venv]" if is_venv_python(candidate.command) else ""
        return f"{version}  {candidate.command}{suffix}"

    def python_label_for_command(self, command: str) -> str:
        for candidate in self.python_candidates:
            if candidate.command == command:
                return self._python_label(candidate)
        return command

    def select_python_from_label(self, _event: object = None) -> None:
        text = self.python_box.get()
        for candidate in self.python_candidates:
            if text == self._python_label(candidate):
                self.python_var.set(candidate.command)
                return
        self.python_var.set(text.strip())

    def browse_project_dir(self) -> None:
        selected = filedialog.askdirectory(title="Choose BrightEyes install folder")
        if selected:
            self.project_dir_var.set(selected)
            self.refresh_status()

    def on_project_dir_changed(self, *_args: object) -> None:
        self.refresh_status()

    def log(self, message: str) -> None:
        self.log_queue.put(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        for button in (
            self.install_python_gui_button,
            self.install_git_gui_button,
            self.firmware_button,
        ):
            button.configure(state=state)
        self.update_setup_button_states()

    def update_setup_button_states(self) -> None:
        if self.is_busy:
            self.install_button.configure(state="disabled")
            self.update_button.configure(state="disabled")
            self.links_button.configure(state="disabled")
            return
        project_dir = project_source_dir(Path(self.project_dir_var.get()).expanduser())
        source_exists = source_or_checkout_exists(project_dir)
        self.install_button.configure(state="disabled" if source_exists else "normal")
        self.update_button.configure(state="normal" if source_exists else "disabled")
        self.links_button.configure(state="normal" if source_exists else "disabled")

    def refresh_python_candidates(self) -> None:
        self.python_candidates = discover_python_candidates()
        values = [self._python_label(candidate) for candidate in self.python_candidates]
        self.python_box.configure(values=values)
        selected = best_python_313()
        if selected:
            self.python_var.set(selected)
            self.python_box.set(self.python_label_for_command(selected))
        self.refresh_status()

    def refresh_status(self) -> None:
        project_dir = project_source_dir(Path(self.project_dir_var.get()).expanduser())
        python_text = "Python 3.13 found" if best_python_313() else "Python 3.13 not found"
        if shutil.which("git"):
            git_text = "Git found"
        else:
            git_text = "Git not found"
        checkout_text = "git checkout" if (project_dir / ".git").exists() else "no .git"
        venv_text = ".venv found" if (project_dir / ".venv" / "Scripts" / "python.exe").exists() else "no .venv"
        self.status_var.set(f"{python_text}; {git_text}; {checkout_text}; {venv_text}")
        self.update_setup_button_states()

    def refresh_source_branches(self) -> None:
        fallback_branch = self.source_branch_var.get().strip() or "main"

        def work() -> None:
            branches = list_github_branches(REPO_API_URL, self.log)
            if not branches:
                branches = [fallback_branch]

            def apply() -> None:
                current = self.source_branch_var.get().strip()
                self.source_branch_box.configure(values=branches)
                selected = current if current in branches else branches[0]
                if selected != current:
                    self.clear_source_commit()
                self.source_branch_var.set(selected)
                self.refresh_source_commits()

            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def on_source_branch_changed(self, _event: object = None) -> None:
        self.clear_source_commit()
        self.refresh_source_commits()

    def clear_source_commit(self) -> None:
        self.source_commit_var.set("")
        if hasattr(self, "source_commit_list"):
            self.source_commit_list.selection_clear(0, tk.END)

    def refresh_source_commits(self) -> None:
        branch = self.source_branch_var.get().strip() or "main"

        def work() -> None:
            commits = list_github_commits(REPO_API_URL, branch, self.log)

            def apply() -> None:
                self.source_commit_items = commits
                self.source_commit_list.delete(0, tk.END)
                self.source_commit_list.insert(tk.END, "[latest branch head]")
                for commit in commits:
                    self.source_commit_list.insert(
                        tk.END,
                        f"{commit.short_sha}  {commit.date}  {commit.message}",
                    )
                self.source_commit_list.selection_set(0)

            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def on_source_commit_selected(self, _event: object = None) -> None:
        selection = self.source_commit_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index == 0:
            self.source_commit_var.set("")
            return
        commit_index = index - 1
        if 0 <= commit_index < len(self.source_commit_items):
            self.source_commit_var.set(self.source_commit_items[commit_index].sha)

    def refresh_firmware_branches(self) -> None:
        fallback_branch = self.firmware_branch_var.get().strip() or "main"

        def work() -> None:
            branches = list_github_branches(FIRMWARE_API_URL, self.log)
            if not branches:
                branches = [fallback_branch]

            def apply() -> None:
                current = self.firmware_branch_var.get().strip()
                self.branch_box.configure(values=branches)
                self.firmware_branch_var.set(current if current in branches else branches[0])
                self.refresh_firmware_license()

            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def on_firmware_branch_changed(self, _event: object = None) -> None:
        self.refresh_firmware_license()

    def set_firmware_license_text(self, text: str) -> None:
        self.firmware_license_text.configure(state="normal")
        self.firmware_license_text.delete("1.0", "end")
        self.insert_markdown_text(self.firmware_license_text, text)
        self.firmware_license_text.configure(state="disabled")

    def refresh_firmware_license(self) -> None:
        branch = self.firmware_branch_var.get().strip() or "main"
        self.set_firmware_license_text(f"Loading LICENSE.md from {FIRMWARE_REPO} branch '{branch}'...")

        def work() -> None:
            text = read_github_text_file(FIRMWARE_API_URL, "LICENSE.md", branch, self.log)
            header = f"# {FIRMWARE_REPO} LICENSE.md ({branch})\n\n"

            def apply() -> None:
                if (self.firmware_branch_var.get().strip() or "main") == branch:
                    self.set_firmware_license_text(header + text)

            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def run_background(self, label: str, work: Callable[[], None]) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Another operation is already running.")
            return

        def target() -> None:
            self.after(0, lambda: self.set_busy(True))
            self.log(label)
            try:
                work()
            except Exception as exc:
                message = str(exc)
                self.log("ERROR: " + message)
                self.after(0, lambda: messagebox.showerror(APP_NAME, message))
            else:
                self.log("Done.")
                self.after(0, lambda: messagebox.showinfo(APP_NAME, f"{label} completed."))
            finally:
                self.after(0, self.refresh_status)
                self.after(0, lambda: self.set_busy(False))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def selected_python(self) -> str | None:
        return self.python_var.get().strip() or self.python_box.get().strip() or None

    def selected_project_dir(self) -> Path:
        return project_source_dir(Path(self.project_dir_var.get()).expanduser()).resolve()

    def install_python_button(self) -> None:
        confirmed = messagebox.askyesno(
            APP_NAME,
            "Python 3.13 will be downloaded from python.org.\n\n"
            f"{PYTHON_313_INSTALLER_URL}\n\n"
            "Do you want to continue?",
        )
        if not confirmed:
            self.log("Python 3.13 download cancelled.")
            return
        self.run_background("Install Python 3.13", lambda: open_python_installer(self.log))

    def install_git_button(self) -> None:
        confirmed = messagebox.askyesno(
            APP_NAME,
            "Git for Windows will be downloaded from GitHub.\n\n"
            f"{GIT_FOR_WINDOWS_URL}\n\n"
            "Do you want to continue?",
        )
        if not confirmed:
            self.log("Git for Windows download cancelled.")
            return
        self.run_background("Install Git for Windows", lambda: open_git_installer(self.log))

    def install_button_clicked(self) -> None:
        self.run_background(
            "Install BrightEyes-MCS",
            lambda: install_project(
                self.selected_project_dir(),
                self.selected_python(),
                self.create_links_var.get(),
                None,
                self.source_branch_var.get(),
                self.source_commit_var.get(),
                self.stash_local_var.get(),
                self.log,
            ),
        )

    def update_button_clicked(self) -> None:
        def work() -> None:
            project_dir = self.selected_project_dir()
            update_from_git(
                project_dir,
                self.source_branch_var.get(),
                self.source_commit_var.get(),
                self.stash_local_var.get(),
                self.log,
            )
            install_project(
                project_dir,
                self.selected_python(),
                self.create_links_var.get(),
                None,
                None,
                None,
                self.stash_local_var.get(),
                self.log,
                upgrade_requirements=True,
            )

        self.run_background("Update BrightEyes-MCS", work)

    def firmware_button_clicked(self) -> None:
        confirmed = messagebox.askyesno(
            APP_NAME,
            "The firmware files will be downloaded from BrightEyes-MCSLL.\n\n"
            "By downloading the firmware, you confirm that you have read and accept the firmware license shown in "
            "this tab.\n\n"
            "Do you want to continue?",
        )
        if not confirmed:
            self.log("Firmware download cancelled.")
            return
        self.run_background(
            "Download firmware",
            lambda: download_firmware(self.selected_project_dir(), self.firmware_branch_var.get(), self.log),
        )

    def links_button_clicked(self) -> None:
        def work() -> None:
            project_dir = self.selected_project_dir()
            venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
            if not venv_python.exists():
                raise InstallerError("The .venv Python was not found. Run install first.")
            create_links(project_dir, venv_python, self.log)

        self.run_background("Create links", work)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BrightEyes-MCS standalone installer")
    parser.add_argument("--version", action="version", version="BrightEyes-MCS installer 1.0")
    subparsers = parser.add_subparsers(dest="command")

    gui = subparsers.add_parser("gui", help="Open the Tk GUI")
    gui.set_defaults(func=lambda _args: run_gui())

    install = subparsers.add_parser("install", help="Create .venv, install requirements, links, and firmware")
    install.add_argument("--path", default=".", help="BrightEyes-MCS folder")
    install.add_argument("--python", help="Path to Python 3.13 executable")
    install.add_argument("--source-branch", default="main", help="BrightEyes-MCS git branch to clone/update")
    install.add_argument("--source-commit", help="Optional BrightEyes-MCS commit to checkout after selecting the branch")
    install.add_argument("--stash-local", action="store_true", help="Stash non-cfg local changes when target is a git checkout")
    install.add_argument("--no-links", action="store_true")
    install.add_argument("--no-firmware", action="store_true")
    install.add_argument("--firmware-branch", default="main")
    install.set_defaults(func=cli_install)

    update = subparsers.add_parser("update", help="Update an existing git checkout, then repair the install")
    update.add_argument("--path", default=".", help="BrightEyes-MCS folder")
    update.add_argument("--python", help="Path to Python 3.13 executable")
    update.add_argument("--branch", help="Git branch to update from")
    update.add_argument("--commit", help="Optional commit to checkout after updating the branch")
    update.add_argument("--stash-local", action="store_true")
    update.add_argument("--no-links", action="store_true")
    update.add_argument("--no-firmware", action="store_true")
    update.add_argument("--firmware-branch", default="main")
    update.set_defaults(func=cli_update)

    firmware = subparsers.add_parser("firmware", help="Download firmware from BrightEyes-MCSLL")
    firmware.add_argument("--path", default=".", help="BrightEyes-MCS folder")
    firmware.add_argument("--firmware-branch", default="main")
    firmware.set_defaults(func=cli_firmware)

    links = subparsers.add_parser("links", help="Create BrightEyes-MCS shortcuts")
    links.add_argument("--path", default=".", help="BrightEyes-MCS folder")
    links.set_defaults(func=cli_links)

    python_link = subparsers.add_parser("python-link", help="Download and open the Python 3.13 installer")
    python_link.set_defaults(func=cli_python_link)

    pythons = subparsers.add_parser("pythons", help="List detected Python installations")
    pythons.set_defaults(func=cli_pythons)

    return parser


def run_gui() -> None:
    app = InstallerApp()
    app.mainloop()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        run_gui()
        return 0
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
