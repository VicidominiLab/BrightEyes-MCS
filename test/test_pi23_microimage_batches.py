"""Sequence retries, overflow reporting, and processing independent of Qt."""

import multiprocessing as mp
import socket
import threading

import numpy as np
import pytest

from brighteyes_mcs.acquisition.detectors.pi23.microimage_stream import (
    BATCH_HEADER, BATCH_TRAILER, DWELL_DTYPE, MicroimageBatch, read_batch, buffered_microimages,
)
from brighteyes_mcs.acquisition.detectors.pi23.microimage_worker import MicroimageWorker
from brighteyes_mcs.acquisition.shared_memory import SharedMemoryRegistry
from brighteyes_mcs.acquisition.preview import PreviewRepository


def records(count):
    result = np.zeros(count, dtype=DWELL_DTYPE)
    index = np.arange(count)
    result["frame"] = index // 5000
    result["x"] = index % 100
    result["y"] = index // 100 % 50
    result["counts"] = index[:, None] % 5000 + np.arange(25)[None, :] + 100
    result["events"] = result["counts"].sum(axis=1)
    result["flags"] = 3
    return result


def packet(data, first=0, *, end=None, oldest=0, status=0, finished=False, session=123):
    end = first + len(data) if end is None else end
    payload = data.tobytes()
    return (BATCH_HEADER.pack(b"TDCBAT01", 1, status, len(data), int(finished), session,
                              first, oldest, end, 100000, len(payload))
            + payload + BATCH_TRAILER.pack(b"TDCBEND1", first, len(payload)))


class FragmentedSocket:
    def __init__(self, data):
        self.data = data
        self.commands = []

    def sendall(self, command):
        self.commands.append(command)

    def recv(self, size):
        part, self.data = self.data[:min(size, 7)], self.data[min(size, 7):]
        return part


def test_worker_delay_counts_recorder_and_local_backlog_then_drains(monkeypatch):
    from brighteyes_mcs.acquisition.detectors.pi23 import microimage_worker

    data = records(10)
    queued, processing_second, release = threading.Event(), threading.Event(), threading.Event()

    def receive(*args):
        for first in (0, 1):
            yield MicroimageBatch(data[first:first + 1], 123, first, 0, 10, 100, False)
        queued.set()
        assert release.wait(5)
        yield MicroimageBatch(data[2:], 123, 2, 0, 10, 100, True)

    original_consume = microimage_worker.MicroimagePreview.consume
    def consume(preview, snapshot):
        if snapshot.x == 0:
            assert queued.wait(5)
        elif snapshot.x == 1:
            processing_second.set()
            assert release.wait(5)
        return original_consume(preview, snapshot)

    monkeypatch.setattr(microimage_worker, "buffered_microimages", receive)
    monkeypatch.setattr(microimage_worker.MicroimagePreview, "consume", consume)
    arrays = SharedMemoryRegistry().allocate_preview(dim_x=100, dim_y=50, dim_z=1,
        detector_dim=5, autocorrelation_maxx=2, trace_bins=2, dfd_bins=2)
    shared = {"channel": "Sum"}
    worker = MicroimageWorker(100, 50, 19000, 4096, arrays, shared)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    try:
        assert processing_second.wait(5)
        status = shared["pi23_uimg_status"]
        assert status["sequence"] == 1
        assert status["available"] == 8
        assert status["local_pending"] == 1
        assert status["pending_dwells"] == 9
        release.set()
        assert worker.done.wait(5)
        assert not worker.error
        status = shared["pi23_uimg_status"]
        assert status["sequence"] == 10
        assert status["available"] == status["local_pending"] == status["pending_dwells"] == 0
    finally:
        release.set()
        worker.stop()
        thread.join(timeout=3)


@pytest.mark.parametrize("fault", [None, "empty", "overflow", "future", "size", "trailer", "truncated", "sequence"])
def test_batch_framing_and_partial_availability(fault):
    data = records(3)
    if fault in ("empty", "overflow", "future"):
        data = records(0)
    response = bytearray(packet(data, first=int(fault == "sequence"),
        oldest=1 if fault == "overflow" else 0, end=3,
        status={"overflow": 3, "future": 4}.get(fault, 0)))
    if fault == "size":
        response[64:72] = (2**40).to_bytes(8, "little")
    if fault == "trailer":
        response[-24] = 0
    if fault == "truncated":
        response = response[:-1]
    sock = FragmentedSocket(response)
    if fault not in (None, "empty"):
        with pytest.raises((ValueError, EOFError)):
            read_batch(sock, 0, 100, threading.Event())
    else:
        batch = read_batch(sock, 0, 100, threading.Event())
        np.testing.assert_array_equal(batch.records, data)
        assert len(batch.records) == (0 if fault == "empty" else 3)
    assert sock.commands == [b"READ 0 100\n"]


@pytest.mark.parametrize("changed_session", [False, True])
def test_interrupted_batch_retries_same_cursor_without_duplicates(changed_session):
    data = records(4)
    errors, requests = [], []
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(2)
        server.settimeout(5)

        def serve():
            try:
                for attempt in range(2):
                    connection, _ = server.accept()
                    with connection, connection.makefile("rb") as stream:
                        connection.settimeout(5)
                        requests.append(stream.readline())
                        if attempt == 0:
                            connection.sendall(packet(data[:2], end=4))
                            requests.append(stream.readline())
                            connection.sendall(packet(data[2:], first=2, end=4)[:100])
                        else:
                            connection.sendall(packet(data[2:], first=2, end=4, finished=True,
                                                      session=456 if changed_session else 123))
                            if not changed_session:
                                requests.append(stream.readline())
                                connection.sendall(packet(data[:0], first=4, finished=True))
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        received = []
        def receive():
            for batch in buffered_microimages(server.getsockname()[1], 100, threading.Event(), threading.Event()):
                received.append(batch.records)
        if changed_session:
            with pytest.raises(ValueError, match="session changed"):
                receive()
        else:
            receive()
            np.testing.assert_array_equal(np.concatenate(received), data)
        thread.join(timeout=5)
        assert not errors
        assert requests[:3] == [b"READ 0 100\n", b"READ 2 100\n", b"READ 2 100\n"]


def test_worker_drains_large_burst_and_changes_channel_without_gui_events():
    data = records(30000)
    errors, requests = [], []
    with socket.socket() as server, mp.Manager() as manager:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(10)

        def serve():
            try:
                connection, _ = server.accept()
                with connection, connection.makefile("rb") as stream:
                    connection.settimeout(10)
                    while True:
                        command = stream.readline().decode().split()
                        assert command[0] == "READ"
                        first, limit = map(int, command[1:])
                        requests.append((first, limit))
                        # Available batches may be shorter than requested.
                        batch = data[first:first + min(limit, 1300)]
                        connection.sendall(packet(batch, first, end=len(data), finished=True))
                        if first == len(data):
                            break
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        shared = manager.dict(channel="24")
        arrays = SharedMemoryRegistry().allocate_preview(dim_x=100, dim_y=50, dim_z=1,
            detector_dim=5, autocorrelation_maxx=2, trace_bins=2, dfd_bins=2)
        repository = PreviewRepository()
        repository.bind(arrays)
        worker = MicroimageWorker(100, 50, server.getsockname()[1], 4096, arrays, shared)
        worker.start()
        try:
            assert worker.done.wait(15)
            assert not worker.error and not errors
            assert shared["pi23_uimg_status"]["total_dwells"] == 30000
            np.testing.assert_array_equal(repository.get_preview_image(), data[-5000:]["counts"][:, 24].reshape(50, 100))
            np.testing.assert_array_equal(repository.get_fingerprint(0).ravel(), data[-5000:]["counts"].sum(axis=0))
            shared["channel"] = "Sum"
            import time
            deadline = time.monotonic() + 3
            expected = data[-5000:]["counts"].sum(axis=1).reshape(50, 100)
            while not np.array_equal(repository.get_preview_image(), expected):
                assert time.monotonic() < deadline
                time.sleep(0.02)
            assert requests[-1] == (30000, 4096)
        finally:
            worker.stop()
            worker.join(timeout=3)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=2)
        thread.join(timeout=2)
