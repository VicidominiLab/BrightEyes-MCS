"""Version 1 full-image and microimage snapshots from tdc_raw_acquire."""

from dataclasses import dataclass
import socket
import select
import struct
import time

import numpy as np


HEADER = struct.Struct("<8sIIIIiIQIIQQ")
TRAILER = struct.Struct("<8sQQ")


@dataclass(frozen=True)
class ImageSnapshot:
    counts: np.ndarray
    frame: int
    events: int
    flags: int


@dataclass(frozen=True)
class MicroimageSnapshot:
    counts: np.ndarray
    frame: int
    x: int
    y: int
    events: int
    flags: int


def read_snapshot(port, width, height, timeout=2.0):
    """Request the current image from the locally launched Rust process.

    Validate dimensions and framing before exposing counts. A not-ready reply
    is normal before the first frame marker and returns None.
    """
    packet = _read_packet(port, width, height, b"TDCIMG01", b"PREVIEW\n", timeout)
    if packet is None:
        return None
    counts, frame, x, y, events, flags = packet
    return ImageSnapshot(counts.reshape(height, width), frame, events, flags)


def read_microimage(port, timeout=2.0):
    """Read the most recent completed dwell, preserving all 25 detector IDs."""
    packet = _read_packet(port, 25, 1, b"TDCMIC01", b"LAST\n", timeout)
    if packet is None:
        return None
    counts, frame, x, y, events, flags = packet
    if not flags & 1:
        raise ValueError("PI23 microimage is not a completed dwell")
    return MicroimageSnapshot(counts, frame, x, y, events, flags)


def _read_packet(port, width, height, expected_magic, request, timeout):
    deadline = time.monotonic() + timeout
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
        def receive(size):
            data = bytearray()
            while len(data) < size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("PI23 image snapshot timed out")
                connection.settimeout(remaining)
                part = connection.recv(min(size - len(data), 65536))
                if not part:
                    raise ValueError("Truncated PI23 image snapshot")
                data.extend(part)
            return data

        connection.sendall(request)
        return _decode_packet(receive, width, height, expected_magic)


def _decode_packet(receive, width, height, expected_magic):
    magic, version, status, nx, ny, pixel, flags, frame, x, y, events, size = (
        HEADER.unpack(receive(HEADER.size))
    )
    if magic != expected_magic or version != 1 or status not in (0, 1):
        raise ValueError("Invalid PI23 image header")
    if (nx, ny) != (width, height) or not 0 < nx * ny <= 16_777_216:
        raise ValueError("PI23 image dimensions do not match the scan")
    if pixel != -1 or size != (nx * ny * 4 if status == 0 else 0):
        raise ValueError("Invalid PI23 image payload")
    payload = receive(size)
    if TRAILER.unpack(receive(TRAILER.size)) != (b"TDCEND01", frame, size):
        raise ValueError("Invalid PI23 image trailer")
    if status == 1:
        return None
    return np.frombuffer(payload, dtype="<u4"), frame, x, y, events, flags


def stream_microimages(port, stop, connected):
    """Yield every completed dwell; acknowledge subscription before FPGA start.

    No automatic reconnect after registration: that would hide missing pixels.
    The initial status=1 is the subscription ACK, the final one a clean end.
    """
    with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
        connection.sendall(b"STREAM\n")
        connection.settimeout(0.2)

        def receive(size):
            data = bytearray()
            while len(data) < size:
                if stop.is_set():
                    raise InterruptedError("Microimage stream stopped")
                try:
                    part = connection.recv(size - len(data))
                except socket.timeout:
                    continue
                if not part:
                    raise ValueError("PI23 microimage stream disconnected before completion")
                data.extend(part)
            return data

        if _decode_packet(receive, 25, 1, b"TDCMIC01") is not None:
            raise ValueError("Missing PI23 microimage subscription acknowledgement")
        connected.set()
        batch = []
        while not stop.is_set():
            packet = _decode_packet(receive, 25, 1, b"TDCMIC01")
            if packet is None:
                if batch:
                    yield batch
                return
            counts, frame, x, y, events, flags = packet
            if flags & 3 != 3:
                raise ValueError("PI23 microimage is not a valid completed dwell")
            batch.append(MicroimageSnapshot(counts, frame, x, y, events, flags))
            if len(batch) >= 256 or not select.select([connection], [], [], 0)[0]:
                yield batch
                batch = []
