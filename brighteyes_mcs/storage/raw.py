"""Canonical RAW acquisition converter import."""

from .converters.spad import convert_raw_acquisition as _convert_legacy_raw


def convert_raw_acquisition(metadata_filename, output_filename=None, progress_callback=None):
    """Dispatch explicitly identified Flare sidecars; preserve legacy H5 conversion."""
    from pathlib import Path
    if str(metadata_filename).endswith(".flare.json"):
        import json
        from .flare import convert_flare_raw
        metadata_path = Path(metadata_filename)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        raw = metadata_path.parent / metadata["raw_file"]
        output = output_filename or metadata_path.with_name(metadata_path.name.removesuffix(".flare.json") + "_converted.h5")
        if progress_callback:
            progress_callback(0, "Converting Flare raw counts")
        result = convert_flare_raw(raw, metadata_path, output)
        if progress_callback:
            progress_callback(100, "Flare conversion complete")
        return result
    return _convert_legacy_raw(metadata_filename, output_filename, progress_callback)


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
