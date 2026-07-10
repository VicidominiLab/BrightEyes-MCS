"""Standalone converter for BrightEyes preview-less SPAD RAW acquisitions.

This module is extracted from BrightEyes-MCS and intentionally has no GUI or
``brighteyes_mcs`` package dependency.  It converts a metadata-only HDF5 file
and its sibling FIFO RAW files into a standard BrightEyes HDF5 acquisition.

Requires: numpy, h5py, and brighteyes-mcs-cylibs.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import traceback
from pathlib import Path

import h5py
import numpy as np

try:
    from brighteyes_mcs_cylibs.fastconverter import (
        convertDataFromAnalogFIFO,
        convertRawDataToCountsDirect,
        convertRawDataToCountsDirect49,
    )
except ImportError as exc:
    raise ImportError(
        "The converter requires brighteyes-mcs-cylibs. Install dependencies "
        "with: python -m pip install -r requirements.txt"
    ) from exc


PI23_DETECTOR_MODELS = {"PI 23", "PI23TT"}


def _attr_scalar(value):
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return value.reshape(-1)[0].item()
        return value
    if isinstance(value, np.generic):
        return value.item()
    return value


def _group_attrs_to_dict(group):
    return {key: _attr_scalar(group.attrs[key]) for key in group.attrs.keys()}


def _attrs_from_first_group(h5file, group_names):
    for group_name in group_names:
        if group_name in h5file:
            return _group_attrs_to_dict(h5file[group_name])
    raise KeyError("None of these H5 groups were found: %s" % ", ".join(group_names))


def _as_bool(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_path(value, base_folder: Path):
    if value in ("", None):
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    path = Path(value)
    return path if path.is_absolute() else (base_folder / path).resolve()


def _base_stem_from_metadata(metadata_filename: Path):
    stem = metadata_filename.stem
    return stem[: -len("_only_metadata")] if stem.endswith("_only_metadata") else stem


def _default_output_filename(metadata_filename: Path):
    base_stem = _base_stem_from_metadata(metadata_filename)
    if base_stem != metadata_filename.stem:
        return metadata_filename.with_name(base_stem + ".h5")
    return metadata_filename.with_name(metadata_filename.stem + "_converted.h5")


def _resolve_raw_stream_path(raw_cfg, metadata_filename: Path, attr_name: str, default_suffix: str):
    candidate = _as_path(raw_cfg.get(attr_name, ""), metadata_filename.parent)
    if candidate is not None and candidate.exists():
        return candidate

    fallback = metadata_filename.with_name(_base_stem_from_metadata(metadata_filename) + default_suffix)
    return fallback.resolve() if fallback.exists() else candidate


def _create_expandable_dataset(h5file, dataset_name, shape, timebins_per_pixel, channels, dtype):
    return h5file.create_dataset(
        dataset_name,
        shape=(1, shape[2], shape[1], shape[0], timebins_per_pixel, channels),
        maxshape=(None, shape[2], shape[1], shape[0], timebins_per_pixel, channels),
        dtype=dtype,
    )


def _ensure_rep_capacity(dataset, rep_index):
    if dataset.shape[0] <= rep_index:
        dimensions = list(dataset.shape)
        dimensions[0] = rep_index + 1
        dataset.resize(dimensions)


def _write_frame(dataset, buffer_frame, rep_index, z_index):
    _ensure_rep_capacity(dataset, rep_index)
    dataset[rep_index, z_index, :] = buffer_frame


def _emit_progress(progress_callback, value, message):
    if progress_callback is not None:
        progress_callback(int(max(0, min(100, value))), message)


def _infer_spad_channels(raw_words, total_samples):
    if total_samples <= 0:
        return 25
    possible = [channels for channels, words in ((25, 2), (49, 8)) if raw_words % words == 0]
    if len(possible) == 1:
        return possible[0]
    raise RuntimeError(
        "Unable to infer whether the SPAD raw stream is 25- or 49-channel. "
        "Provide digital_channels or spad_channels in the RAW metadata."
    )


def _load_metadata(metadata_filename: Path):
    with h5py.File(metadata_filename, "r") as h5file:
        mcs_cfg = _attrs_from_first_group(
            h5file, ("configurationSpadFCSmanager", "configurationMcsManager")
        )
        fpga_cfg = _group_attrs_to_dict(h5file["configurationFPGA"])
        gui_cfg = _group_attrs_to_dict(h5file["configurationGUI"])
        raw_cfg = _group_attrs_to_dict(h5file["rawStreamAcquisition"])

    detector_model = raw_cfg.get("detector_model", gui_cfg.get("detector_model", "SPAD Array"))
    if isinstance(detector_model, bytes):
        detector_model = detector_model.decode("utf-8", errors="ignore")
    if detector_model in PI23_DETECTOR_MODELS:
        raise NotImplementedError(
            "This standalone converter supports SPAD FIFO RAW streams only; "
            "PI23-native RAW conversion is not implemented."
        )

    shape = (int(mcs_cfg["#pixels"]), int(mcs_cfg["#lines"]), int(mcs_cfg["#frames"]))
    repetitions = int(mcs_cfg["#repetition"]) - 1
    timebins_per_pixel = int(mcs_cfg["#timebinsPerPixel"])
    circ_rep = int(mcs_cfg.get("#circular_rep", 1))
    circ_points = int(mcs_cfg.get("#circular_points", 1))
    effective_timebins = timebins_per_pixel * circ_rep * circ_points
    total_frames = shape[2] * repetitions

    return {
        "mcs_cfg": mcs_cfg,
        "fpga_cfg": fpga_cfg,
        "gui_cfg": gui_cfg,
        "raw_cfg": raw_cfg,
        "spad_channels_hint": int(gui_cfg.get("spad_number_of_channels", gui_cfg.get("spad_channels", 25))),
        "shape": shape,
        "effective_timebins": effective_timebins,
        "total_samples": shape[0] * shape[1] * effective_timebins * total_frames,
        "snake_walk_xy": _as_bool(raw_cfg.get("snake_walk_xy", fpga_cfg.get("snake", False))),
        "snake_walk_z": _as_bool(raw_cfg.get("snake_walk_z", fpga_cfg.get("snake_z", False))),
        "clk_multiplier": int(raw_cfg.get("clk_multiplier", fpga_cfg.get("clk_multiplier", 1)) or 1),
        "dfd_shift": int(raw_cfg.get("dfd_shift", fpga_cfg.get("dfd_shift", 0)) or 0),
    }


def _detect_streams(metadata_filename: Path, meta):
    raw_cfg = meta["raw_cfg"]
    digital_path = _resolve_raw_stream_path(raw_cfg, metadata_filename, "digital_raw_file", "_FIFO.raw")
    analog_path = _resolve_raw_stream_path(raw_cfg, metadata_filename, "analog_raw_file", "_FIFOAnalog.raw")
    streams = []

    if digital_path is not None and digital_path.exists():
        digital_words = digital_path.stat().st_size // np.dtype(np.uint64).itemsize
        spad_channels = int(raw_cfg.get(
            "digital_channels", raw_cfg.get("spad_channels", meta["spad_channels_hint"])
        ))
        if spad_channels not in (25, 49):
            spad_channels = _infer_spad_channels(digital_words, meta["total_samples"])
        words_per_sample = int(raw_cfg.get("digital_words_per_sample", 0) or 0)
        expected_words = 2 if spad_channels == 25 else 8
        if words_per_sample not in (2, 8):
            words_per_sample = expected_words
        if words_per_sample != expected_words:
            raise RuntimeError(
                f"Inconsistent SPAD stream metadata: spad_channels={spad_channels}, "
                f"words_per_sample={words_per_sample}."
            )
        if digital_words % words_per_sample:
            raise RuntimeError(
                f"Digital raw file size is not aligned to {words_per_sample} uint64 words per sample: {digital_path}"
            )
        streams.append({"path": digital_path, "kind": "digital", "spad_channels": spad_channels})

    if analog_path is not None and analog_path.exists():
        streams.append({"path": analog_path, "kind": "analog"})
    if not streams:
        raise FileNotFoundError(
            "No raw FIFO stream was found. Expected metadata attributes "
            "'digital_raw_file'/'analog_raw_file' or sibling files ending with "
            "'_FIFO.raw' / '_FIFOAnalog.raw'."
        )
    return streams


def decode_pointer_list(pointer_start, gap, timebins_per_pixel, shape, snake_walk_xy=False,
                        snake_walk_z=False, clk_multiplier=1, delay=0):
    """Return time-bin, x, y, z, repetition indices for a range of FIFO samples."""
    pointer = np.arange(pointer_start, pointer_start + gap)
    shifted = pointer + delay * timebins_per_pixel
    pixel = shifted // timebins_per_pixel
    timebin = shifted % timebins_per_pixel
    if clk_multiplier != 1:
        timebin %= timebins_per_pixel // clk_multiplier
    x = pixel % shape[0]
    y = (pixel // shape[0]) % shape[1]
    if snake_walk_xy:
        x = x + (y % 2) * (-2 * x + shape[0] - 1)
    z = pixel // (shape[0] * shape[1])
    repetition = z // shape[2]
    if snake_walk_z:
        z = (z + (repetition % 2) * (-2 * z + shape[2] - 1)) % shape[2]
    else:
        z %= shape[2]
    return timebin, x, y, z, repetition


def accumulate_unordered_sum_4d(destination, y, x, timebin, values):
    """Sum samples with repeated (y, x, time-bin) coordinates into a 4-D buffer."""
    if values.size == 0:
        return
    linear = ((y.astype(np.int64) * destination.shape[1] + x.astype(np.int64))
              * destination.shape[2] + timebin.astype(np.int64))
    order = np.argsort(linear, kind="mergesort")
    linear_sorted = linear[order]
    starts_mask = np.empty(linear_sorted.shape[0], dtype=bool)
    starts_mask[0] = True
    starts_mask[1:] = linear_sorted[1:] != linear_sorted[:-1]
    starts = np.nonzero(starts_mask)[0]
    destination.reshape(-1, destination.shape[-1])[linear_sorted[starts]] += np.add.reduceat(
        values[order], starts, axis=0
    )


def _convert_digital(raw_filename, output_filename, meta, spad_channels, progress_callback=None,
                     progress_start=0, progress_span=100):
    shape = meta["shape"]
    effective_timebins = meta["effective_timebins"]
    clk_multiplier = max(1, meta["clk_multiplier"])
    reduced_timebins = effective_timebins // clk_multiplier
    words_per_sample = 2 if spad_channels == 25 else 8
    converter = convertRawDataToCountsDirect if spad_channels == 25 else convertRawDataToCountsDirect49
    raw_words = np.memmap(raw_filename, dtype=np.uint64, mode="r")
    total_samples = raw_words.shape[0] // words_per_sample
    samples_per_frame = shape[0] * shape[1] * effective_timebins
    chunk_samples = max(1, min(samples_per_frame, 250000))

    with h5py.File(output_filename, "r+") as h5file:
        data_dset = _create_expandable_dataset(h5file, "data", shape, reduced_timebins, spad_channels, np.uint16)
        extra_dset = _create_expandable_dataset(h5file, "data_channels_extra", shape, reduced_timebins, 2, np.uint8)
        frame = np.zeros((shape[1], shape[0], reduced_timebins, spad_channels), dtype=np.uint16)
        frame_extra = np.zeros((shape[1], shape[0], reduced_timebins, 2), dtype=np.uint8)
        decoded_buffer = np.zeros((chunk_samples, spad_channels + 2), dtype=np.uint64)
        buffer_sum = np.zeros(chunk_samples, dtype=np.uint64)
        saturation = np.zeros(spad_channels + 2, dtype=np.uint64)
        mask = np.ones(spad_channels, dtype=np.uint8)
        sample_pointer = frame_index = 0

        while sample_pointer < total_samples:
            frame_start = frame_index * samples_per_frame
            count = int(min(chunk_samples, total_samples - sample_pointer,
                            frame_start + samples_per_frame - sample_pointer))
            start_word = sample_pointer * words_per_sample
            word_count = count * words_per_sample
            chunk = np.array(raw_words[start_word:start_word + word_count], dtype=np.uint64, copy=True)
            saturation[:] = 0
            converter(
                data=chunk,
                start=0,
                stop=word_count,
                buffer_out=decoded_buffer,
                buffer_sum=buffer_sum,
                fingerprint_saturation=saturation,
                mask=mask,
            )
            timebin, x, y, _, _ = decode_pointer_list(
                sample_pointer, count, effective_timebins, shape,
                meta["snake_walk_xy"], meta["snake_walk_z"], clk_multiplier, meta["dfd_shift"],
            )
            decoded = decoded_buffer[:count]
            accumulate_unordered_sum_4d(frame, y, x, timebin, decoded[:, :spad_channels].astype(np.uint16, copy=False))
            accumulate_unordered_sum_4d(frame_extra, y, x, timebin, decoded[:, spad_channels:].astype(np.uint8, copy=False))
            sample_pointer += count
            _emit_progress(progress_callback, progress_start + progress_span * sample_pointer / total_samples,
                           f"Converting SPAD RAW ({spad_channels} ch): {sample_pointer}/{total_samples} samples")
            if sample_pointer == frame_start + samples_per_frame or sample_pointer >= total_samples:
                _write_frame(data_dset, frame, frame_index // shape[2], frame_index % shape[2])
                _write_frame(extra_dset, frame_extra, frame_index // shape[2], frame_index % shape[2])
                frame[:] = 0
                frame_extra[:] = 0
                frame_index += 1


def _convert_analog(raw_filename, output_filename, meta, progress_callback=None, progress_start=0, progress_span=100):
    shape = meta["shape"]
    effective_timebins = meta["effective_timebins"]
    raw_words = np.memmap(raw_filename, dtype=np.uint64, mode="r")
    total_samples = raw_words.shape[0]
    samples_per_frame = shape[0] * shape[1] * effective_timebins
    chunk_samples = max(1, min(samples_per_frame, 500000))

    with h5py.File(output_filename, "r+") as h5file:
        dataset = _create_expandable_dataset(h5file, "data_analog", shape, effective_timebins, 2, np.int32)
        frame = np.zeros((shape[1], shape[0], effective_timebins, 2), dtype=np.int32)
        decoded_buffer = np.zeros((chunk_samples, 2), dtype=np.int32)
        sample_pointer = frame_index = 0
        while sample_pointer < total_samples:
            frame_start = frame_index * samples_per_frame
            count = int(min(chunk_samples, total_samples - sample_pointer,
                            frame_start + samples_per_frame - sample_pointer))
            chunk = np.array(raw_words[sample_pointer:sample_pointer + count], dtype=np.uint64, copy=True)
            convertDataFromAnalogFIFO(
                data=chunk,
                start=0,
                stop=count,
                buffer_out=decoded_buffer,
                force_positive=0,
            )
            timebin, x, y, _, _ = decode_pointer_list(
                sample_pointer, count, effective_timebins, shape,
                meta["snake_walk_xy"], meta["snake_walk_z"], delay=meta["dfd_shift"],
            )
            decoded = decoded_buffer[:count]
            for channel in range(2):
                accumulate_unordered_sum_4d(frame[:, :, :, channel:channel + 1], y, x, timebin,
                                            decoded[:, channel:channel + 1])
            sample_pointer += count
            _emit_progress(progress_callback, progress_start + progress_span * sample_pointer / total_samples,
                           f"Converting analog RAW: {sample_pointer}/{total_samples} samples")
            if sample_pointer == frame_start + samples_per_frame or sample_pointer >= total_samples:
                _write_frame(dataset, frame, frame_index // shape[2], frame_index % shape[2])
                frame[:] = 0
                frame_index += 1


def convert_raw_acquisition(metadata_filename: Path, output_filename: Path | None = None, progress_callback=None):
    """Rebuild a standard HDF5 acquisition from SPAD FIFO RAW stream files."""
    metadata_filename = Path(metadata_filename).resolve()
    meta = _load_metadata(metadata_filename)
    streams = _detect_streams(metadata_filename, meta)
    output_filename = Path(output_filename or _default_output_filename(metadata_filename)).resolve()
    if output_filename == metadata_filename:
        raise RuntimeError("Output H5 must be different from the metadata-only input H5.")

    _emit_progress(progress_callback, 0, "Preparing output H5")
    shutil.copyfile(metadata_filename, output_filename)
    with h5py.File(output_filename, "r+") as h5file:
        if "rawStreamAcquisition" in h5file:
            h5file["rawStreamAcquisition"].attrs["converted_to_standard_h5"] = True
            h5file["rawStreamAcquisition"].attrs["conversion_output_h5"] = str(output_filename)

    total_bytes = sum(stream["path"].stat().st_size for stream in streams)
    processed_bytes = 0
    for stream in streams:
        size = stream["path"].stat().st_size
        start = 5 if not total_bytes else 5 + 90 * processed_bytes / total_bytes
        span = 0 if not total_bytes else 90 * size / total_bytes
        if stream["kind"] == "digital":
            _convert_digital(stream["path"], output_filename, meta, stream["spad_channels"], progress_callback, start, span)
        else:
            _convert_analog(stream["path"], output_filename, meta, progress_callback, start, span)
        processed_bytes += size
    _emit_progress(progress_callback, 100, "Conversion completed")
    return output_filename


def main():
    parser = argparse.ArgumentParser(description="Convert preview-less BrightEyes SPAD RAW acquisitions to HDF5.")
    parser.add_argument("metadata_h5", type=Path, help="Metadata-only HDF5 file")
    parser.add_argument("-o", "--output", type=Path, help="Output HDF5 file (default: derived from metadata name)")
    args = parser.parse_args()
    progress = {"value": -1}

    def report(value, message):
        if value != progress["value"]:
            print(f"\r[{value:3d}%] {message}", end="", file=sys.stderr, flush=True)
            progress["value"] = value

    try:
        output = convert_raw_acquisition(args.metadata_h5, args.output, report)
    except Exception:
        print(file=sys.stderr)
        traceback.print_exc()
        return 1
    print(file=sys.stderr)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
