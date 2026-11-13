"""Acquisition metadata kept beside a pSPAD TDC RAW recording."""
from dataclasses import asdict, dataclass
from pathlib import Path

import h5py

from .h5 import H5Manager
from .legacy_names import LEGACY_H5_REGISTER_NAME_MAP


@dataclass(frozen=True)
class ScanGeometry:
    width: int
    height: int
    frames: int
    repetitions: int
    dwell_seconds: float
    snake: bool = False
    snake_z: bool = False

    def __post_init__(self):
        import math
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1
               for v in (self.width, self.height, self.frames, self.repetitions)):
            raise ValueError("Scan dimensions, frames and repetitions must be positive integers")
        if self.width * self.height > 16_777_216:
            raise ValueError("Scan frame is too large")
        if not math.isfinite(self.dwell_seconds) or self.dwell_seconds <= 0:
            raise ValueError("Dwell duration must be finite and positive")


def sidecar_path(raw):
    return Path(str(raw) + ".metadata.h5")


def create_metadata(raw, geometry, snapshot=None):
    """Create before acquisition, including when the main MCS file is suppressed."""
    path = sidecar_path(raw)
    snapshot = snapshot or {}
    manager = H5Manager(path, exclusive=True)
    try:
        manager.metadata_add_initial(snapshot.get("comment", ""))
        manager.set_attributes("/", dict(pispad_raw_format="tdc6", raw_file=Path(raw).name,
                                          acquisition_status="starting"))
        manager.set_attributes("pispad_tdc_geometry", asdict(geometry))
        for group, values in snapshot.get("groups", {}).items():
            register_names = LEGACY_H5_REGISTER_NAME_MAP if group in (
                "configurationFPGA", "configurationSpadFCSmanager") else None
            manager.metadata_add_dict(group, values, legacy_name_map=register_names)
    finally:
        manager.close()
    return path


def update_status(raw, status):
    path = sidecar_path(raw)
    if not path.exists():
        return
    with h5py.File(path, "r+") as metadata:
        metadata.attrs.update(acquisition_status=status.get("state", "unknown"),
                              acquisition_error=status.get("error", ""))
        if Path(raw).is_file():
            metadata.attrs["source_bytes"] = Path(raw).stat().st_size


_DATA_NODES = {"data", "data_analog", "data_channels_extra", "pispad23_microimages",
    "event_table", "event_id", "coarse", "monotonic_coarse", "coarse_wrap_count",
    "fine_or_wrap", "pixel", "is_pixel", "is_marker", "counts", "valid", "frame_complete",
    "x", "y", "z", "ff", "dwell_marker", "line_marker", "frame_marker", "overrun_marker"}


def copy_metadata(source, destination, *, snapshot=False):
    """Copy metadata without acquisition image payloads; retain conflicting attrs.

    Conversion outputs keep an exact metadata snapshot under acquisition_metadata
    and expose nonconflicting groups/attributes at their normal MCS locations.
    """
    with h5py.File(source, "r") as original, h5py.File(destination, "r+") as output:
        target = output.create_group("acquisition_metadata") if snapshot else output
        def copy_attrs(node, destination):
            for key, value in node.attrs.items():
                if key in destination.attrs:
                    del destination.attrs[key]
                destination.attrs.create(key, value, dtype=node.attrs.get_id(key).dtype)

        def describe(node, destination):
            copy_attrs(node, destination)
            if isinstance(node, h5py.Group):
                for key in node:
                    describe(node[key], destination.require_group(key))

        copy_attrs(original, target)
        for name, value in original.attrs.items():
            if snapshot and name not in output.attrs:
                output.attrs.create(name, value, dtype=original.attrs.get_id(name).dtype)
        for name in original:
            if name in _DATA_NODES:
                # Retain dataset/group attributes without duplicating data arrays.
                describe(original[name], target.require_group(name))
                continue
            if name in target:
                del target[name]
            original.copy(name, target, name=name, expand_soft=True, expand_external=True,
                          expand_refs=True)
            if snapshot and name not in output:
                target.copy(name, output, name=name)


def find_metadata(raw):
    raw = Path(raw)
    sidecar = sidecar_path(raw)
    if sidecar.is_file():
        return sidecar
    # MCS names RAW recordings <acquisition>-ts.raw, with an optional index.
    import re
    base = re.sub(r"-ts(?:-\d+)?$", "", raw.stem)
    candidates = [raw.with_name(base + ".h5"), raw.with_name(base + "_only_metadata.h5")]
    matches = list(dict.fromkeys(p for p in candidates if p.is_file()))
    return matches[0] if len(matches) == 1 else None


def read_geometry(metadata):
    if metadata is None:
        return None
    def as_bool(value):
        if isinstance(value, bytes):
            value = value.decode()
        return value.strip().lower() in ("1", "true", "yes", "on") if isinstance(value, str) else bool(value)

    with h5py.File(metadata, "r") as file:
        if "pispad_tdc_geometry" in file:
            attrs = dict(file["pispad_tdc_geometry"].attrs)
            return ScanGeometry(**{k: (as_bool(attrs[k]) if k in ("snake", "snake_z") else
                                      float(attrs[k]) if k == "dwell_seconds" else int(attrs[k]))
                                   for k in ScanGeometry.__dataclass_fields__})
        gui = {}
        for group in ("configurationGUI", "configurationGUI_beforeStart"):
            if group in file:
                gui.update(file[group].attrs)
        data = file.get("data")
        shape = data.shape if isinstance(data, h5py.Dataset) and data.ndim == 6 else None
        width, height = gui.get("nx"), gui.get("ny")
        frames, repetitions = gui.get("nframe"), gui.get("nrep")
        if shape:
            width, height = width or shape[3], height or shape[2]
            frames, repetitions = frames or shape[1], repetitions or shape[0]
        dwell = data.attrs.get("dwell_seconds") if shape else None
        if dwell is None and "time_resolution" in gui and "timebin_per_pixel" in gui:
            dwell = float(gui["time_resolution"]) * float(gui["timebin_per_pixel"]) * 1e-6
            if as_bool(gui.get("circular_active", False)):
                dwell *= float(gui.get("circular_points", 1)) * float(gui.get("circular_repetition", 1))
        info = file.get("pispad23_microimages")
        info = dict(info.attrs) if info is not None else {}
        if any(v is None for v in (width, height, frames, repetitions, dwell)):
            return None
        return ScanGeometry(int(width), int(height), int(frames), int(repetitions), float(dwell),
                            as_bool(info.get("snake_walk_xy", gui.get("snake", False))),
                            as_bool(info.get("snake_walk_z", gui.get("snake_z", False))))
