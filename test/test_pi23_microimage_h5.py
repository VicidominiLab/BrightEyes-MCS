"""Saved dwell frames never use pixels retained by the live preview."""

import h5py
import numpy as np
import pytest

from brighteyes_mcs.storage.pi23_microimage import MicroimageH5Writer
from brighteyes_mcs.acquisition.detectors.pi23.stream_image import MicroimageSnapshot
from brighteyes_mcs.acquisition.detectors.pi23.timestamp_pipeline import Pi23MicroimagePipeline


def dwell(frame, x, y, value, flags=3):
    counts = np.full(25, value, dtype=np.uint32)
    return MicroimageSnapshot(counts, frame, x, y, int(counts.sum()), flags)


@pytest.mark.parametrize("preview", [False, True])
def test_pipeline_saves_only_acquisitions_and_uses_full_dwell_duration(tmp_path, preview):
    from types import SimpleNamespace
    acquisition = SimpleNamespace(dim_x=3, dim_y=2, dim_z=4, dim_rep=5,
        shared_dict={}, shared_objects={}, filenameh5=str(tmp_path / "scan.h5"),
        time_resolution=10, timebins_per_pixel=100, circ_points=2, circ_repetition=3)
    worker = Pi23MicroimagePipeline().make_acquisition_loop(acquisition, preview)
    if preview:
        assert worker.saving is None
    else:
        assert worker.saving["filename"] == acquisition.filenameh5
        assert worker.saving["frames"] == 4 and worker.saving["repetitions"] == 5
        assert worker.saving["dwell_seconds"] == pytest.approx(0.006)


def test_h5_preserves_channels_frames_repetitions_and_snake_coordinates(tmp_path):
    path = tmp_path / "scan.h5"
    writer = MicroimageH5Writer(path, 3, 2, 2, 2, 0.001, snake=True, snake_z=True)
    for frame in range(4):
        for y in range(2):
            for x in range(3):
                writer.consume(dwell(frame, x, y, 100000 * frame + 10 * y + x))
    assert writer.close(finished=True)
    with h5py.File(path) as saved:
        assert saved["data"].shape == (2, 2, 2, 3, 1, 25)
        for frame in range(4):
            rep, z = divmod(frame, 2)
            if rep % 2:
                z = 1 - z
            for channel in range(25):
                np.testing.assert_array_equal(saved["data"][rep, z, :, :, 0, channel],
                    [[100000 * frame + x for x in range(3)],
                     [100000 * frame + 10 + x for x in (2, 1, 0)]])
        assert saved["pi23_microimages/valid"][...].all()
        assert saved["pi23_microimages/frame_complete"][...].all()
        assert saved["pi23_microimages"].attrs["complete"]
        assert saved["data"].attrs["dwell_seconds"] == 0.001


@pytest.mark.parametrize("finished", [False, True])
def test_partial_frame_has_no_old_pixels_and_distinguishes_missing_from_zero(tmp_path, finished):
    path = tmp_path / "partial.h5"
    writer = MicroimageH5Writer(path, 2, 1, 2, 1, 0.01)
    writer.consume(dwell(0, 0, 0, 90000))
    writer.consume(dwell(0, 1, 0, 60000))
    writer.consume(dwell(1, 0, 0, 0))
    writer.consume(dwell(1, 2, 0, 123))  # Synchronization dwell outside the scan.
    assert not writer.close(finished=finished)
    with h5py.File(path) as saved:
        assert not saved["pi23_microimages"].attrs["complete"]
        assert saved["pi23_microimages"].attrs["stop_reason"] == ("incomplete" if finished else "stopped")
        np.testing.assert_array_equal(saved["pi23_microimages/valid"][0, 1], [[True, False]])
        assert not saved["data"][0, 1].any()
        assert saved["data"][0, 0, 0, 1, 0, 24] == 60000


def test_missing_frame_is_not_renumbered_and_saturation_is_explicit(tmp_path):
    path = tmp_path / "missing.h5"
    writer = MicroimageH5Writer(path, 1, 1, 3, 1, 0.01)
    writer.consume(dwell(0, 0, 0, 4))
    writer.consume(dwell(2, 0, 0, 2**32 - 1, flags=7))
    assert not writer.close(finished=True)
    with h5py.File(path) as saved:
        np.testing.assert_array_equal(saved["pi23_microimages/frame_id"][0], [0, -1, 2])
        assert not saved["pi23_microimages/valid"][0, 1].any()
        assert saved["pi23_microimages/flags"][0, 2, 0, 0] == 7
        assert saved["data"][0, 2, 0, 0, 0, 0] == 2**32 - 1


def test_duplicate_and_existing_output_are_rejected(tmp_path):
    path = tmp_path / "scan.h5"
    writer = MicroimageH5Writer(path, 1, 1, 1, 1, 0.01)
    writer.consume(dwell(0, 0, 0, 4))
    with pytest.raises(ValueError, match="Duplicate"):
        writer.consume(dwell(0, 0, 0, 5))
    writer.close(error="Duplicate dwell")
    with pytest.raises((OSError, FileExistsError)):
        MicroimageH5Writer(path, 1, 1, 1, 1, 0.01)
    with h5py.File(path) as saved:
        assert saved["data"][0, 0, 0, 0, 0, 0] == 4
        assert saved["pi23_microimages"].attrs["stop_reason"] == "error"
