"""Validate BrightEyes-MCS wheel and source-distribution contents."""

from __future__ import annotations

import argparse
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
import tarfile
import zipfile


REQUIRED_WHEEL_FILES = {
    "brighteyes_mcs/__main__.py",
    "brighteyes_mcs/cfg/default.cfg",
    "brighteyes_mcs/cfg/plugins_cfg/channel_delay_skew.cfg",
    "brighteyes_mcs/cfg/plugins_cfg/dfd.cfg",
    "brighteyes_mcs/images/icon.ico",
    "brighteyes_mcs/images/icon.png",
    "brighteyes_mcs/images/splash.png",
    "brighteyes_mcs/plugins/builtin/dfd/dfd_widget_design.ui",
    "brighteyes_mcs/plugins/builtin/myplugin/gui/plugin_gui.ui",
    "brighteyes_mcs/plugins/builtin/script_launcher/gui/plugin_gui.ui",
    "brighteyes_mcs/ui/qt/about.html",
    "brighteyes_mcs/ui/qt/main_window_design.ui",
    "brighteyes_mcs/ui/qt/ttm_widget_design.ui",
}


def _one_match(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {pattern!r} artifact in {directory}, found {len(matches)}."
        )
    return matches[0]


def check_distribution(directory: Path) -> None:
    wheel = _one_match(directory, "*.whl")
    sdist = _one_match(directory, "*.tar.gz")

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
        metadata_paths = [name for name in wheel_names if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise RuntimeError("The wheel must contain exactly one METADATA file.")
        metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_paths[0]))

        entry_point_paths = [
            name for name in wheel_names if name.endswith(".dist-info/entry_points.txt")
        ]

    missing = sorted(REQUIRED_WHEEL_FILES - wheel_names)
    if missing:
        raise RuntimeError(f"Required wheel resources are missing: {missing}")

    forbidden_wheel_files = sorted(
        name
        for name in wheel_names
        if name.endswith((".exe", ".lvbitx", "/mifobio.cfg", "/provacfg.cfg"))
    )
    if forbidden_wheel_files:
        raise RuntimeError(f"Local or proprietary files entered the wheel: {forbidden_wheel_files}")

    if metadata["License-Expression"] != "GPL-3.0-or-later":
        raise RuntimeError("Unexpected or missing wheel license expression.")
    if "psutil" not in (metadata.get_all("Requires-Dist") or []):
        raise RuntimeError("The direct psutil dependency is missing from the wheel.")
    if entry_point_paths:
        raise RuntimeError(
            "The wheel unexpectedly contains entry points; BrightEyes-MCS must "
            "be launched with python -m brighteyes_mcs."
        )

    with tarfile.open(sdist, "r:gz") as archive:
        forbidden_sdist_files = sorted(
            name
            for name in archive.getnames()
            if name.endswith((".exe", ".lvbitx", "/mifobio.cfg", "/provacfg.cfg"))
        )
    if forbidden_sdist_files:
        raise RuntimeError(f"Local or proprietary files entered the sdist: {forbidden_sdist_files}")

    print(f"Validated {wheel.name} ({len(wheel_names)} files) and {sdist.name}.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("dist"),
        help="Directory containing exactly one wheel and one .tar.gz sdist.",
    )
    args = parser.parse_args()
    check_distribution(args.directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
