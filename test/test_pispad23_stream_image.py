"""Protocol validation uses local sockets only."""

from types import SimpleNamespace

import numpy as np
import pytest

from brighteyes_mcs.acquisition.detectors.pispad23.microimage import MicroimageSnapshot
from brighteyes_mcs.acquisition.detectors.factory import create_detector_pipeline
from brighteyes_mcs.acquisition.detectors.models import (
    DETECTOR_DISABLED, DETECTOR_PISPAD23_TS_UIMG, DETECTOR_PISPAD23, DETECTOR_PISPAD23_TT, DETECTOR_PISPAD23_UI,
    detector_uses_nifpga_fifo, normalize_detector_model,
)
from brighteyes_mcs.acquisition.detectors.pispad23.pipeline import PISPAD23DetectorPipeline
from brighteyes_mcs.acquisition.detectors.pispad23.timestamp_pipeline import PISPAD23MicroimagePipeline
from brighteyes_mcs.acquisition.detectors.pispad23.microimage import MicroimagePreview
from brighteyes_mcs.acquisition.manager import _pispad23_nifpga_dimension_registers


def test_timestamp_detector_controls_fpga_without_intensity_receiver():
    model = DETECTOR_PISPAD23_TS_UIMG
    assert normalize_detector_model(model) == model
    assert not detector_uses_nifpga_fifo(model)
    pipeline = create_detector_pipeline(model)
    assert isinstance(pipeline, PISPAD23MicroimagePipeline)
    assert not isinstance(pipeline, PISPAD23DetectorPipeline)
    assert pipeline.detector_model == model
    assert pipeline.make_receiver_process(None, None, None) is None
    worker = pipeline.make_acquisition_loop(SimpleNamespace(dim_x=3, dim_y=2, shared_dict={}, shared_objects={}), True)
    assert worker is not None
    assert pipeline.make_raw_stream_writer(None, None) is None
    registers = {"max_pixel": 3, "max_line": 2, "max_frame": 1}
    physical = _pispad23_nifpga_dimension_registers(registers, model)
    assert physical == {"max_pixel": 4, "max_line": 3, "max_frame": 2}
    assert _pispad23_nifpga_dimension_registers(physical, model, -1) == registers


@pytest.mark.parametrize("label", ["TCP/IP - PI SPAD23R (TS mode)", "TCP/IP - PI SPAD23R (TS mode - img)"])
def test_retired_timestamp_labels_disable_detector(label):
    assert normalize_detector_model(label) == DETECTOR_DISABLED
    assert create_detector_pipeline(label).detector_model == DETECTOR_DISABLED


@pytest.mark.parametrize("label", [DETECTOR_PISPAD23, DETECTOR_PISPAD23_UI, DETECTOR_PISPAD23_TT])
def test_intensity_detector_selects_its_pipeline(label):
    expected = DETECTOR_PISPAD23_TT if label == DETECTOR_PISPAD23_TT else DETECTOR_PISPAD23
    assert normalize_detector_model(label) == expected
    assert isinstance(create_detector_pipeline(label), PISPAD23DetectorPipeline)


def microimage(frame=0, x=0, y=0, flags=3, counts=None):
    counts = np.arange(25, dtype=np.uint32) if counts is None else counts
    return MicroimageSnapshot(counts, frame, x, y, int(counts.sum()), flags)


def test_microimage_preview_preserves_channels_and_zero_pixels_without_double_counting():
    preview = MicroimagePreview(3, 2)
    snapshot = microimage(x=2, y=1)
    assert preview.consume(snapshot)
    assert not preview.consume(snapshot)
    assert preview.image()[1, 2] == 300
    assert preview.image("24")[1, 2] == 24
    assert np.count_nonzero(preview.seen) == 1
    assert preview.consume(microimage(counts=np.zeros(25, dtype=np.uint32)))
    assert preview.image()[0, 0] == 0
    assert preview.image()[0, 1] == 0


def test_microimage_preview_ignores_invalid_dwells_and_replaces_pixels_across_frames():
    preview = MicroimagePreview(3, 2)
    assert preview.consume(microimage())
    assert not preview.consume(microimage(flags=1))
    assert not preview.consume(microimage(x=3))
    assert not preview.consume(microimage(y=2))
    assert preview.consume(microimage(frame=1, x=1))
    assert preview.image()[0, 0] == 300
    assert preview.image()[0, 1] == 300
    assert preview.frame_dwells == 1
    np.testing.assert_array_equal(preview.fingerprints[0], np.arange(25).reshape(5, 5))
    assert preview.consume(microimage(frame=1, counts=np.zeros(25, dtype=np.uint32)))
    assert preview.image()[0, 0] == 0  # A real zero-photon dwell replaces old data.
    assert preview.image()[0, 1] == 300
    with pytest.raises(ValueError, match="order reversed"):
        preview.consume(microimage())


def test_microimage_snake_mapping_and_large_counts():
    preview = MicroimagePreview(3, 2, snake=True)
    counts = np.full(25, 2**32 - 1, dtype=np.uint32)
    preview.consume(microimage(y=1, counts=counts, flags=7))
    assert preview.image()[1, 2] == 25 * (2**32 - 1)
    assert preview.image()[1, 0] == 0


def test_microimage_pipeline_publishes_channel_image_fingerprint_mask_and_repeat_counts():
    from brighteyes_mcs.acquisition.shared_memory import SharedMemoryRegistry
    from brighteyes_mcs.acquisition.preview import PreviewRepository

    arrays = SharedMemoryRegistry().allocate_preview(
        dim_x=3, dim_y=2, dim_z=1, detector_dim=5,
        autocorrelation_maxx=2, trace_bins=2, dfd_bins=2,
    )
    preview = MicroimagePreview(3, 2, shared_objects=arrays)
    repository = PreviewRepository()
    repository.bind(arrays)
    vectors = []
    for i in range(6):
        counts = np.arange(25, dtype=np.uint32) * (i + 1) * 100
        vectors.append(counts)
        assert preview.consume(microimage(x=i % 3, y=i // 3, counts=counts))
    preview.publish("24")
    np.testing.assert_array_equal(repository.get_preview_image(), [[2400, 4800, 7200], [9600, 12000, 14400]])
    expected = np.sum(vectors, axis=0).reshape(5, 5)
    np.testing.assert_array_equal(repository.get_fingerprint(0), expected)
    np.testing.assert_array_equal(repository.get_fingerprint(2), expected)
    np.testing.assert_array_equal(repository.get_fingerprint(3), expected)
    np.testing.assert_allclose(preview.fingerprint_rate(0, 0.001), expected / 0.006)
    mask = np.zeros(25, dtype=np.uint8)
    mask[24] = 1
    np.testing.assert_array_equal(preview.publish(mask=mask), preview.image("24"))
    preview.consume(microimage(frame=1, counts=vectors[0]))
    np.testing.assert_array_equal(preview.fingerprints[3], expected)
    assert preview.image("24")[0, 0] == 2400
    preview.publish("24")
    np.testing.assert_array_equal(repository.get_preview_image(), [[2400, 4800, 7200], [9600, 12000, 14400]])
    assert preview.publish("24", accumulate=True)[0, 0] == 4800
    assert preview.frame_dwells == 1 and preview.total_dwells == 7


def test_microimage_recent_fingerprint_is_rolling_10000_dwells():
    preview = MicroimagePreview(1, 1)
    for frame in range(10005):
        counts = np.full(25, frame, dtype=np.uint32)
        preview.consume(microimage(frame=frame, counts=counts))
    np.testing.assert_array_equal(preview.fingerprints[2], np.full((5, 5), sum(range(5, 10005))))
    np.testing.assert_array_equal(preview.fingerprints[0], np.full((5, 5), 10004))
