from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parent
SAFE_DIRECTORY = REPO_ROOT.as_posix()
PRESERVED_PATHS = [
    Path("brighteyes_mcs/cfg"),
    Path("brighteyes_mcs/bitfiles"),
    Path("upgrade_mcs.py"),
    Path("update.bat"),
]
COPY_OVER_TARGET_PATHS = [
    Path("brighteyes_mcs/cfg"),
    Path("brighteyes_mcs/bitfiles"),
    Path("update.bat"),
]
RESTORE_IF_MISSING_PATHS = [
    Path("upgrade_mcs.py"),
]
CLEAR_BEFORE_CHECKOUT = [
    Path("brighteyes_mcs/cfg"),
    Path("brighteyes_mcs/bitfiles"),
]
CYTHON_WATCH_PATHS = [
    "setup.py",
    "installer.py",
    "brighteyes_mcs/libs/cython",
]
COMPILE_SCRIPT = Path("compile_cython.bat")


class UpgradeError(RuntimeError):
    """Raised when the upgrade workflow cannot continue safely."""


class GitCommandError(UpgradeError):
    """Raised when a git command fails."""

    def __init__(self, command: list[str], result: subprocess.CompletedProcess[str]):
        message = f"Command failed ({result.returncode}): {' '.join(command)}"
        details = (result.stderr or result.stdout or "").strip()
        if details:
            message = f"{message}\n{details}"
        super().__init__(message)
        self.command = command
        self.result = result


@dataclass
class BranchInfo:
    name: str
    sha: str
    date: str
    subject: str
    local_ref: str | None = None
    remote_ref: str | None = None


@dataclass
class CommitInfo:
    sha: str
    short_sha: str
    date: str
    subject: str


@dataclass
class StatusEntry:
    code: str
    raw_path: str

    @property
    def paths(self) -> list[str]:
        if " -> " in self.raw_path:
            return [part.strip() for part in self.raw_path.split(" -> ")]
        return [self.raw_path.strip()]


@dataclass
class UpgradeSelection:
    branch: str | None
    commit: str | None
    stash_local: bool
    no_post_install: bool
    no_fetch: bool
    gui_used: bool = False


@dataclass
class UpgradeResult:
    old_head: str
    new_head: str
    branch: str | None
    commit: str | None
    stash_ref: str | None
    backup_dir: Path
    preserved_restored: list[str]
    fetch_succeeded: bool
    requirements_refreshed: bool
    cython_rebuilt: bool


def print_log(message: str) -> None:
    print(message, flush=True)


def run_command(
    command: list[str],
    *,
    cwd: Path = REPO_ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise GitCommandError(command, result)
    return result


def run_passthrough(command: list[str], log: Callable[[str], None]) -> None:
    log("Running: " + " ".join(command))
    result = subprocess.run(command, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise UpgradeError(f"Command failed ({result.returncode}): {' '.join(command)}")


def run_compile_cython(log: Callable[[str], None]) -> None:
    compile_script = REPO_ROOT / COMPILE_SCRIPT
    if compile_script.exists():
        log("Running the Cython compilation script...")
        run_passthrough(["cmd", "/c", str(COMPILE_SCRIPT)], log)
        return

    log("compile_cython.bat not found. Falling back to installer.py for Cython compilation...")
    run_passthrough(
        [sys.executable, "installer.py", "--no--install-requirements", "--do-not-upgrade-msys2"],
        log,
    )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["git", "-c", f"safe.directory={SAFE_DIRECTORY}", *args]
    return run_command(command, check=check)


def git_output(*args: str, check: bool = True) -> str:
    return git(*args, check=check).stdout.strip()


def normalize_branch_name(name: str | None) -> str | None:
    if not name:
        return None
    branch = name.strip()
    if branch.startswith("origin/"):
        branch = branch.split("/", 1)[1]
    return branch or None


def ref_exists(ref_name: str) -> bool:
    result = git("rev-parse", "--verify", "--quiet", f"{ref_name}^{{commit}}", check=False)
    return result.returncode == 0


def branch_exists_local(branch: str) -> bool:
    return ref_exists(f"refs/heads/{branch}")


def branch_exists_remote(branch: str) -> bool:
    return ref_exists(f"refs/remotes/origin/{branch}")


def resolve_branch_ref(branch: str) -> str:
    if branch_exists_remote(branch):
        return f"origin/{branch}"
    if branch_exists_local(branch):
        return branch
    raise UpgradeError(f"Branch '{branch}' was not found locally or on origin.")


def resolve_commit(commit: str) -> str:
    output = git_output("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}", check=False)
    if not output:
        raise UpgradeError(f"Commit '{commit}' was not found.")
    return output.splitlines()[-1].strip()


def get_current_branch() -> str | None:
    branch = git_output("rev-parse", "--abbrev-ref", "HEAD")
    return None if branch == "HEAD" else branch


def get_current_head() -> str:
    return git_output("rev-parse", "HEAD")


def get_current_short_head() -> str:
    return git_output("rev-parse", "--short", "HEAD")


def get_default_branch(branches: list[BranchInfo]) -> str | None:
    head_ref = git_output("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    if head_ref:
        return head_ref.rsplit("/", 1)[-1]
    current = get_current_branch()
    if current:
        return current
    if branches:
        return branches[0].name
    return None


def fetch_remote(log: Callable[[str], None]) -> bool:
    log("Refreshing git references from origin...")
    result = git("fetch", "--all", "--prune", "--tags", check=False)
    if result.returncode == 0:
        log("Git references refreshed.")
        return True
    message = (result.stderr or result.stdout or "").strip()
    if message:
        log("Warning: git fetch failed.")
        log(message)
    else:
        log("Warning: git fetch failed.")
    return False


def list_branches() -> list[BranchInfo]:
    branch_map: dict[str, BranchInfo] = {}
    for ref_root, is_remote in (("refs/remotes/origin", True), ("refs/heads", False)):
        output = git_output(
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname:short)|%(committerdate:short)|%(objectname:short)|%(subject)",
            ref_root,
        )
        for line in output.splitlines():
            ref_name, date, sha, subject = line.split("|", 3)
            if ref_name == "origin/HEAD":
                continue
            if is_remote and "/" not in ref_name:
                continue
            branch_name = ref_name.split("/", 1)[1] if is_remote else ref_name
            info = branch_map.get(branch_name)
            if info is None:
                info = BranchInfo(
                    name=branch_name,
                    sha=sha,
                    date=date,
                    subject=subject,
                )
                branch_map[branch_name] = info
            if is_remote:
                info.remote_ref = ref_name
                info.sha = sha
                info.date = date
                info.subject = subject
            else:
                info.local_ref = ref_name
                if info.remote_ref is None:
                    info.sha = sha
                    info.date = date
                    info.subject = subject
    return sorted(branch_map.values(), key=lambda item: (item.date, item.name), reverse=True)


def list_commits(ref_name: str, limit: int = 15) -> list[CommitInfo]:
    output = git_output(
        "log",
        f"-n{limit}",
        "--date=short",
        "--pretty=format:%H|%h|%ad|%s",
        ref_name,
    )
    commits: list[CommitInfo] = []
    for line in output.splitlines():
        sha, short_sha, date, subject = line.split("|", 3)
        commits.append(CommitInfo(sha=sha, short_sha=short_sha, date=date, subject=subject))
    return commits


def list_status_entries() -> list[StatusEntry]:
    output = git_output("status", "--porcelain", "--untracked-files=all")
    entries: list[StatusEntry] = []
    for line in output.splitlines():
        if not line:
            continue
        entries.append(StatusEntry(code=line[:2], raw_path=line[3:]))
    return entries


def normalize_status_path(path_text: str) -> str:
    return path_text.strip().strip('"').replace("\\", "/")


def is_preserved_path(path_text: str) -> bool:
    normalized = normalize_status_path(path_text)
    for preserved in PRESERVED_PATHS:
        preserved_text = preserved.as_posix()
        if normalized == preserved_text or normalized.startswith(preserved_text + "/"):
            return True
    return False


def get_blocking_changes() -> list[StatusEntry]:
    entries = list_status_entries()
    blocking: list[StatusEntry] = []
    for entry in entries:
        if not entry.paths:
            continue
        if all(is_preserved_path(path) for path in entry.paths):
            continue
        blocking.append(entry)
    return blocking


def stash_local_changes(log: Callable[[str], None]) -> str | None:
    before = git_output("stash", "list", "-n", "1", check=False)
    message = "upgrade_mcs automatic stash"
    result = git("stash", "push", "--include-untracked", "-m", message, check=False)
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    if "No local changes to save" in combined:
        return None
    if result.returncode != 0:
        raise UpgradeError((result.stderr or result.stdout or "").strip() or "git stash failed.")
    after = git_output("stash", "list", "-n", "1", check=False)
    if after and after != before:
        stash_ref = after.split(":", 1)[0].strip()
        log(f"Stored unrelated local changes in {stash_ref}.")
        return stash_ref
    return None


def handle_remove_readonly(func, path, exc_info) -> None:  # type: ignore[no-untyped-def]
    os.chmod(path, stat.S_IWRITE)
    func(path)


def backup_preserved_paths(log: Callable[[str], None]) -> tuple[Path, list[str]]:
    backup_dir = Path(tempfile.mkdtemp(prefix="upgrade_mcs_"))
    copied: list[str] = []
    for relative in PRESERVED_PATHS:
        source = REPO_ROOT / relative
        if not source.exists():
            continue
        destination = backup_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        copied.append(relative.as_posix())
    if copied:
        log("Backup created in: " + str(backup_dir))
    return backup_dir, copied


def remove_checkout_conflicts(log: Callable[[str], None]) -> None:
    for relative in CLEAR_BEFORE_CHECKOUT:
        target = REPO_ROOT / relative
        if not target.exists():
            continue
        log("Temporarily moving aside: " + relative.as_posix())
        if target.is_dir():
            shutil.rmtree(target, onerror=handle_remove_readonly)
        else:
            target.unlink()


def restore_preserved_paths(backup_dir: Path, log: Callable[[str], None]) -> list[str]:
    restored: list[str] = []
    for relative in COPY_OVER_TARGET_PATHS:
        source = backup_dir / relative
        if not source.exists():
            continue
        destination = REPO_ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        restored.append(relative.as_posix())
    for relative in RESTORE_IF_MISSING_PATHS:
        source = backup_dir / relative
        if not source.exists():
            continue
        destination = REPO_ROOT / relative
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        restored.append(relative.as_posix())
    if restored:
        log("Restored preserved paths.")
    return restored


def cleanup_backup_dir(backup_dir: Path) -> None:
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)


def branch_contains_commit(branch: str, commit: str) -> bool | None:
    try:
        branch_ref = resolve_branch_ref(branch)
    except UpgradeError:
        return None
    result = git("merge-base", "--is-ancestor", commit, branch_ref, check=False)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def checkout_target(branch: str | None, commit: str | None, log: Callable[[str], None]) -> tuple[str | None, str]:
    if branch and commit:
        relation = branch_contains_commit(branch, commit)
        if relation is False:
            log(
                f"Warning: commit {commit[:8]} is not reachable from branch {branch}. "
                "Continuing with the explicit commit."
            )
    if branch and not commit:
        if branch_exists_local(branch):
            log(f"Checking out local branch '{branch}'...")
            git("checkout", branch)
        elif branch_exists_remote(branch):
            log(f"Creating local branch '{branch}' from origin/{branch}...")
            git("checkout", "-B", branch, f"origin/{branch}")
        else:
            raise UpgradeError(f"Branch '{branch}' was not found.")
        if branch_exists_remote(branch):
            log(f"Pulling the latest changes from origin/{branch}...")
            git("pull", "--ff-only", "origin", branch)
        new_head = get_current_head()
        return branch, new_head

    if commit:
        resolved_commit = resolve_commit(commit)
        log(f"Checking out commit {resolved_commit[:8]}...")
        git("checkout", resolved_commit)
        return None, resolved_commit

    raise UpgradeError("Nothing to upgrade: choose a branch, a commit, or both.")


def get_changed_files(old_head: str, new_head: str, *paths: str) -> list[str]:
    output = git_output("diff", "--name-only", old_head, new_head, "--", *paths)
    return [line.strip() for line in output.splitlines() if line.strip()]


def run_post_install_if_needed(
    old_head: str,
    new_head: str,
    selection: UpgradeSelection,
    log: Callable[[str], None],
) -> tuple[bool, bool]:
    if selection.no_post_install:
        log("Post-install step skipped by request.")
        return False, False

    requirements_changed = bool(get_changed_files(old_head, new_head, "requirements.txt"))
    cython_changed = bool(get_changed_files(old_head, new_head, *CYTHON_WATCH_PATHS))

    if requirements_changed:
        log("requirements.txt changed. Updating the active Python environment...")
        run_passthrough([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], log)
    elif cython_changed:
        log("Cython build files changed. Running the compilation step...")
    else:
        log("No requirements change detected. Running the Cython compilation step after the update...")

    run_compile_cython(log)
    return requirements_changed, True


def describe_current_state() -> str:
    branch = get_current_branch()
    short_head = get_current_short_head()
    if branch:
        return f"{branch} @ {short_head}"
    return f"detached HEAD @ {short_head}"


def resolve_positional_selection(
    target: str | None,
    commit: str | None,
    branch_names: set[str],
) -> tuple[str | None, str | None]:
    branch = None
    explicit_commit = commit
    if target:
        normalized = normalize_branch_name(target)
        if normalized in branch_names:
            branch = normalized
        elif commit is None:
            explicit_commit = target
        else:
            raise UpgradeError(
                "When two positional arguments are provided, the first one must be a valid branch name."
            )
    return branch, explicit_commit


def parse_menu_choice(choice: str, options: list[str], default_value: str | None) -> str | None:
    text = choice.strip()
    if not text:
        return default_value
    if text.lower() in {"q", "quit", "exit"}:
        raise KeyboardInterrupt
    if text.isdigit():
        index = int(text)
        if 1 <= index <= len(options):
            return options[index - 1]
    if text in options:
        return text
    normalized = normalize_branch_name(text)
    if normalized in options:
        return normalized
    raise UpgradeError(f"'{text}' is not a valid selection.")


def choose_with_cli(
    branches: list[BranchInfo],
    default_branch: str | None,
    no_post_install: bool,
    no_fetch: bool,
) -> UpgradeSelection:
    print("Current version:", describe_current_state())
    print()
    print("Branches:")
    branch_names = [branch.name for branch in branches]
    for index, branch in enumerate(branches, start=1):
        remote_marker = "origin" if branch.remote_ref else "local"
        print(f"[{index:2}] {branch.name:20} {branch.sha:8} {branch.date} {remote_marker}  {branch.subject}")
    print()

    selected_branch = parse_menu_choice(
        input(f"Choose a branch [default {default_branch or 'none'}]: "),
        branch_names,
        default_branch,
    )

    if not selected_branch:
        raise UpgradeError("A branch is required for interactive mode.")

    commits = list_commits(resolve_branch_ref(selected_branch))
    print()
    print(f"Recent commits on {selected_branch}:")
    print("[ 0] Latest branch head")
    for index, commit in enumerate(commits, start=1):
        print(f"[{index:2}] {commit.short_sha:8} {commit.date}  {commit.subject}")
    print()

    selected_commit: str | None = None
    commit_choice = input("Choose a commit [default 0]: ").strip()
    if commit_choice and commit_choice not in {"0"}:
        if commit_choice.isdigit():
            commit_index = int(commit_choice)
            if 1 <= commit_index <= len(commits):
                selected_commit = commits[commit_index - 1].sha
            else:
                raise UpgradeError("The selected commit number is out of range.")
        else:
            selected_commit = resolve_commit(commit_choice)

    blocking_changes = get_blocking_changes()
    stash_local = False
    if blocking_changes:
        print()
        print("Other local changes were found outside the preserved folders:")
        for entry in blocking_changes[:10]:
            print(f"  {entry.code} {entry.raw_path}")
        if len(blocking_changes) > 10:
            print(f"  ... and {len(blocking_changes) - 10} more")
        answer = input("Stash those extra changes before upgrading? [y/N]: ").strip().lower()
        stash_local = answer in {"y", "yes"}

    return UpgradeSelection(
        branch=selected_branch,
        commit=selected_commit,
        stash_local=stash_local,
        no_post_install=no_post_install,
        no_fetch=no_fetch,
        gui_used=False,
    )


def choose_with_gui(
    branches: list[BranchInfo],
    default_branch: str | None,
    no_post_install: bool,
    no_fetch: bool,
) -> UpgradeSelection | None:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception:
        return None

    if not branches and not default_branch:
        raise UpgradeError("No branches were found in this repository.")

    branch_names = [branch.name for branch in branches]
    initial_branch = default_branch or (branch_names[0] if branch_names else "")
    selected: dict[str, object] = {}
    commit_items: list[CommitInfo] = []

    try:
        root = tk.Tk()
    except tk.TclError:
        return None
    root.title("BrightEyes-MCS Upgrade")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=12)
    frame.grid(sticky="nsew")

    ttk.Label(frame, text="Current version").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=describe_current_state()).grid(row=0, column=1, sticky="w", pady=(0, 8))

    ttk.Label(frame, text="Branch").grid(row=1, column=0, sticky="w")
    branch_var = tk.StringVar(value=initial_branch)
    branch_box = ttk.Combobox(frame, textvariable=branch_var, values=branch_names, state="readonly", width=32)
    branch_box.grid(row=1, column=1, sticky="we", pady=(0, 8))

    ttk.Label(frame, text="Recent commits").grid(row=2, column=0, sticky="nw")
    commit_list = tk.Listbox(frame, width=60, height=10, exportselection=False)
    commit_list.grid(row=2, column=1, sticky="we")

    use_commit_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Use the selected commit", variable=use_commit_var).grid(
        row=3, column=1, sticky="w", pady=(6, 0)
    )

    stash_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Stash other local changes", variable=stash_var).grid(
        row=4, column=1, sticky="w", pady=(6, 0)
    )

    no_post_var = tk.BooleanVar(value=no_post_install)
    ttk.Checkbutton(frame, text="Skip post-install refresh", variable=no_post_var).grid(
        row=5, column=1, sticky="w", pady=(6, 0)
    )

    no_fetch_var = tk.BooleanVar(value=no_fetch)
    ttk.Checkbutton(frame, text="Skip git fetch", variable=no_fetch_var).grid(
        row=6, column=1, sticky="w", pady=(6, 0)
    )

    def reload_commits(*_args) -> None:
        branch_name = branch_var.get().strip()
        commit_list.delete(0, tk.END)
        commit_list.insert(tk.END, "[latest branch head]")
        commit_items.clear()
        if not branch_name:
            return
        try:
            for commit in list_commits(resolve_branch_ref(branch_name)):
                commit_items.append(commit)
                commit_list.insert(tk.END, f"{commit.short_sha}  {commit.date}  {commit.subject}")
        except Exception as exc:
            messagebox.showerror("BrightEyes-MCS Upgrade", str(exc), parent=root)

    def submit() -> None:
        branch_name = branch_var.get().strip()
        if not branch_name:
            messagebox.showwarning("BrightEyes-MCS Upgrade", "Choose a branch first.", parent=root)
            return
        commit_sha = None
        if use_commit_var.get():
            selection = commit_list.curselection()
            if not selection:
                messagebox.showwarning("BrightEyes-MCS Upgrade", "Select a commit or disable the checkbox.", parent=root)
                return
            commit_index = selection[0]
            if commit_index > 0:
                commit_sha = commit_items[commit_index - 1].sha
        selected.update(
            {
                "branch": branch_name,
                "commit": commit_sha,
                "stash_local": bool(stash_var.get()),
                "no_post_install": bool(no_post_var.get()),
                "no_fetch": bool(no_fetch_var.get()),
            }
        )
        root.destroy()

    def cancel() -> None:
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=7, column=1, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text="Upgrade", command=submit).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Cancel", command=cancel).grid(row=0, column=1)

    frame.columnconfigure(1, weight=1)
    branch_box.bind("<<ComboboxSelected>>", reload_commits)
    reload_commits()
    commit_list.selection_set(0)
    root.mainloop()

    if not selected:
        return None

    return UpgradeSelection(
        branch=str(selected["branch"]),
        commit=selected["commit"] if selected["commit"] else None,
        stash_local=bool(selected["stash_local"]),
        no_post_install=bool(selected["no_post_install"]),
        no_fetch=bool(selected["no_fetch"]),
        gui_used=True,
    )


def print_available_versions(branches: list[BranchInfo], default_branch: str | None) -> None:
    print("Current version:", describe_current_state())
    print()
    print("Available branches:")
    for branch in branches:
        print(f"  {branch.name:20} {branch.sha:8} {branch.date}  {branch.subject}")
    if default_branch:
        print()
        print(f"Default branch: {default_branch}")
        print()
        print(f"Recent commits on {default_branch}:")
        for commit in list_commits(resolve_branch_ref(default_branch)):
            print(f"  {commit.short_sha:8} {commit.date}  {commit.subject}")


def ensure_safe_worktree(selection: UpgradeSelection) -> str | None:
    blocking_changes = get_blocking_changes()
    if not blocking_changes:
        return None
    if selection.stash_local:
        return "needs_stash"

    preview = "\n".join(f"  {entry.code} {entry.raw_path}" for entry in blocking_changes[:10])
    more = ""
    if len(blocking_changes) > 10:
        more = f"\n  ... and {len(blocking_changes) - 10} more"
    raise UpgradeError(
        "Other local changes were found outside the preserved folders.\n"
        "Commit or stash them first, or rerun with --stash-local.\n"
        f"{preview}{more}"
    )


def perform_upgrade(selection: UpgradeSelection, log: Callable[[str], None]) -> UpgradeResult:
    old_head = get_current_head()
    fetch_succeeded = True
    if not selection.no_fetch:
        fetch_succeeded = fetch_remote(log)

    backup_dir, copied_paths = backup_preserved_paths(log)
    stash_ref: str | None = None
    preserved_restored: list[str] = []

    try:
        worktree_state = ensure_safe_worktree(selection)
        if worktree_state == "needs_stash":
            stash_ref = stash_local_changes(log)

        remove_checkout_conflicts(log)
        actual_branch, new_head = checkout_target(selection.branch, selection.commit, log)
        preserved_restored = restore_preserved_paths(backup_dir, log)
        requirements_refreshed, cython_rebuilt = run_post_install_if_needed(old_head, new_head, selection, log)
    except Exception:
        try:
            restore_preserved_paths(backup_dir, log)
        finally:
            if copied_paths:
                log("The backup is still available in: " + str(backup_dir))
        raise
    else:
        cleanup_backup_dir(backup_dir)
        return UpgradeResult(
            old_head=old_head,
            new_head=new_head,
            branch=actual_branch,
            commit=selection.commit,
            stash_ref=stash_ref,
            backup_dir=backup_dir,
            preserved_restored=preserved_restored,
            fetch_succeeded=fetch_succeeded,
            requirements_refreshed=requirements_refreshed,
            cython_rebuilt=cython_rebuilt,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upgrade BrightEyes-MCS from git while preserving brighteyes_mcs/cfg "
            "and brighteyes_mcs/bitfiles."
        )
    )
    parser.add_argument("target", nargs="?", help="Branch name, or a commit hash when used alone.")
    parser.add_argument("commit", nargs="?", help="Optional commit hash to checkout after choosing a branch.")
    parser.add_argument("--branch", help="Branch to update to.")
    parser.add_argument("--commit-hash", dest="commit_hash", help="Commit hash to checkout.")
    parser.add_argument("--list", action="store_true", help="List branches and recent commits, then exit.")
    parser.add_argument("--cli", action="store_true", help="Force text-mode selection instead of the GUI.")
    parser.add_argument("--gui", action="store_true", help="Force the selection GUI.")
    parser.add_argument("--stash-local", action="store_true", help="Stash unrelated local changes before upgrading.")
    parser.add_argument("--no-post-install", action="store_true", help="Skip requirements and Cython refresh.")
    parser.add_argument("--no-fetch", action="store_true", help="Skip git fetch before listing and upgrading.")
    return parser.parse_args()


def show_message_box(title: str, message: str, error: bool = False) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        return
    try:
        root = tk.Tk()
    except tk.TclError:
        return
    root.withdraw()
    if error:
        messagebox.showerror(title, message, parent=root)
    else:
        messagebox.showinfo(title, message, parent=root)
    root.destroy()


def main() -> int:
    if REPO_ROOT != Path.cwd():
        os.chdir(REPO_ROOT)

    args = parse_args()
    if not args.no_fetch:
        fetch_remote(print_log)

    branches = list_branches()
    branch_names = {branch.name for branch in branches}
    default_branch = get_default_branch(branches)

    if args.list:
        print_available_versions(branches, default_branch)
        return 0

    positional_branch, positional_commit = resolve_positional_selection(args.target, args.commit, branch_names)
    branch = normalize_branch_name(args.branch) or positional_branch
    commit = args.commit_hash or positional_commit

    selection: UpgradeSelection | None
    if branch or commit:
        selection = UpgradeSelection(
            branch=branch if branch else (None if commit else default_branch),
            commit=commit,
            stash_local=args.stash_local,
            no_post_install=args.no_post_install,
            no_fetch=args.no_fetch,
            gui_used=False,
        )
    else:
        if args.cli and args.gui:
            raise UpgradeError("Choose only one of --cli or --gui.")
        if args.cli:
            selection = choose_with_cli(
                branches,
                default_branch,
                no_post_install=args.no_post_install,
                no_fetch=args.no_fetch,
            )
        else:
            selection = choose_with_gui(
                branches,
                default_branch,
                no_post_install=args.no_post_install,
                no_fetch=args.no_fetch,
            )
            if selection is None:
                selection = choose_with_cli(
                    branches,
                    default_branch,
                    no_post_install=args.no_post_install,
                    no_fetch=args.no_fetch,
                )

    if not selection.branch and not selection.commit:
        raise UpgradeError("Nothing selected.")

    result = perform_upgrade(selection, print_log)
    target_text = selection.commit[:8] if selection.commit else (selection.branch or "detached HEAD")

    print()
    print("Upgrade completed successfully.")
    print(f"Previous HEAD: {result.old_head[:8]}")
    print(f"Current  HEAD: {result.new_head[:8]}")
    print(f"Selected target: {target_text}")
    print(f"Current state: {describe_current_state()}")
    if not result.fetch_succeeded:
        print("Fetch note: the upgrade used locally available git refs because git fetch failed.")
    if result.stash_ref:
        print(f"Local changes stash: {result.stash_ref}")
    if result.requirements_refreshed:
        print("requirements.txt was refreshed.")
    if result.cython_rebuilt:
        print("Cython extensions were rebuilt.")
    if selection.gui_used:
        show_message_box(
            "BrightEyes-MCS Upgrade",
            f"Upgrade completed.\nCurrent version: {describe_current_state()}",
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
        print("Upgrade cancelled.")
        raise SystemExit(1)
    except Exception as exc:
        print("Upgrade failed:", exc, file=sys.stderr)
        show_message_box("BrightEyes-MCS Upgrade", str(exc), error=True)
        raise SystemExit(1)
