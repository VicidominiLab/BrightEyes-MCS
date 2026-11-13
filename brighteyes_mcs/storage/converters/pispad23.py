"""Offline PISPAD23 raw conversion scaffold."""

from pathlib import Path

import os
import tempfile

from ..tdc_metadata import ScanGeometry, copy_metadata, find_metadata, read_geometry


class ConversionCancelled(Exception):
    pass


def tdc_output_paths(raw, directory=None):
    raw = Path(raw)
    folder = Path(directory) if directory else raw.parent
    return {"tdc": folder / f"{raw.stem}-tdc.h5",
            "intensity": folder / f"{raw.stem}-intensity.h5"}


def convert_tdc_raw(raw, *, tdc_output=None, intensity_output=None, metadata=None,
                    geometry=None, progress_callback=None, cancel_event=None):
    """Convert one TDC RAW file, publishing selected outputs after metadata copy.

    Existing destinations are never overwritten. Intensity output is standard
    MCS HDF5 reconstructed from original, ordered Rust-decoded microimages.
    """
    import h5py
    from ..pispad23_microimage import MicroimageH5Writer
    from ...acquisition.detectors.pispad23.microimage import MicroimageSnapshot
    import brighteyes_pispad as pispad

    raw = Path(raw).resolve(strict=True)
    if raw.suffix.lower() != ".raw":
        raise ValueError("Select pSPAD TDC RAW files")
    cs_sidecar = Path(str(raw) + ".json")
    if cs_sidecar.is_file():
        import json
        if json.loads(cs_sidecar.read_text()).get("format") == "pispad_cs_u8_planar_v1":
            raise ValueError("This is intensity-mode RAW, not TDC RAW")
    outputs = {k: Path(v).resolve() for k, v in
               (("tdc", tdc_output), ("intensity", intensity_output)) if v is not None}
    if not outputs:
        raise ValueError("Select TDC HDF5, intensity HDF5, or both")
    if len(set(outputs.values())) != len(outputs):
        raise ValueError("TDC and intensity destinations must be different")
    for target in outputs.values():
        if target == raw or target.exists():
            raise FileExistsError(f"Destination already exists: {target}")
        if not target.parent.is_dir():
            raise FileNotFoundError(f"Output folder does not exist: {target.parent}")
    metadata = Path(metadata).resolve(strict=True) if metadata else find_metadata(raw)
    if metadata == raw:
        raise ValueError("Metadata must be an HDF5 companion file")
    if metadata:
        with h5py.File(metadata, "r") as file:
            state = file.attrs.get("acquisition_status", "")
            state = state.decode() if isinstance(state, bytes) else str(state)
            if state.lower() in ("starting", "running", "recording"):
                raise ValueError("This TDC acquisition is still active; wait for recording to finish")
    if intensity_output is not None:
        geometry = read_geometry(metadata) or geometry
        if not isinstance(geometry, ScanGeometry):
            raise ValueError("Intensity conversion needs scan geometry and dwell time: select acquisition metadata or enable fallback scan settings")
        if not hasattr(pispad, "iter_tdc_raw_microimages"):
            raise RuntimeError("Update brighteyes-pispad-libs to version 0.3.1 or newer")
    before = raw.stat()
    stages, published = {}, []

    def progress(value, message):
        if cancel_event is not None and cancel_event.is_set():
            raise ConversionCancelled("Conversion cancelled")
        if progress_callback:
            progress_callback(value, message)

    # Keep staging on each destination's filesystem for atomic no-overwrite links.
    from contextlib import ExitStack
    with ExitStack() as cleanup:
        for kind, target in outputs.items():
            folder = cleanup.enter_context(tempfile.TemporaryDirectory(prefix=".pispad-convert-", dir=target.parent))
            stages[kind] = Path(folder) / target.name
        try:
            progress(0, f"Preparing {raw.name}")
            if "tdc" in outputs:
                pispad.convert_to_h5(raw, stages["tdc"])
                progress(50 if "intensity" in outputs else 90, "TDC events converted")
            if "intensity" in outputs:
                from dataclasses import asdict
                writer = MicroimageH5Writer(stages["intensity"], **asdict(geometry))
                writer_closed = False
                offset, span = (50, 40) if "tdc" in outputs else (0, 90)
                try:
                    for batch in pispad.iter_tdc_raw_microimages(raw, progress_callback=lambda n:
                            progress(offset + span * n / max(1, before.st_size), "Reconstructing intensity")):
                        for row in batch:
                            writer.consume(MicroimageSnapshot(row["counts"], int(row["frame"]),
                                int(row["x"]), int(row["y"]), int(row["events"]), int(row["flags"])))
                    writer_closed = True
                    writer.close(finished=True)
                except BaseException as error:
                    # close() owns its own failure cleanup; avoid closing twice.
                    if not writer_closed:
                        try:
                            writer.close(error=str(error))
                        except Exception:
                            pass
                    raise
            progress(92, "Preserving acquisition metadata")
            after = raw.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError("RAW file changed during conversion; wait for acquisition to finish")
            for kind, stage in stages.items():
                if kind == "tdc":
                    with h5py.File(stage, "r+") as file:
                        file.attrs["default"] = "event_table"
                if metadata:
                    copy_metadata(metadata, stage, snapshot=True)
                with h5py.File(stage, "r+") as file:
                    provenance = file.require_group("conversion")
                    provenance.attrs.update(source_file=str(raw), source_bytes=before.st_size,
                        source_mtime_ns=before.st_mtime_ns, output_kind=kind,
                        metadata_source=str(metadata) if metadata else "",
                        acquisition_metadata_available=metadata is not None)
                    if kind == "intensity":
                        from dataclasses import asdict
                        provenance.attrs.update(asdict(geometry))
            progress(98, "Publishing converted files")
            for kind, target in outputs.items():
                if os.name == "nt":
                    # Windows rename refuses existing destinations and also
                    # supports filesystems that do not implement hard links.
                    os.rename(stages[kind], target)
                else:
                    os.link(stages[kind], target)
                published.append((stages[kind], target, target.stat()))
        except BaseException:
            for stage, target, owned in published:
                if not target.exists():
                    continue
                current = target.stat()
                identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
                if identity(current) == identity(owned) and (
                        not stage.exists() or os.path.samefile(stage, target)):
                    target.unlink()
            raise
    if progress_callback:
        progress_callback(100, f"Converted {raw.name}")
    return tuple(outputs.values())


def convert_pispad23_raw_acquisition(metadata_filename, output_filename=None, progress_callback=None):
    """
    Placeholder for PISPAD23 raw-bunch conversion.

    The PISPAD23 raw stream is intentionally not SPAD FIFO words. Fill this
    converter once the real detector payload and decoding rules are available.
    """
    metadata_filename = Path(metadata_filename).resolve()
    if progress_callback is not None:
        progress_callback(0, "PISPAD23 raw conversion scaffold")
    raise NotImplementedError(
        "PISPAD23 raw conversion is scaffolded but not implemented yet. "
        "PISPAD23 raw files are not SPAD FIFO raw streams."
    )

