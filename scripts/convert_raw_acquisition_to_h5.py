"""CLI wrapper for converting preview-less RAW acquisitions into standard H5 files."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from brighteyes_mcs.libs.raw_acquisition_converter import convert_raw_acquisition


def main():
    parser = argparse.ArgumentParser(
        description="Convert preview-less RAW BrightEyes acquisitions back into standard H5 datasets."
    )
    parser.add_argument("metadata_h5", type=Path, help="Metadata-only H5 produced by preview-less RAW acquisition")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output H5 filename. Defaults to <metadata>_converted.h5",
    )
    args = parser.parse_args()

    last_progress = {"value": -1}

    def progress_callback(value, message):
        if value != last_progress["value"]:
            print(f"\r[{value:3d}%] {message}", end="", file=sys.stderr, flush=True)
            last_progress["value"] = value

    try:
        output_filename = convert_raw_acquisition(
            args.metadata_h5,
            args.output,
            progress_callback=progress_callback,
        )
    except Exception:
        print(file=sys.stderr)
        traceback.print_exc()
        raise
    print(file=sys.stderr)
    print(output_filename)


if __name__ == "__main__":
    main()
