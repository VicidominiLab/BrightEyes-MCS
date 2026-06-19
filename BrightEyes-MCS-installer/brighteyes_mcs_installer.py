from __future__ import annotations

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
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable
import tkinter as tk


APP_NAME = "BrightEyes-MCS Installer"
REPO_URL = "https://github.com/VicidominiLab/BrightEyes-MCS"
GITHUB_API_URL = "https://api.github.com/repos/VicidominiLab/BrightEyes-MCS"
GITHUB_ZIP_URL = "https://github.com/VicidominiLab/BrightEyes-MCS/archive/refs/heads/{branch}.zip"
VS_BUILD_TOOLS_URL = "https://aka.ms/vs/17/release/vs_BuildTools.exe"
MSYS2_WINGET_ID = "MSYS2.MSYS2"
MSYS2_GCC_PACKAGE = "mingw-w64-ucrt-x86_64-gcc"
PRESERVED_PATHS = [
    Path("brighteyes_mcs/cfg"),
    Path("brighteyes_mcs/bitfiles"),
]


@dataclass
class PythonCandidate:
    label: str
    command: str
    version: tuple[int, int, int] | None


class InstallError(RuntimeError):
    pass


def default_install_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "BrightEyes-MCS"
    return Path.home() / "BrightEyes-MCS"


def creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


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


def program_exists(name: str) -> bool:
    return shutil.which(name) is not None


def check_vs_build_tools() -> bool:
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere_path = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere_path.exists():
        return False
    result = run_capture(
        [
            str(vswhere_path),
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualCpp.Tools.HostX86.TargetX86",
            "-find",
            r"VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
        ]
    )
    return bool(result.stdout.strip())


def msys2_root() -> Path:
    return Path(os.environ.get("MSYS2_ROOT", r"C:\msys64"))


def check_msys2() -> bool:
    return (msys2_root() / "usr" / "bin" / "bash.exe").exists()


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
            text = line.strip()
            if not text:
                continue
            path_text = path_from_py_launcher_line(text)
            if not path_text:
                continue
            if Path(path_text).exists() and path_text.lower() not in seen:
                seen.add(path_text.lower())
                version = python_version(path_text)
                candidates.append(PythonCandidate(path_text, path_text, version))

    where_python = shutil.which("where")
    if where_python:
        result = run_capture([where_python, "python.exe"])
        for line in result.stdout.splitlines():
            path_text = line.strip()
            if Path(path_text).exists() and path_text.lower() not in seen:
                seen.add(path_text.lower())
                version = python_version(path_text)
                candidates.append(PythonCandidate(path_text, path_text, version))

    current = Path(sys.executable)
    if current.exists() and str(current).lower() not in seen:
        version = python_version(str(current))
        if version:
            candidates.append(PythonCandidate(str(current), str(current), version))

    return candidates


def is_python_313(version: tuple[int, int, int] | None) -> bool:
    return bool(version and version[0] == 3 and version[1] == 13)


def open_vs_build_tools_gui(log: Callable[[str], None]) -> None:
    download_path = Path(tempfile.gettempdir()) / "vs_BuildTools.exe"
    log("Downloading Visual Studio Build Tools bootstrapper...")
    download_file(VS_BUILD_TOOLS_URL, download_path, log)
    log("Opening the Visual Studio Build Tools installer GUI.")
    subprocess.Popen([str(download_path)], creationflags=creationflags())


def install_msys2_silent(log: Callable[[str], None]) -> None:
    if check_msys2():
        log(f"MSYS2 found at {msys2_root()}.")
    else:
        if not program_exists("winget"):
            raise InstallError(
                "MSYS2 is not installed and winget was not found. "
                "Install MSYS2 manually, or install App Installer/winget and try again."
            )
        log("Installing MSYS2 silently with winget...")
        run_logged(
            [
                "winget",
                "install",
                "--id",
                MSYS2_WINGET_ID,
                "--exact",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            None,
            log,
        )

    bash_path = msys2_root() / "usr" / "bin" / "bash.exe"
    if not bash_path.exists():
        raise InstallError(f"MSYS2 bash was not found at {bash_path}.")

    log("Updating MSYS2 packages...")
    run_logged([str(bash_path), "-lc", "pacman --noconfirm -Syu"], None, log)
    log("Installing the MSYS2 UCRT64 GCC compiler...")
    run_logged(
        [str(bash_path), "-lc", f"pacman --noconfirm -Sy --needed {MSYS2_GCC_PACKAGE}"],
        None,
        log,
    )


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
                        percent = int(downloaded * 100 / total_bytes)
                        log(f"Download progress: {percent}%")
    except urllib.error.URLError as exc:
        raise InstallError(f"Download failed: {exc}") from exc


def github_default_branch(log: Callable[[str], None]) -> str:
    request = urllib.request.Request(GITHUB_API_URL, headers={"User-Agent": APP_NAME})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            branch = data.get("default_branch")
            if branch:
                return str(branch)
    except Exception as exc:
        log(f"Could not read GitHub default branch, using main: {exc}")
    return "main"


def copy_preserved_paths(source_root: Path, backup_root: Path, log: Callable[[str], None]) -> list[Path]:
    copied: list[Path] = []
    for relative in PRESERVED_PATHS:
        source = source_root / relative
        if not source.exists():
            continue
        destination = backup_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        copied.append(relative)
    if copied:
        log("Preserved local configuration and bitfiles.")
    return copied


def restore_preserved_paths(
    backup_root: Path,
    target_root: Path,
    copied: list[Path],
    log: Callable[[str], None],
) -> None:
    for relative in copied:
        source = backup_root / relative
        destination = target_root / relative
        if not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
    if copied:
        log("Restored preserved local files.")


def install_source_from_github(target_dir: Path, log: Callable[[str], None]) -> None:
    if target_dir.exists() and any(target_dir.iterdir()):
        raise InstallError(f"The install folder is not empty: {target_dir}")

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if program_exists("git"):
        log("Cloning the latest BrightEyes-MCS source from GitHub...")
        run_logged(["git", "clone", "--depth", "1", REPO_URL, str(target_dir)], None, log)
        return

    branch = github_default_branch(log)
    with tempfile.TemporaryDirectory(prefix="brighteyes_mcs_source_") as temp_name:
        temp_dir = Path(temp_name)
        archive_path = temp_dir / "source.zip"
        extract_dir = temp_dir / "extract"
        log(f"Git was not found. Downloading GitHub archive for branch '{branch}'...")
        download_file(GITHUB_ZIP_URL.format(branch=branch), archive_path, log)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_dir)
        extracted_roots = [path for path in extract_dir.iterdir() if path.is_dir()]
        if not extracted_roots:
            raise InstallError("The GitHub archive did not contain a source folder.")
        shutil.copytree(extracted_roots[0], target_dir, dirs_exist_ok=True)


def update_source_from_github(
    target_dir: Path,
    python_command: str,
    toolchain: str,
    log: Callable[[str], None],
) -> None:
    if not target_dir.exists():
        raise InstallError(f"The install folder does not exist: {target_dir}")

    if (target_dir / ".git").exists():
        log("Updating the installed git checkout.")
        branch = current_git_branch(target_dir) or remote_default_branch(target_dir) or "main"
        args = [python_command, "upgrade_mcs.py", "--branch", branch, "--stash-local", "--no-post-install"]
        run_logged(args, target_dir, log)
        run_project_installer(target_dir, python_command, toolchain, log)
        return

    branch = github_default_branch(log)
    with tempfile.TemporaryDirectory(prefix="brighteyes_mcs_update_") as temp_name:
        temp_dir = Path(temp_name)
        backup_dir = temp_dir / "backup"
        copied = copy_preserved_paths(target_dir, backup_dir, log)
        archive_path = temp_dir / "source.zip"
        extract_dir = temp_dir / "extract"
        log(f"Downloading the latest BrightEyes-MCS archive for branch '{branch}'...")
        download_file(GITHUB_ZIP_URL.format(branch=branch), archive_path, log)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_dir)
        extracted_roots = [path for path in extract_dir.iterdir() if path.is_dir()]
        if not extracted_roots:
            raise InstallError("The GitHub archive did not contain a source folder.")

        log("Replacing source files while preserving local configuration.")
        for item in target_dir.iterdir():
            if item.name == ".venv":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        for item in extracted_roots[0].iterdir():
            destination = target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
        restore_preserved_paths(backup_dir, target_dir, copied, log)

    run_project_installer(target_dir, python_command, toolchain, log)


def current_git_branch(repo_dir: Path) -> str | None:
    result = run_capture(
        ["git", "-c", f"safe.directory={repo_dir.as_posix()}", "branch", "--show-current"],
        cwd=repo_dir,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def remote_default_branch(repo_dir: Path) -> str | None:
    result = run_capture(
        [
            "git",
            "-c",
            f"safe.directory={repo_dir.as_posix()}",
            "symbolic-ref",
            "--quiet",
            "--short",
            "refs/remotes/origin/HEAD",
        ],
        cwd=repo_dir,
    )
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    if "/" in text:
        return text.split("/", 1)[1]
    return text or None


def create_virtual_environment(project_dir: Path, python_command: str, log: Callable[[str], None]) -> Path:
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        log("Using the existing virtual environment.")
        return venv_python

    log("Creating the BrightEyes-MCS virtual environment...")
    run_logged([python_command, "-m", "venv", ".venv"], project_dir, log)
    if not venv_python.exists():
        raise InstallError("Virtual environment creation completed, but .venv Python was not found.")
    return venv_python


def run_project_installer(
    project_dir: Path,
    venv_python: str,
    toolchain: str,
    log: Callable[[str], None],
) -> None:
    args = [venv_python, "installer.py"]
    if toolchain == "vs":
        args.append("--force-vs")
    elif toolchain == "msys2":
        args.append("--force-msys2")
    log("Installing Python requirements and building BrightEyes-MCS extensions...")
    run_logged(args, project_dir, log)


def run_optional_project_script(
    project_dir: Path,
    venv_python: str,
    script_name: str,
    log: Callable[[str], None],
) -> None:
    script_path = project_dir / script_name
    if not script_path.exists():
        log(f"Skipping {script_name}; file not found.")
        return
    log(f"Running {script_name}...")
    run_logged([venv_python, script_name], project_dir, log)


def run_logged(
    command: list[str],
    cwd: Path | None,
    log: Callable[[str], None],
    env: dict[str, str] | None = None,
) -> None:
    log("Running: " + " ".join(f'"{part}"' if " " in part else part for part in command))
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
        raise InstallError(f"Command failed with exit code {return_code}: {' '.join(command)}")


class InstallerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.minsize(800, 600)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.python_candidates = discover_python_candidates()

        self.install_dir_var = tk.StringVar(value=str(default_install_dir()))
        self.python_var = tk.StringVar()
        self.toolchain_var = tk.StringVar(value="vs")
        self.msys2_license_var = tk.BooleanVar(value=False)
        self.create_links_var = tk.BooleanVar(value=True)
        self.download_firmware_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")

        if self.python_candidates:
            preferred = next((item for item in self.python_candidates if is_python_313(item.version)), None)
            self.python_var.set((preferred or self.python_candidates[0]).command)

        self._build_ui()
        self.after(100, self._drain_log_queue)
        self.refresh_status()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(5, weight=1)

        title = ttk.Label(root, text="BrightEyes-MCS install and update manager", font=("", 14, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Label(root, text="Install folder").grid(row=1, column=0, sticky="w")
        ttk.Entry(root, textvariable=self.install_dir_var).grid(row=1, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(root, text="Browse", command=self.browse_install_dir).grid(row=1, column=2, sticky="e")

        ttk.Label(root, text="Python 3.13").grid(row=2, column=0, sticky="w", pady=(8, 0))
        python_values = [self._python_label(candidate) for candidate in self.python_candidates]
        self.python_box = ttk.Combobox(root, values=python_values, state="normal")
        self.python_box.grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        self.python_box.bind("<<ComboboxSelected>>", self._select_python_from_label)
        if self.python_candidates:
            self.python_box.set(self._python_label_for_command(self.python_var.get()))
        ttk.Button(root, text="Browse", command=self.browse_python).grid(row=2, column=2, sticky="e", pady=(8, 0))

        tools = ttk.LabelFrame(root, text="Compiler toolchain", padding=10)
        tools.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        tools.columnconfigure(1, weight=1)

        ttk.Radiobutton(
            tools,
            text="Visual Studio Build Tools",
            value="vs",
            variable=self.toolchain_var,
            command=self.refresh_status,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(tools, text="Open VS Build Tools installer", command=self.open_vs_installer).grid(
            row=0, column=1, sticky="e"
        )

        ttk.Radiobutton(
            tools,
            text="MSYS2 UCRT64",
            value="msys2",
            variable=self.toolchain_var,
            command=self.refresh_status,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(tools, text="Install MSYS2 silently", command=self.install_msys2_button).grid(
            row=1, column=1, sticky="e", pady=(8, 0)
        )
        ttk.Checkbutton(
            tools,
            text="I accept the MSYS2 license and package license notices for silent installation",
            variable=self.msys2_license_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        options = ttk.Frame(root)
        options.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(options, text="Create desktop links", variable=self.create_links_var).grid(row=0, column=0)
        ttk.Checkbutton(options, text="Download firmware", variable=self.download_firmware_var).grid(
            row=0, column=1, padx=(16, 0)
        )

        log_frame = ttk.Frame(root)
        log_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=16, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(root)
        footer.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.install_button = ttk.Button(footer, text="Install latest", command=self.install_latest)
        self.install_button.grid(row=0, column=1, padx=(8, 0))
        self.update_button = ttk.Button(footer, text="Update existing", command=self.update_existing)
        self.update_button.grid(row=0, column=2, padx=(8, 0))
        ttk.Button(footer, text="Refresh", command=self.refresh_status).grid(row=0, column=3, padx=(8, 0))

    def _python_label(self, candidate: PythonCandidate) -> str:
        version = ".".join(str(part) for part in candidate.version) if candidate.version else "unknown"
        return f"{version}  {candidate.command}"

    def _python_label_for_command(self, command: str) -> str:
        for candidate in self.python_candidates:
            if candidate.command == command:
                return self._python_label(candidate)
        return command

    def _select_python_from_label(self, _event: object = None) -> None:
        text = self.python_box.get()
        for candidate in self.python_candidates:
            if text == self._python_label(candidate):
                self.python_var.set(candidate.command)
                return
        self.python_var.set(text.strip())

    def browse_install_dir(self) -> None:
        selected = filedialog.askdirectory(title="Choose BrightEyes-MCS install folder")
        if selected:
            self.install_dir_var.set(selected)
            self.refresh_status()

    def browse_python(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose Python 3.13 executable",
            filetypes=[("Python executable", "python.exe"), ("All files", "*.*")],
        )
        if selected:
            self.python_var.set(selected)
            self.python_box.set(selected)

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

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
        state = "disabled" if busy else "normal"
        self.install_button.configure(state=state)
        self.update_button.configure(state=state)

    def refresh_status(self) -> None:
        install_dir = Path(self.install_dir_var.get()).expanduser()
        existing = "installed" if (install_dir / "brighteyes_mcs").exists() else "not installed"
        vs = "found" if check_vs_build_tools() else "not found"
        msys2 = "found" if check_msys2() else "not found"
        self.status_var.set(f"Status: BrightEyes-MCS {existing}; VS Build Tools {vs}; MSYS2 {msys2}")

    def open_vs_installer(self) -> None:
        self.run_background("Open Visual Studio Build Tools installer", lambda: open_vs_build_tools_gui(self.log))

    def install_msys2_button(self) -> None:
        if not self.msys2_license_var.get():
            messagebox.showwarning(APP_NAME, "Accept the MSYS2 license notice before silent installation.")
            return
        self.run_background("Install MSYS2", lambda: install_msys2_silent(self.log))

    def install_latest(self) -> None:
        self.run_background("Install BrightEyes-MCS", self._install_latest)

    def update_existing(self) -> None:
        self.run_background("Update BrightEyes-MCS", self._update_existing)

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
                error_message = str(exc)
                self.log(f"ERROR: {error_message}")
                self.after(0, lambda: messagebox.showerror(APP_NAME, error_message))
            else:
                self.log("Done.")
                self.after(0, lambda: messagebox.showinfo(APP_NAME, f"{label} completed."))
            finally:
                self.after(0, self.refresh_status)
                self.after(0, lambda: self.set_busy(False))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def validate_inputs(self) -> tuple[Path, str, str]:
        install_dir = Path(self.install_dir_var.get()).expanduser()
        python_command = self.python_var.get().strip() or self.python_box.get().strip()
        toolchain = self.toolchain_var.get()

        if not python_command:
            raise InstallError("Choose a Python 3.13 executable.")
        version = python_version(python_command)
        if not is_python_313(version):
            found = ".".join(str(part) for part in version) if version else "unknown"
            raise InstallError(f"BrightEyes-MCS expects Python 3.13. Selected Python version: {found}.")

        if toolchain == "vs" and not check_vs_build_tools():
            open_vs_build_tools_gui(self.log)
            raise InstallError("Visual Studio Build Tools was not found. Complete the GUI installer, then run again.")

        if toolchain == "msys2":
            if not self.msys2_license_var.get():
                raise InstallError("Accept the MSYS2 license notice before using MSYS2.")
            install_msys2_silent(self.log)

        return install_dir, python_command, toolchain

    def _install_latest(self) -> None:
        install_dir, python_command, toolchain = self.validate_inputs()
        install_source_from_github(install_dir, self.log)
        venv_python = create_virtual_environment(install_dir, python_command, self.log)
        run_project_installer(install_dir, str(venv_python), toolchain, self.log)
        if self.create_links_var.get():
            run_optional_project_script(install_dir, str(venv_python), "create_links.py", self.log)
        if self.download_firmware_var.get():
            run_optional_project_script(install_dir, str(venv_python), "download_firmware.py", self.log)

    def _update_existing(self) -> None:
        install_dir, python_command, toolchain = self.validate_inputs()
        venv_python = install_dir / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            venv_python = create_virtual_environment(install_dir, python_command, self.log)
        update_source_from_github(install_dir, str(venv_python), toolchain, self.log)


def main() -> int:
    app = InstallerApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
