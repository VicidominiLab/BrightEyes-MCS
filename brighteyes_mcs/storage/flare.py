"""Lossless Flare raw and HDF5 storage, separate from the NI v0.0.1 format."""

from datetime import datetime
import json
from pathlib import Path

import h5py

from ..acquisition.detectors.flare.v19 import circular_counts, ordinary_bins


FLARE_FORMAT = "brighteyes-flare-1"
FLARE_DFD_FORMAT = "brighteyes-flare-dfd-1"
FLARE_DFD3_FORMAT = "brighteyes-flare-dfd-3"
FLARE_CIRCULAR_FORMAT = "brighteyes-flare-circular-1"


def timestamp():
    return datetime.now().astimezone().isoformat()


class FlareRecording:
    def __init__(self, filename, configuration, *, raw_only=False):
        self.path = Path(filename)
        self.raw_path = self.path.with_suffix(".flare.raw")
        self.metadata_path = self.path.with_suffix(".flare.json")
        if any(p.exists() for p in (self.path, self.raw_path, self.metadata_path)):
            raise FileExistsError("Flare output already exists; choose a new filename")
        self.configuration = dict(configuration)
        self.dfd = configuration.get("acquisition_mode") == "dfd"
        self.scoped = configuration.get("stream_format") == "DFD3"
        self.circular = circular_counts(configuration)
        self.format = (FLARE_DFD3_FORMAT if self.scoped else FLARE_DFD_FORMAT if self.dfd
                       else FLARE_CIRCULAR_FORMAT if self.circular != (1, 1) else FLARE_FORMAT)
        self.raw_only = raw_only
        self.h5 = None
        self.data = None
        self.written_bins = 0
        self.metadata = {
            "format": self.format,
            "raw_format": f"{configuration['stream_format']} raw little-endian" if self.dfd else "FLR4 raw little-endian",
            "configuration": dict(configuration),
            "started_at": timestamp(),
            "result": "partial",
            "complete": False,
            "raw_file": self.raw_path.name,
        }
        # Persist initial identity before receiving bytes so interrupted runs remain identifiable.
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")
        if not raw_only:
            try:
                self.h5 = h5py.File(self.path, "x")
                self.h5.attrs["data_format_version"] = self.format
                c = configuration
                chunks = True
                if self.dfd and not self.scoped:
                    # Keep a pixel's complete histogram together. Automatic
                    # six-dimensional chunks split it across many small tiles,
                    # multiplying read/modify/write work during live recording.
                    pixel_bytes = c["histogram_bins"] * c["stream_channels"] * 2
                    chunk_pixels = min(c["pixels"], max(1, 262144 // pixel_bytes))
                    chunks = (1, 1, 1, chunk_pixels, c["histogram_bins"], c["stream_channels"])
                shape = (
                    c["repetitions"], c["frames"], c["lines"], c["pixels"],
                    c["histogram_bins"] if self.dfd else c["bins_per_pixel"],
                    c["stream_channels"] if self.dfd else c["channels"],
                )
                if self.scoped:
                    shape = (c["total_records"], c["histogram_bins"], c["stream_channels"])
                    chunks = (1, c["histogram_bins"], c["stream_channels"])
                elif not self.dfd and self.circular != (1, 1):
                    points, circles = self.circular
                    shape = (*shape[:4], circles, points, ordinary_bins(c), c["channels"])
                self.data = self.h5.create_dataset(
                    "data",
                    shape=shape,
                    dtype="<u2" if self.dfd and not self.scoped else "<u4",
                    chunks=chunks,
                )
                if self.scoped:
                    self.data.attrs["axes"] = "window,phase,channel"
                    group = self.h5.create_group("dfd_windows")
                    for name, dims, dtype in (
                        ("first_coordinates", (7,), "<u4"), ("last_coordinates", (7,), "<u4"),
                        ("first_tick", (), "<u8"), ("last_tick", (), "<u8"),
                        ("requested_boundaries", (), "<u4"), ("completed_boundaries", (), "<u4"),
                        ("partial", (), "?"), ("stopped", (), "?"),
                        ("run_id", (), "<u4"), ("trajectory_id", (), "<u4"),
                        ("ordinal", (), "<u4"), ("scope", (), "S24"),
                    ):
                        group.create_dataset(name, shape=(c["total_records"], *dims), dtype=dtype)
                    group.attrs["coordinate_axes"] = "x,y,z,image_repetition,circular_point,circular_repetition,time_bin"
                elif not self.dfd and self.circular != (1, 1):
                    self.data.attrs["axes"] = "image_repetition,z,y,x,circular_repetition,circular_point,time_bin,channel"
                self.h5.attrs["complete"] = False
                self.h5.flush()
            except Exception:
                if self.h5 is not None:
                    self.h5.close()
                raise

    def append(self, index, counts, *, windows=None):
        if self.data is None or len(counts) == 0:
            return
        c = self.configuration
        if self.scoped:
            if windows is None or len(windows) != len(counts):
                raise ValueError("DFD3 counts require matching exposure windows")
            self.data[index:index + len(counts)] = counts
            for name, dataset in self.h5["dfd_windows"].items():
                dataset[index:index + len(counts)] = [getattr(window, name) for window in windows]
            self.written_bins = index + len(counts)
            return
        if not self.dfd and self.circular != (1, 1):
            # Expanded A2 bins unflatten time -> point -> circle -> X -> Y -> Z -> repetition.
            points, circles = self.circular
            bins = ordinary_bins(c)
            expanded = bins * points * circles
            offset = 0
            while offset < len(counts):
                n, b = divmod(index + offset, expanded)
                n, x = divmod(n, c["pixels"])
                n, y = divmod(n, c["lines"])
                rep, z = divmod(n, c["frames"])
                remaining = len(counts) - offset
                if b == 0 and remaining >= expanded:
                    pixels = min(c["pixels"] - x, remaining // expanded)
                    take = pixels * expanded
                    self.data[rep, z, y, x:x + pixels] = counts[offset:offset + take].reshape(
                        pixels, circles, points, bins, c["channels"],
                    )
                else:
                    visit, time_bin = divmod(b, bins)
                    circle, point = divmod(visit, points)
                    take = min(remaining, bins - time_bin)
                    self.data[rep, z, y, x, circle, point, time_bin:time_bin + take] = counts[offset:offset + take]
                offset += take
                self.written_bins = index + offset
            return
        if self.dfd:
            offset = 0
            while offset < len(counts):
                n = index + offset
                x, n = n % c["pixels"], n // c["pixels"]
                y, n = n % c["lines"], n // c["lines"]
                z, rep = n % c["frames"], n // c["frames"]
                take = min(len(counts) - offset, c["pixels"] - x)
                self.data[rep, z, y, x:x + take, :, :] = counts[offset:offset + take]
                offset += take
                self.written_bins = index + offset
            return
        offset = 0
        while offset < len(counts):
            n = index + offset
            b = n % c["bins_per_pixel"]
            n //= c["bins_per_pixel"]
            x = n % c["pixels"]
            n //= c["pixels"]
            y = n % c["lines"]
            n //= c["lines"]
            z, rep = n % c["frames"], n // c["frames"]
            remaining = len(counts) - offset
            if b or remaining < c["bins_per_pixel"]:
                take = min(remaining, c["bins_per_pixel"] - b)
                self.data[rep, z, y, x, b : b + take, :] = counts[offset : offset + take]
            else:
                pixels = min(c["pixels"] - x, remaining // c["bins_per_pixel"])
                take = pixels * c["bins_per_pixel"]
                self.data[rep, z, y, x : x + pixels, :, :] = counts[offset : offset + take].reshape(
                    pixels, c["bins_per_pixel"], c["channels"]
                )
            offset += take
            self.written_bins = index + offset

    def finish(self, metadata):
        self.metadata.update(metadata)
        self.metadata["stored_bins"] = self.written_bins
        self.metadata["finished_at"] = timestamp()
        try:
            if self.h5 is not None:
                self._write_reader_metadata()
                self.h5.attrs["complete"] = bool(self.metadata.get("complete"))
                self.h5.attrs["validated_bins"] = int(self.metadata.get("validated_bins", 0))
                self.h5.attrs["stored_bins"] = self.written_bins
                if self.dfd:
                    self.h5.attrs["validated_records"] = int(self.metadata.get("validated_bins", 0))
                    self.h5.attrs["stored_records"] = self.written_bins
                    for key in ("stream_format", "histogram_bins", "reference_channel_index", "count_bits", "detector_channels"):
                        self.h5.attrs[key] = self.configuration[key]
                    for key in ("stream_format_version", "stream_channels", "padded_channels",
                                "extra_channel_count", "extra_channel_index", "extra_channel_physical_io",
                                "padding_channel_indices", "channel_roles"):
                        if key in self.configuration:
                            self.h5.attrs[key] = self.configuration[key]
                            self.data.attrs[key] = self.configuration[key]
                    self.data.attrs["reference_channel_index"] = self.configuration["reference_channel_index"]
                    if self.scoped:
                        self.data.attrs["dfd_scope"] = self.configuration["dfd_scope"]
                        self.data.attrs["count_bits"] = 32
                    from ..acquisition.detectors.flare.dfd import REFERENCE_METADATA, ALIGNMENT_METADATA
                    for key in (*REFERENCE_METADATA, *ALIGNMENT_METADATA):
                        if self.configuration.get(key) is not None:
                            self.h5.attrs[key] = self.configuration[key]
                            self.data.attrs[key] = self.configuration[key]
                self.h5.attrs["flare_metadata"] = json.dumps(self.metadata)
                self.h5.flush()
        except Exception as error:
            self.metadata.update(
                complete=False, result="partial", error=f"File finalization failed: {error}"
            )
            raise
        finally:
            if self.h5 is not None:
                self.h5.close()
                self.h5 = None
            self.metadata_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    def checkpoint(self, metadata):
        self.metadata.update(metadata)
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    def _write_reader_metadata(self):
        """Expose common analysis metadata while keeping the Flare format identity."""
        c = self.configuration
        gui = dict(self.metadata.get("configurationGUI", {}))
        gui.update(
            nx=c["pixels"],
            ny=c["lines"],
            nframe=c["frames"],
            nrep=c["repetitions"],
            timebin_per_pixel=91 if self.dfd else c["bins_per_pixel"],
            spad_number_of_channels=c["channels"],
            detector_model="FPGA Flare",
        )
        normalized = {
            "nx": c["pixels"],
            "ny": c["lines"],
            "nz": c["frames"],
            "nrep": c["repetitions"],
            "time_bins": 91 if self.dfd else c["bins_per_pixel"],
            "dfd_active": self.dfd,
            "dfd_window_axis": self.scoped,
            "circular_points": self.circular[0], "circular_repetitions": self.circular[1],
            "ordinary_time_bins": ordinary_bins(c),
        }
        clock = self.metadata.get("firmware", {}).get("clock_hz")
        if clock:
            pixel_us = (c["pixel_sys_cycles"] if self.dfd else c["dwell"] * c["bins_per_pixel"]) * 1e6 / clock
            gui["time_resolution"] = pixel_us / (91 if self.dfd else c["bins_per_pixel"])
            normalized["time_resolution_us"] = gui["time_resolution"]
            normalized["pixel_dwell_time_us"] = pixel_us
        if self.dfd:
            gui.update(DFD_Activate=True, DFDnbins=91, dfd_cycle_mhz=c["laser_hz"] / 1e6, clk_base_multiplier=1)
            normalized.update(
                stream_channels=c["stream_channels"], reference_channel_index=c["reference_channel_index"],
                dfd_nbins=91, dfd_cycle_mhz=c["laser_hz"] / 1e6,
                laser_frequency_mhz=c["laser_hz"] / 1e6,
                dfd_bin_width_ps=1e12 / c["laser_hz"] / 91,
            )
            from ..acquisition.detectors.flare.dfd import REFERENCE_METADATA, ALIGNMENT_METADATA
            normalized.update({key: c[key] for key in (*REFERENCE_METADATA, *ALIGNMENT_METADATA) if key in c})
        for axis, count in (("x", c["pixels"]), ("y", c["lines"]), ("z", c["frames"])):
            if f"range_{axis}" in gui:
                normalized[f"range_{axis}_um"] = gui[f"range_{axis}"]
                normalized[f"pixel_size_{axis}_um"] = gui[f"range_{axis}"] / count
            if f"offset_{axis}_um" in gui:
                normalized[f"offset_{axis}_um"] = gui[f"offset_{axis}_um"]
        for group_name, values in (
            ("configurationGUI", gui),
            ("raw/metadata", normalized),
            ("configurationFlare", c),
        ):
            group = self.h5.require_group(group_name)
            for key, value in values.items():
                if isinstance(value, (str, int, float, bool)):
                    group.attrs[key] = value


def convert_flare_raw(raw_filename, metadata_filename, output_filename):
    """Convert only explicitly identified Flare files, preserving partial status."""
    from ..acquisition.detectors.flare.decoder import FlareDecoder
    from ..acquisition.detectors.flare.dfd import FlareDfdDecoder

    metadata = json.loads(Path(metadata_filename).read_text(encoding="utf-8"))
    dfd_formats = (FLARE_DFD_FORMAT, FLARE_DFD3_FORMAT)
    if metadata.get("format") not in (FLARE_FORMAT, FLARE_CIRCULAR_FORMAT, *dfd_formats):
        raise ValueError("Metadata does not identify a supported Flare recording")
    decoder = (FlareDfdDecoder if metadata["format"] in dfd_formats else FlareDecoder)(metadata["configuration"], metadata["run_id"])
    recording = FlareRecording(output_filename, metadata["configuration"])
    result = dict(metadata)
    try:
        with open(raw_filename, "rb") as source:
            while chunk := source.read(262144):
                index = decoder.index
                counts = decoder.feed(chunk)
                recording.append(index, counts, **({"windows": decoder.windows} if recording.scoped else {}))
        if metadata["format"] in dfd_formats and not metadata.get("complete"):
            result.update(decoder.finish(cancelled=True))
        else:
            decoder.finish()
    except Exception as error:
        result.update(complete=False, result="partial", error=str(error))
        raise
    finally:
        result["validated_bins"] = decoder.index
        result["source_raw_file"] = str(raw_filename)
        result["raw_file"] = str(Path(raw_filename).resolve())
        recording.finish(result)
    return str(output_filename)
