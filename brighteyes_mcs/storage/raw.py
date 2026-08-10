"""Canonical RAW acquisition converter import."""

from .converters.spad import convert_raw_acquisition


def metadata_filename(filename):
    """Preserve the legacy preview-less metadata filename convention."""

    if filename.endswith(".h5") and not filename.endswith("_only_metadata.h5"):
        return filename[:-3] + "_only_metadata.h5"
    return filename


def raw_output_files(metadata_h5, *, digital, analog):
    """Return v1 stream keys while preserving legacy RAW filename suffixes."""

    base = str(metadata_h5).replace(".h5", "")
    if base.endswith("_only_metadata"):
        base = base[: -len("_only_metadata")]
    result = {}
    if digital:
        result["stream_out_main"] = base + "_FIFO.raw"
    if analog:
        result["stream_out_aux"] = base + "_FIFOAnalog.raw"
    return result


__all__ = ["convert_raw_acquisition", "metadata_filename", "raw_output_files"]
