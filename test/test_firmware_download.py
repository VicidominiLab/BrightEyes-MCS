from io import BytesIO
from pathlib import Path
import tempfile
from zipfile import ZipFile

import pytest

from brighteyes_mcs.application.firmware_download import (
    FirmwareArchiveError,
    download_firmware,
    extract_firmware_archive,
    firmware_archive_url,
)


def _archive(files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    return output.getvalue()


def test_branch_archive_url_supports_slashes_and_rejects_traversal():
    assert firmware_archive_url("feature/device-2").endswith(
        "/archive/refs/heads/feature/device-2.zip"
    )
    with pytest.raises(FirmwareArchiveError):
        firmware_archive_url("feature/../main")


def test_extract_strips_github_root_and_preserves_repository_files():
    contents = _archive(
        {
            "BrightEyes-MCSLL-main/device.lvbitx": b"firmware",
            "BrightEyes-MCSLL-main/README.md": b"instructions",
        }
    )
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        archive_path = temporary_path / "firmware.zip"
        archive_path.write_bytes(contents)
        destination = temporary_path / "bitfiles"

        extracted = extract_firmware_archive(archive_path, destination)

        assert destination / "device.lvbitx" in extracted
        assert (destination / "device.lvbitx").read_bytes() == b"firmware"
        assert (destination / "README.md").read_bytes() == b"instructions"


def test_extract_rejects_zip_path_traversal_before_writing():
    contents = _archive(
        {
            "BrightEyes-MCSLL-main/device.lvbitx": b"firmware",
            "../outside.txt": b"unsafe",
        }
    )
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        archive_path = temporary_path / "firmware.zip"
        archive_path.write_bytes(contents)
        with pytest.raises(FirmwareArchiveError):
            extract_firmware_archive(archive_path, temporary_path / "bitfiles")
        assert not (temporary_path / "outside.txt").exists()


class _FakeResponse:
    def __init__(self, contents: bytes):
        self.contents = contents
        self.headers = {"content-length": str(len(contents))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.contents[:chunk_size]
        yield self.contents[chunk_size:]


class _FakeSession:
    def __init__(self, contents: bytes):
        self.contents = contents
        self.request = None

    def get(self, url, **kwargs):
        self.request = (url, kwargs)
        return _FakeResponse(self.contents)


def test_download_streams_archive_reports_progress_and_extracts():
    contents = _archive({"BrightEyes-MCSLL-main/device.lvbitx": b"firmware"})
    session = _FakeSession(contents)
    progress = []
    with tempfile.TemporaryDirectory() as temporary:
        extracted = download_firmware(
            "main",
            temporary,
            session=session,
            progress=lambda received, total: progress.append((received, total)),
        )
        assert Path(temporary, "device.lvbitx") in extracted
        assert Path(temporary, "device.lvbitx").read_bytes() == b"firmware"
    assert session.request[0].endswith("/archive/refs/heads/main.zip")
    assert progress[-1] == (len(contents), len(contents))
