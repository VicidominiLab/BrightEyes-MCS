"""Protocol validation uses local sockets only."""

import socket
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from brighteyes_mcs.acquisition.detectors.pi23.stream_image import (
    HEADER, TRAILER, read_snapshot, read_microimage, stream_microimages, MicroimageSnapshot,
)
from brighteyes_mcs.acquisition.detectors.factory import create_detector_pipeline
from brighteyes_mcs.acquisition.detectors.models import (
    DETECTOR_PI23_TS, DETECTOR_PI23_TS_UIMG, DETECTOR_PI_23, DETECTOR_PI23_UI,
    detector_uses_nifpga_fifo, normalize_detector_model,
)
from brighteyes_mcs.acquisition.detectors.pi23.pipeline import Pi23DetectorPipeline
from brighteyes_mcs.acquisition.detectors.pi23.timestamp_pipeline import Pi23TimestampPipeline, Pi23MicroimagePipeline
from brighteyes_mcs.acquisition.detectors.pi23.microimage import MicroimagePreview
from brighteyes_mcs.acquisition.manager import _pi23_nifpga_dimension_registers


@pytest.mark.parametrize("model,pipeline_class", [(DETECTOR_PI23_TS, Pi23TimestampPipeline), (DETECTOR_PI23_TS_UIMG, Pi23MicroimagePipeline)])
def test_timestamp_detector_controls_fpga_without_intensity_receiver(model, pipeline_class):
    assert normalize_detector_model(model) == model
    assert not detector_uses_nifpga_fifo(model)
    pipeline = create_detector_pipeline(model)
    assert isinstance(pipeline, pipeline_class)
    assert not isinstance(pipeline, Pi23DetectorPipeline)
    assert pipeline.detector_model == model
    assert pipeline.make_receiver_process(None, None, None) is None
    worker = pipeline.make_acquisition_loop(SimpleNamespace(dim_x=3, dim_y=2, shared_dict={}, shared_objects={}), True)
    assert (worker is not None) == (model == DETECTOR_PI23_TS_UIMG)
    assert pipeline.make_raw_stream_writer(None, None) is None
    registers = {"max_pixel": 3, "max_line": 2, "max_frame": 1}
    physical = _pi23_nifpga_dimension_registers(registers, model)
    assert physical == {"max_pixel": 4, "max_line": 3, "max_frame": 2}
    assert _pi23_nifpga_dimension_registers(physical, model, -1) == registers


def test_old_timestamp_label_selects_image_mode():
    assert normalize_detector_model("TCP/IP - PI23 (TS mode)") == DETECTOR_PI23_TS


@pytest.mark.parametrize("label", ["TCP/IP - PI23", DETECTOR_PI23_UI, "TCP/IP - PI23 (Intensity)"])
def test_renamed_intensity_detector_keeps_original_pipeline_and_configurations(label):
    assert normalize_detector_model(label) == DETECTOR_PI_23
    assert isinstance(create_detector_pipeline(label), Pi23DetectorPipeline)


@pytest.mark.parametrize("microimage", [False, True])
@pytest.mark.parametrize("fault", [None, "not_ready", "dimensions", "size", "trailer", "truncated", "version", "magic"])
def test_snapshot_framing_and_non_square_orientation(fault, microimage):
    payload = np.arange(25 if microimage else 6, dtype="<u4").tobytes()
    status = 1 if fault == "not_ready" else 0
    if status:
        payload = b""
    size = len(payload)
    packet = HEADER.pack(
        b"INVALID!" if fault == "magic" else b"TDCMIC01" if microimage else b"TDCIMG01",
        2 if fault == "version" else 1, status,
        2 if fault == "dimensions" else 25 if microimage else 3,
        1 if microimage else 2, -1, 3 if microimage else 2, 7, 2, 1, 15,
        2**40 if fault == "size" else size,
    ) + payload + TRAILER.pack(b"BADEND01" if fault == "trailer" else b"TDCEND01", 7, size)
    if fault == "truncated":
        packet = packet[:70]
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        requests = []

        def serve():
            connection, _ = server.accept()
            with connection:
                connection.settimeout(2)
                requests.append(connection.recv(64))
                try:
                    # Deliberately fragment both header and payload.
                    for offset in range(0, len(packet), 7):
                        connection.sendall(packet[offset:offset + 7])
                except OSError:
                    pass

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        def read():
            return read_microimage(server.getsockname()[1]) if microimage else read_snapshot(server.getsockname()[1], 3, 2)
        if fault not in (None, "not_ready"):
            with pytest.raises(ValueError):
                read()
        else:
            snapshot = read()
            if status:
                assert snapshot is None
            else:
                expected = np.arange(25) if microimage else [[0, 1, 2], [3, 4, 5]]
                np.testing.assert_array_equal(snapshot.counts, expected)
                assert snapshot.frame == 7 and snapshot.events == 15
                if microimage:
                    assert (snapshot.x, snapshot.y) == (2, 1)
        thread.join(timeout=3)
        assert requests == [b"LAST\n" if microimage else b"PREVIEW\n"]


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


@pytest.mark.parametrize("clean_end", [True, False])
def test_microimage_subscription_delivers_burst_and_rejects_unexpected_disconnect(clean_end):
    def packet(index=None):
        payload = b"" if index is None else np.full(25, index, dtype="<u4").tobytes()
        frame = 0 if index is None else index // 200
        return (HEADER.pack(b"TDCMIC01", 1, int(index is None), 25, 1, -1,
                            3, frame, 0 if index is None else index % 200,
                            0, 0 if index is None else index * 25, len(payload))
                + payload + TRAILER.pack(b"TDCEND01", frame, len(payload)))

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        requests = []
        def serve():
            connection, _ = server.accept()
            with connection:
                requests.append(connection.recv(64))
                data = packet() + b"".join(packet(i) for i in range(2000))
                if clean_end:
                    data += packet()
                for offset in range(0, len(data), 1001):
                    connection.sendall(data[offset:offset + 1001])
        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        connected = threading.Event()
        snapshots = []
        def receive():
            for batch in stream_microimages(server.getsockname()[1], threading.Event(), connected):
                snapshots.extend(batch)
        if clean_end:
            receive()
            assert len(snapshots) == 2000
            assert [s.events for s in snapshots] == list(range(0, 2000 * 25, 25))
        else:
            with pytest.raises(ValueError, match="disconnected before completion"):
                receive()
        assert connected.is_set()
        worker.join(timeout=2)
        assert requests == [b"STREAM\n"]
