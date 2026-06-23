"""Offline PI23 raw conversion scaffold."""

from pathlib import Path


def convert_pi23_raw_acquisition(metadata_filename, output_filename=None, progress_callback=None):
    """
    Placeholder for PI23 raw-bunch conversion.

    The PI23 raw stream is intentionally not SPAD FIFO words. Fill this
    converter once the real detector payload and decoding rules are available.
    """
    metadata_filename = Path(metadata_filename).resolve()
    if progress_callback is not None:
        progress_callback(0, "PI23 raw conversion scaffold")
    raise NotImplementedError(
        "PI23 raw conversion is scaffolded but not implemented yet. "
        "PI23 raw files are not SPAD FIFO raw streams."
    )

