"""Download and safely extract BrightEyes-MCSLL firmware archives."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from urllib.parse import quote
from zipfile import ZipFile, ZipInfo

import requests


FIRMWARE_REPOSITORY = "https://github.com/VicidominiLab/BrightEyes-MCSLL"
FIRMWARE_LICENSE_URL = f"{FIRMWARE_REPOSITORY}/blob/main/LICENSE.md"
DEFAULT_FIRMWARE_BRANCH = "main"
_BRANCH_PATTERN = re.compile(r"[A-Za-z0-9._/-]+")


class FirmwareArchiveError(ValueError):
    """Raised for an invalid branch or unsafe firmware archive."""


def validate_branch(branch: str) -> str:
    """Return a normalized Git branch name suitable for an archive URL."""

    selected = branch.strip()
    parts = selected.split("/")
    if (
        not selected
        or not _BRANCH_PATTERN.fullmatch(selected)
        or selected.startswith("/")
        or selected.endswith("/")
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise FirmwareArchiveError(
            "Enter a valid branch name using letters, numbers, '.', '_', '-', and '/'."
        )
    return selected


def firmware_archive_url(branch: str) -> str:
    """Return GitHub's ZIP archive URL for a BrightEyes-MCSLL branch."""

    selected = validate_branch(branch)
    return f"{FIRMWARE_REPOSITORY}/archive/refs/heads/{quote(selected, safe='/')}.zip"


def _safe_members(archive: ZipFile) -> list[tuple[ZipInfo, tuple[str, ...]]]:
    members: list[tuple[ZipInfo, tuple[str, ...]]] = []
    for member in archive.infolist():
        if member.is_dir():
            continue
        if "\\" in member.filename:
            raise FirmwareArchiveError(f"Unsafe archive member: {member.filename}")
        path = PurePosixPath(member.filename)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise FirmwareArchiveError(f"Unsafe archive member: {member.filename}")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise FirmwareArchiveError(f"Archive links are not supported: {member.filename}")
        members.append((member, path.parts))

    if not members:
        raise FirmwareArchiveError("The downloaded firmware archive is empty.")

    first_parts = {parts[0] for _, parts in members}
    strip_root = len(first_parts) == 1 and all(len(parts) > 1 for _, parts in members)
    return [
        (member, parts[1:] if strip_root else parts)
        for member, parts in members
    ]


def extract_firmware_archive(
    archive_path: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = True,
) -> list[Path]:
    """Safely extract a GitHub firmware ZIP, omitting its generated root folder."""

    target_root = Path(destination)
    target_root.mkdir(parents=True, exist_ok=True)
    root_resolved = target_root.resolve()
    extracted: list[Path] = []

    with ZipFile(archive_path) as archive:
        members = _safe_members(archive)
        targets: list[tuple[ZipInfo, Path]] = []
        for member, parts in members:
            target = target_root.joinpath(*parts)
            try:
                target.resolve().relative_to(root_resolved)
            except ValueError as error:
                raise FirmwareArchiveError(
                    f"Unsafe archive member: {member.filename}"
                ) from error
            targets.append((member, target))

        for member, target in targets:
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".download")
            try:
                with archive.open(member) as source, temporary.open("wb") as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            extracted.append(target)
    return extracted


def download_firmware(
    branch: str,
    destination: str | Path,
    *,
    overwrite: bool = True,
    progress: Callable[[int, int | None], None] | None = None,
    session=requests,
) -> list[Path]:
    """Download one repository branch as ZIP and extract it into ``destination``."""

    url = firmware_archive_url(branch)
    temporary_path: Path | None = None
    try:
        with session.get(url, stream=True, timeout=(15, 180)) as response:
            response.raise_for_status()
            total_header = response.headers.get("content-length")
            total = int(total_header) if total_header and total_header.isdigit() else None
            received = 0
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temporary:
                temporary_path = Path(temporary.name)
                for block in response.iter_content(chunk_size=1024 * 1024):
                    if not block:
                        continue
                    temporary.write(block)
                    received += len(block)
                    if progress is not None:
                        progress(received, total)
        return extract_firmware_archive(
            temporary_path,
            destination,
            overwrite=overwrite,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


__all__ = [
    "DEFAULT_FIRMWARE_BRANCH",
    "FIRMWARE_LICENSE_URL",
    "FIRMWARE_REPOSITORY",
    "FirmwareArchiveError",
    "download_firmware",
    "extract_firmware_archive",
    "firmware_archive_url",
    "validate_branch",
]
