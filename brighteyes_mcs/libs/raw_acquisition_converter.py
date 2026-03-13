"""Offline reconstruction of preview-less RAW acquisitions into standard HDF5 datasets."""

from __future__ import annotations

import shutil
from pathlib import Path

import h5py
import numpy as np

from .cython.fastconverter import (
    convertDataFromAnalogFIFO,
    convertRawDataToCountsDirect,
    convertRawDataToCountsDirect49,
)
from .processes.acquisition_loop_process import (
    accumulate_unordered_sum_4d,
    decode_pointer_list,
)


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
    if not path.is_absolute():
        path = (base_folder / path).resolve()
    return path


def _create_expandable_dataset(h5file, dataset_name, shape, timebins_per_pixel, channels, dtype):
    return h5file.create_dataset(
        dataset_name,
        shape=(1, shape[2], shape[1], shape[0], timebins_per_pixel, channels),
        maxshape=(None, shape[2], shape[1], shape[0], timebins_per_pixel, channels),
        dtype=dtype,
    )


def _ensure_rep_capacity(dataset, rep_index):
    if dataset.shape[0] > rep_index:
        return
    dims = list(dataset.shape)
    dims[0] = rep_index + 1
    dataset.resize(dims)


def _write_frame(dataset, buffer_frame, rep_index, z_index):
    _ensure_rep_capacity(dataset, rep_index)
    dataset[rep_index, z_index, :] = buffer_frame


def _resolve_raw_stream_path(raw_cfg, metadata_filename: Path, attr_name: str, default_suffix: str):
    candidate = _as_path(raw_cfg.get(attr_name, ""), metadata_filename.parent)
    if candidate is not None and candidate.exists():
        return candidate

    fallback = metadata_filename.with_name(_base_stem_from_metadata(metadata_filename) + default_suffix)
    if fallback.exists():
        return fallback.resolve()

    return candidate


def _base_stem_from_metadata(metadata_filename: Path):
    stem = metadata_filename.stem
    if stem.endswith("_only_metadata"):
        return stem[: -len("_only_metadata")]
    return stem


def _default_output_filename(metadata_filename: Path):
    base_stem = _base_stem_from_metadata(metadata_filename)
    if base_stem != metadata_filename.stem:
        return metadata_filename.with_name(base_stem + ".h5")
    return metadata_filename.with_name(metadata_filename.stem + "_converted.h5")


def _emit_progress(progress_callback, value, message):
    if progress_callback is not None:
        progress_callback(int(max(0, min(100, value))), message)


def _infer_digital_channels(raw_words, total_samples):
    if total_samples <= 0:
        return 25

    valid_channel_counts = []
    for candidate_channels, words_per_sample in ((25, 2), (49, 8)):
        if raw_words % words_per_sample == 0:
            valid_channel_counts.append(candidate_channels)

    if len(valid_channel_counts) == 1:
        return valid_channel_counts[0]

    raise RuntimeError(
        "Unable to infer whether the digital raw stream is 25- or 49-channel. "
        "Save acquisitions with updated raw metadata or keep configurationGUI.spad_number_of_channels populated."
    )


def _detect_streams(metadata_filename: Path, meta):
    raw_cfg = meta["raw_cfg"]

    digital_path = _resolve_raw_stream_path(
        raw_cfg, metadata_filename, "digital_raw_file", "_FIFO.raw"
    )
    analog_path = _resolve_raw_stream_path(
        raw_cfg, metadata_filename, "analog_raw_file", "_FIFOAnalog.raw"
    )

    streams = []
    if digital_path is not None and digital_path.exists():
        digital_words = digital_path.stat().st_size // np.dtype(np.uint64).itemsize
        total_samples = meta["total_samples"]
        channel_hint = int(raw_cfg.get("digital_channels", meta.get("channels_hint", 0) or 0))
        if channel_hint not in (25, 49):
            channel_hint = _infer_digital_channels(digital_words, total_samples)

        words_per_sample = int(raw_cfg.get("digital_words_per_sample", 0) or 0)
        expected_words_per_sample = 2 if channel_hint == 25 else 8
        if words_per_sample not in (2, 8):
            words_per_sample = expected_words_per_sample
        if words_per_sample != expected_words_per_sample:
            raise RuntimeError(
                f"Inconsistent digital stream metadata: channels={channel_hint}, "
                f"words_per_sample={words_per_sample}."
            )
        if digital_words % words_per_sample != 0:
            raise RuntimeError(
                f"Digital raw file size is not aligned to {words_per_sample} uint64 words per sample: {digital_path}"
            )

        streams.append(
            {
                "fifo_name": "FIFO",
                "path": digital_path,
                "kind": "digital",
                "channels": channel_hint,
            }
        )

    if analog_path is not None and analog_path.exists():
        streams.append(
            {
                "fifo_name": "FIFOAnalog",
                "path": analog_path,
                "kind": "analog",
                "channels": 2,
            }
        )

    if not streams:
        raise FileNotFoundError(
            "No raw FIFO stream was found. Expected metadata attributes "
            "'digital_raw_file'/'analog_raw_file' or sibling files ending with '_FIFO.raw' / '_FIFOAnalog.raw'."
        )

    return streams


def _load_metadata(metadata_filename: Path):
    with h5py.File(metadata_filename, "r") as h5file:
        spad_cfg = _group_attrs_to_dict(h5file["configurationSpadFCSmanager"])
        fpga_cfg = _group_attrs_to_dict(h5file["configurationFPGA"])
        gui_cfg = _group_attrs_to_dict(h5file["configurationGUI"])
        raw_cfg = _group_attrs_to_dict(h5file["rawStreamAcquisition"])

    channels_hint = int(gui_cfg.get("spad_number_of_channels", 25))
    shape = (
        int(spad_cfg["#pixels"]),
        int(spad_cfg["#lines"]),
        int(spad_cfg["#frames"]),
    )
    repetitions = int(spad_cfg["#repetition"]) - 1
    timebins_per_pixel = int(spad_cfg["#timebinsPerPixel"])
    circ_rep = int(spad_cfg.get("#circular_rep", 1))
    circ_points = int(spad_cfg.get("#circular_points", 1))
    effective_timebins = timebins_per_pixel * circ_rep * circ_points
    clk_base = float(raw_cfg.get("clock_base_mhz", gui_cfg.get("clock_base", 40)))
    time_resolution = float(spad_cfg.get("Cx", 40)) / clk_base
    total_frames = shape[2] * repetitions
    total_samples = shape[0] * shape[1] * effective_timebins * total_frames

    return {
        "spad_cfg": spad_cfg,
        "fpga_cfg": fpga_cfg,
        "gui_cfg": gui_cfg,
        "raw_cfg": raw_cfg,
        "channels_hint": channels_hint,
        "shape": shape,
        "repetitions": repetitions,
        "timebins_per_pixel": timebins_per_pixel,
        "circ_rep": circ_rep,
        "circ_points": circ_points,
        "effective_timebins": effective_timebins,
        "total_frames": total_frames,
        "total_samples": total_samples,
        "time_resolution": time_resolution,
        "snake_walk_xy": _as_bool(raw_cfg.get("snake_walk_xy", fpga_cfg.get("snake", False))),
        "snake_walk_z": _as_bool(raw_cfg.get("snake_walk_z", fpga_cfg.get("snake_z", False))),
        "dfd_activate": _as_bool(raw_cfg.get("dfd_activate", fpga_cfg.get("DFD_Activate", False))),
        "clk_multiplier": int(raw_cfg.get("clk_multiplier", fpga_cfg.get("clk_multiplier", 1)) or 1),
        "dfd_shift": int(raw_cfg.get("dfd_shift", fpga_cfg.get("dfd_shift", 0)) or 0),
    }


def _convert_digital(
    raw_filename: Path,
    output_filename: Path,
    meta,
    channels,
    progress_callback=None,
    progress_start=0,
    progress_span=100,
):
    shape = meta["shape"]
    effective_timebins = meta["effective_timebins"]
    clk_multiplier = max(1, meta["clk_multiplier"])
    reduced_timebins = effective_timebins // clk_multiplier
    words_per_sample = 2 if channels == 25 else 8
    converter = convertRawDataToCountsDirect if channels == 25 else convertRawDataToCountsDirect49

    raw_words = np.memmap(raw_filename, dtype=np.uint64, mode="r")
    total_samples = raw_words.shape[0] // words_per_sample
    samples_per_frame = shape[0] * shape[1] * effective_timebins
    chunk_samples = max(1, min(samples_per_frame, 250000))

    with h5py.File(output_filename, "r+") as h5file:
        data_dset = _create_expandable_dataset(
            h5file, "data", shape, reduced_timebins, channels, np.uint16
        )
        extra_dset = _create_expandable_dataset(
            h5file, "data_channels_extra", shape, reduced_timebins, 2, np.uint8
        )

        frame_buffer = np.zeros((shape[1], shape[0], reduced_timebins, channels), dtype=np.uint16)
        frame_extra_buffer = np.zeros((shape[1], shape[0], reduced_timebins, 2), dtype=np.uint8)
        decode_buffer = np.zeros((chunk_samples, channels + 2), dtype=np.uint64)
        buffer_sum = np.zeros(chunk_samples, dtype=np.uint64)
        saturation = np.zeros(channels + 2, dtype=np.uint64)
        mask = np.ones(channels, dtype=np.uint8)

        sample_pointer = 0
        frame_index = 0
        while sample_pointer < total_samples:
            current_frame_start = frame_index * samples_per_frame
            remaining_in_frame = current_frame_start + samples_per_frame - sample_pointer
            process_samples = int(min(chunk_samples, total_samples - sample_pointer, remaining_in_frame))
            process_words = process_samples * words_per_sample
            start_word = sample_pointer * words_per_sample
            stop_word = start_word + process_words

            # The Cython decoder expects a writable contiguous buffer; memmap
            # slices opened in read-only mode can trip "buffer source array is read-only".
            chunk = np.array(raw_words[start_word:stop_word], dtype=np.uint64, copy=True)
            saturation[:] = 0
            converter(
                data=chunk,
                start=0,
                stop=process_words,
                buffer_out=decode_buffer,
                buffer_sum=buffer_sum,
                fingerprint_saturation=saturation,
                mask=mask,
            )

            decoded = decode_buffer[:process_samples]
            list_b, list_x, list_y, _, _ = decode_pointer_list(
                sample_pointer,
                process_samples,
                effective_timebins,
                shape,
                snake_walk_xy=meta["snake_walk_xy"],
                snake_walk_z=meta["snake_walk_z"],
                clk_multiplier=clk_multiplier,
                delay=meta["dfd_shift"],
            )

            accumulate_unordered_sum_4d(
                frame_buffer,
                list_y,
                list_x,
                list_b,
                decoded[:, :channels].astype(np.uint16, copy=False),
            )
            accumulate_unordered_sum_4d(
                frame_extra_buffer,
                list_y,
                list_x,
                list_b,
                decoded[:, channels:].astype(np.uint8, copy=False),
            )

            sample_pointer += process_samples
            if total_samples > 0:
                _emit_progress(
                    progress_callback,
                    progress_start + progress_span * (sample_pointer / total_samples),
                    f"Converting digital RAW ({channels} ch): {sample_pointer}/{total_samples} samples",
                )
            reached_frame_end = sample_pointer == (current_frame_start + samples_per_frame)
            last_chunk = sample_pointer >= total_samples

            if reached_frame_end or last_chunk:
                rep_index = frame_index // shape[2]
                z_index = frame_index % shape[2]
                _write_frame(data_dset, frame_buffer, rep_index, z_index)
                _write_frame(extra_dset, frame_extra_buffer, rep_index, z_index)
                frame_buffer[:] = 0
                frame_extra_buffer[:] = 0
                frame_index += 1


def _convert_analog(
    raw_filename: Path,
    output_filename: Path,
    meta,
    progress_callback=None,
    progress_start=0,
    progress_span=100,
):
    shape = meta["shape"]
    effective_timebins = meta["effective_timebins"]
    raw_words = np.memmap(raw_filename, dtype=np.uint64, mode="r")
    total_samples = raw_words.shape[0]
    samples_per_frame = shape[0] * shape[1] * effective_timebins
    chunk_samples = max(1, min(samples_per_frame, 500000))

    with h5py.File(output_filename, "r+") as h5file:
        analog_dset = _create_expandable_dataset(
            h5file, "data_analog", shape, effective_timebins, 2, np.int32
        )

        frame_buffer = np.zeros((shape[1], shape[0], effective_timebins, 2), dtype=np.int32)
        decode_buffer = np.zeros((chunk_samples, 2), dtype=np.int32)

        sample_pointer = 0
        frame_index = 0
        while sample_pointer < total_samples:
            current_frame_start = frame_index * samples_per_frame
            remaining_in_frame = current_frame_start + samples_per_frame - sample_pointer
            process_samples = int(min(chunk_samples, total_samples - sample_pointer, remaining_in_frame))

            # Analog conversion has the same writable-buffer requirement as the
            # digital path, so convert the read-only memmap slice to a plain array.
            chunk = np.array(
                raw_words[sample_pointer: sample_pointer + process_samples],
                dtype=np.uint64,
                copy=True,
            )
            convertDataFromAnalogFIFO(
                data=chunk,
                start=0,
                stop=process_samples,
                buffer_out=decode_buffer,
                force_positive=0,
            )

            decoded = decode_buffer[:process_samples]
            list_b, list_x, list_y, _, _ = decode_pointer_list(
                sample_pointer,
                process_samples,
                effective_timebins,
                shape,
                snake_walk_xy=meta["snake_walk_xy"],
                snake_walk_z=meta["snake_walk_z"],
                delay=meta["dfd_shift"],
            )

            for analog_ch in range(2):
                accumulate_unordered_sum_4d(
                    frame_buffer[:, :, :, analog_ch: analog_ch + 1],
                    list_y,
                    list_x,
                    list_b,
                    decoded[:, analog_ch: analog_ch + 1],
                )

            sample_pointer += process_samples
            if total_samples > 0:
                _emit_progress(
                    progress_callback,
                    progress_start + progress_span * (sample_pointer / total_samples),
                    f"Converting analog RAW: {sample_pointer}/{total_samples} samples",
                )
            reached_frame_end = sample_pointer == (current_frame_start + samples_per_frame)
            last_chunk = sample_pointer >= total_samples

            if reached_frame_end or last_chunk:
                rep_index = frame_index // shape[2]
                z_index = frame_index % shape[2]
                _write_frame(analog_dset, frame_buffer, rep_index, z_index)
                frame_buffer[:] = 0
                frame_index += 1


def convert_raw_acquisition(metadata_filename: Path, output_filename: Path | None = None, progress_callback=None):
    """Rebuild a normal BrightEyes acquisition HDF5 from raw-stream acquisition files."""
    metadata_filename = Path(metadata_filename).resolve()
    meta = _load_metadata(metadata_filename)
    streams = _detect_streams(metadata_filename, meta)

    if output_filename is None:
        output_filename = _default_output_filename(metadata_filename)
    output_filename = Path(output_filename).resolve()
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
        stream_size = stream["path"].stat().st_size
        progress_start = 5 if total_bytes == 0 else 5 + 90 * (processed_bytes / total_bytes)
        progress_span = 0 if total_bytes == 0 else 90 * (stream_size / total_bytes)
        if stream["kind"] == "digital":
            _convert_digital(
                stream["path"],
                output_filename,
                meta,
                stream["channels"],
                progress_callback=progress_callback,
                progress_start=progress_start,
                progress_span=progress_span,
            )
        elif stream["kind"] == "analog":
            _convert_analog(
                stream["path"],
                output_filename,
                meta,
                progress_callback=progress_callback,
                progress_start=progress_start,
                progress_span=progress_span,
            )
        processed_bytes += stream_size

    _emit_progress(progress_callback, 100, "Conversion completed")

    return output_filename
