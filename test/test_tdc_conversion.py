"""Real library conversions preserve event data, dwell counts and acquisition metadata."""
import threading

import h5py
import numpy as np
import pytest

from brighteyes_mcs.storage.converters.pispad23 import (ConversionCancelled, convert_tdc_raw,
                                                       tdc_output_paths)
from brighteyes_mcs.storage.tdc_metadata import (ScanGeometry, copy_metadata, create_metadata,
    find_metadata, read_geometry, sidecar_path, update_status)

pispad = pytest.importorskip("brighteyes_pispad")
from brighteyes_pispad.simulator import SimulationConfig, simulated_raw


def recording(folder, name="scan-ts.raw", *, geometry=None, partial=False):
    geometry = geometry or ScanGeometry(3, 2, 2, 2, 0.002, snake=True, snake_z=True)
    raw = folder / name
    simulation = SimulationConfig(width=geometry.width, height=geometry.height,
        frames=geometry.frames * geometry.repetitions, photons_per_dwell=500, empty_every=4)
    payload = simulated_raw(simulation)
    raw.write_bytes(payload[:-6] if partial else payload)
    metadata = create_metadata(raw, geometry, dict(comment="Sample α", groups={
        "configurationGUI": dict(nx=geometry.width, ny=geometry.height, nframe=geometry.frames,
                                  nrep=geometry.repetitions),
        "configurationFPGA": dict(max_pixel=geometry.width)}))
    update_status(raw, dict(state="stopped" if partial else "complete"))
    with h5py.File(metadata, "r+") as file:
        file.attrs["schema_version"] = 999  # Must not replace the TDC output schema.
        file.create_dataset("thumbnail", data=np.arange(8, dtype=np.uint8))
        file.create_group("custom").attrs["units"] = "µm"
        file.create_dataset("custom/calibration", data=[1.25, 2.5])
        dataset = file.create_dataset("data", data=[123456])
        dataset.attrs["source_units"] = "original counts"
    return raw, metadata, geometry, simulation


@pytest.mark.parametrize("formats", [("tdc",), ("intensity",), ("tdc", "intensity")])
def test_selected_outputs_preserve_metadata_and_decoded_values(tmp_path, formats):
    raw, metadata, geometry, simulation = recording(tmp_path)
    paths = tdc_output_paths(raw)
    outputs = convert_tdc_raw(raw, **{kind + "_output": paths[kind] for kind in formats})
    assert set(outputs) == {paths[kind] for kind in formats}
    for kind in formats:
        with h5py.File(paths[kind]) as file:
            assert file.attrs["comment"] == "Sample α"
            assert file["configurationGUI"].attrs["nx"] == 3
            assert file["custom"].attrs["units"] == "µm"
            np.testing.assert_array_equal(file["custom/calibration"][:], [1.25, 2.5])
            np.testing.assert_array_equal(file["thumbnail"][:], np.arange(8, dtype=np.uint8))
            assert file["acquisition_metadata"].attrs["schema_version"] == 999
            assert file["acquisition_metadata/data"].attrs["source_units"] == "original counts"
            assert isinstance(file["acquisition_metadata/data"], h5py.Group)  # No image payload copy.
            assert file["conversion"].attrs["metadata_source"] == str(metadata)
            assert file["conversion"].attrs["source_bytes"] == raw.stat().st_size
            if kind == "tdc":
                assert file.attrs["schema_version"] == 3
                assert file.attrs["default"] == "event_table"
                expected = pispad.read_raw(raw)
                for name in ("event_id", "coarse", "fine_or_wrap"):
                    np.testing.assert_array_equal(file[name][:], expected[name])
            else:
                assert file["data"].shape == (2, 2, 2, 3, 1, 25)
                assert file["data"].dtype == np.uint32
                assert file["pispad23_microimages"].attrs["complete"]
                for dwell in range(24):
                    frame, pixel = divmod(dwell, 6)
                    rep, z = divmod(frame, 2)
                    z = 1 - z if rep % 2 else z
                    y, x = divmod(pixel, 3)
                    x = 2 - x if y % 2 else x
                    expected = np.zeros(25, dtype=np.uint32)
                    if dwell % 4:
                        for photon in range(500):
                            expected[(dwell + photon) % 25] += 1
                    np.testing.assert_array_equal(file["data"][rep, z, y, x, 0], expected)
    assert raw.read_bytes() == simulated_raw(simulation)
    assert not list(tmp_path.glob(".pispad-convert-*"))


def test_partial_raw_has_explicit_missing_dwell_validity(tmp_path):
    raw, _, _, _ = recording(tmp_path, geometry=ScanGeometry(2, 1, 1, 1, 0.001), partial=True)
    path = tmp_path / "intensity.h5"
    convert_tdc_raw(raw, intensity_output=path)
    with h5py.File(path) as file:
        assert not file["pispad23_microimages"].attrs["complete"]
        np.testing.assert_array_equal(file["pispad23_microimages/valid"][0, 0], [[True, False]])
        assert not file["data"][0, 0, 0, 1].any()
        assert file["acquisition_metadata"].attrs["acquisition_status"] == "stopped"


def test_missing_metadata_requires_explicit_geometry_for_intensity(tmp_path):
    raw = tmp_path / "standalone.raw"
    raw.write_bytes(simulated_raw(SimulationConfig(width=2, height=1, frames=1)))
    with pytest.raises(ValueError, match="geometry"):
        convert_tdc_raw(raw, intensity_output=tmp_path / "counts.h5")
    path = tmp_path / "events.h5"
    convert_tdc_raw(raw, tdc_output=path)
    with h5py.File(path) as file:
        assert not file["conversion"].attrs["acquisition_metadata_available"]
    convert_tdc_raw(raw, intensity_output=tmp_path / "counts.h5",
                    geometry=ScanGeometry(2, 1, 1, 1, 0.001))


def test_existing_output_or_failed_second_conversion_publishes_nothing(tmp_path):
    raw, _, _, _ = recording(tmp_path)
    events, counts = tmp_path / "events.h5", tmp_path / "counts.h5"
    events.write_bytes(b"precious")
    with pytest.raises(FileExistsError):
        convert_tdc_raw(raw, tdc_output=events, intensity_output=counts)
    assert events.read_bytes() == b"precious" and not counts.exists()
    # Missing acquisition metadata prevents a half-published pair of outputs.
    sidecar_path(raw).unlink()
    with pytest.raises(ValueError):
        convert_tdc_raw(raw, tdc_output=tmp_path / "new.h5", intensity_output=counts)
    assert not (tmp_path / "new.h5").exists() and not counts.exists()


def test_cancel_cleans_staged_outputs(tmp_path):
    raw, _, _, _ = recording(tmp_path)
    stop = threading.Event()
    def cancel(value, message):
        if "Reconstructing" in message:
            stop.set()
    outputs = tdc_output_paths(raw)
    with pytest.raises(ConversionCancelled):
        convert_tdc_raw(raw, tdc_output=outputs["tdc"], intensity_output=outputs["intensity"],
                        progress_callback=cancel, cancel_event=stop)
    assert not any(p.exists() for p in outputs.values())
    assert not list(tmp_path.glob(".pispad-convert-*"))


def test_companion_mcs_file_detection_and_geometry(tmp_path):
    raw = tmp_path / "scan-ts.raw"
    raw.touch()
    metadata = tmp_path / "scan.h5"
    with h5py.File(metadata, "w") as file:
        data = file.create_dataset("data", (2, 3, 4, 5, 1, 25), dtype="u4")
        data.attrs["dwell_seconds"] = 0.003
        file.create_group("pispad23_microimages").attrs["snake_walk_xy"] = True
    assert find_metadata(raw) == metadata
    assert read_geometry(metadata) == ScanGeometry(5, 4, 3, 2, 0.003, snake=True)


def test_active_acquisition_cannot_be_converted(tmp_path):
    raw, metadata, _, _ = recording(tmp_path)
    with h5py.File(metadata, "r+") as file:
        file.attrs["acquisition_status"] = "running"
    with pytest.raises(ValueError, match="still active"):
        convert_tdc_raw(raw, tdc_output=tmp_path / "events.h5")
