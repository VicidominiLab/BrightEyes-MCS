"""Buffered, sequence-addressed PI23 dwell batches on the preview TCP port."""

from dataclasses import dataclass
import socket
import struct
import time

import numpy as np


BATCH_HEADER = struct.Struct("<8sIIIIQQQQQQ")
BATCH_TRAILER = struct.Struct("<8sQQ")
DWELL_DTYPE = np.dtype([
    ("frame", "<u8"), ("x", "<u4"), ("y", "<u4"), ("events", "<u8"),
    ("flags", "<u4"), ("counts", "<u4", (25,)),
])


@dataclass(frozen=True)
class MicroimageBatch:
    records: np.ndarray
    session: int
    sequence: int
    oldest: int
    next_sequence: int
    capacity: int
    finished: bool


def read_batch(connection, sequence, limit, stop):
    if not 1 <= limit <= 65536:
        raise ValueError("PI23 batch size must be 1..65536 dwells")
    connection.sendall(f"READ {sequence} {limit}\n".encode("ascii"))
    deadline = time.monotonic() + 5

    def receive(size):
        data = bytearray()
        while len(data) < size:
            if stop.is_set():
                raise InterruptedError("Microimage read stopped")
            if time.monotonic() >= deadline:
                raise TimeoutError("PI23 batch response timed out")
            try:
                part = connection.recv(min(size - len(data), 262144))
            except socket.timeout:
                continue
            if not part:
                raise EOFError("PI23 batch response disconnected")
            data.extend(part)
        return data

    magic, version, status, count, flags, session, first, oldest, end, capacity, size = (
        BATCH_HEADER.unpack(receive(BATCH_HEADER.size))
    )
    if magic != b"TDCBAT01" or version != 1 or status not in (0, 2, 3, 4):
        raise ValueError("Invalid PI23 batch header; rebuild the Rust recorder with READ support")
    if (first != sequence or count > limit or size != count * DWELL_DTYPE.itemsize
            or flags & ~1 or not 1 <= capacity <= 8388608 or oldest > end
            or end - oldest > capacity or (status != 0 and count != 0)):
        raise ValueError("Invalid PI23 batch dimensions or sequence")
    if status == 0 and not oldest <= first <= first + count <= end:
        raise ValueError("Invalid PI23 batch sequence range")
    payload = receive(size)
    if BATCH_TRAILER.unpack(receive(BATCH_TRAILER.size)) != (b"TDCBEND1", first, size):
        raise ValueError("Invalid PI23 batch trailer")
    if status == 3:
        raise ValueError(f"PI23 microimage buffer overflow: lost {oldest - sequence} dwells; "
                         "increase the uimg buffer or reduce the scan rate")
    if status:
        raise ValueError(f"PI23 rejected batch request (status {status})")
    records = np.frombuffer(payload, dtype=DWELL_DTYPE)
    if np.any(records["flags"] & 3 != 3):
        raise ValueError("Invalid or incomplete dwell in PI23 batch")
    return MicroimageBatch(records, session, first, oldest, end, capacity, bool(flags & 1))


def buffered_microimages(port, limit, stop, connected):
    """Retry interrupted reads at the same cursor; never cross recorder sessions."""
    sequence, session, retries = 0, None, 0
    while not stop.is_set():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1) as connection:
                connection.settimeout(0.2)
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                while not stop.is_set():
                    batch = read_batch(connection, sequence, limit, stop)
                    if session is not None and batch.session != session:
                        raise ValueError("PI23 recorder session changed during acquisition")
                    session = batch.session
                    connected.set()
                    retries = 0
                    yield batch
                    sequence += len(batch.records)
                    # An empty final READ acknowledges that all previous batches
                    # reached our local processing queue; Rust can now close.
                    if batch.finished and not len(batch.records) and sequence == batch.next_sequence:
                        return
                    if not len(batch.records):
                        stop.wait(0.005)
        except (OSError, EOFError):
            if stop.is_set():
                return
            retries += 1
            if connected.is_set() and retries > 3:
                raise
            stop.wait(0.1)
