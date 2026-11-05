# SPDX-License-Identifier: MIT
"""SCP1/DFD3 decoder ported from brighteyes-flare/software/dfd_scope_format.py.

Source contract: firmware 1.9, 2026-11-03; MIT licensed.
"""

from dataclasses import dataclass
import struct

SCOPE_MAGIC = 0x53435031
DFD_MAGIC = 0x44464433
TAIL = 0x4446445F454E4421
SCOPE_NAMES = {5: "circular_point", 6: "circular_repetition", 7: "pixel", 8: "line", 9: "frame"}
HEADER_WORDS = 16


@dataclass(frozen=True)
class ScopeLayout:
    detector_channels: int
    total_records: int
    histogram_bins: int = 91

    def __post_init__(self):
        if type(self.detector_channels) is not int or self.detector_channels not in (25, 49):
            raise ValueError("unsupported DFD3 detector count")
        if type(self.total_records) is not int or not 0 < self.total_records <= 0xFFFFFFFF:
            raise ValueError("invalid DFD3 record count")
        if self.histogram_bins != 91:
            raise ValueError("unsupported DFD3 phase profile")

    @property
    def stream_channels(self):
        return self.detector_channels + 2

    @property
    def padded_channels(self):
        return (self.stream_channels + 3) // 4 * 4

    @property
    def payload_words(self):
        return self.histogram_bins * self.padded_channels // 2

    @property
    def record_bytes(self):
        return (HEADER_WORDS + 6 + self.payload_words) * 8

    @property
    def total_bytes(self):
        return self.record_bytes * self.total_records

    @property
    def max_packet_records(self):
        return min(4096, 8388607 // self.record_bytes)

    @classmethod
    def from_metadata(cls, metadata):
        if (
            metadata.get("stream_format") != "DFD3"
            or metadata.get("stream_format_version") != 3
            or metadata.get("count_bits") != 32
        ):
            raise ValueError("expected scoped uint32 DFD3 metadata")
        result = cls(
            metadata["detector_channels"], metadata["total_records"], metadata["histogram_bins"]
        )
        for key, value in dict(
            record_bytes=result.record_bytes,
            total_bytes=result.total_bytes,
            stream_channels=result.stream_channels,
            scope_header_words=HEADER_WORDS,
        ).items():
            if type(metadata.get(key)) is not int or metadata[key] != value:
                raise ValueError("inconsistent DFD3 " + key)
        return result


@dataclass(frozen=True)
class ScopeRecord:
    run_id: int
    ordinal: int
    scope: str
    partial: bool
    stopped: bool
    requested_boundaries: int
    completed_boundaries: int
    first_tick: int
    last_tick: int
    first_coordinates: tuple
    last_coordinates: tuple
    trajectory_id: int
    payload: bytes

    def counts(self, layout):
        import numpy as np

        return np.frombuffer(self.payload, dtype="<u4").reshape(
            layout.histogram_bins, layout.padded_channels
        )[:, : layout.stream_channels]


class ScopeDecoder:
    def __init__(self, layout, run_id=None, trajectory_id=None):
        self.trajectory_id = trajectory_id
        self.layout = layout
        self.run_id = run_id
        self.records = 0
        self.buffer = bytearray()
        self.stopped = False
        self._record_layout = (layout.record_bytes, layout.stream_channels, layout.padded_channels, layout.payload_words)

    def feed(self, data):
        self.buffer.extend(data)
        layout = self.layout
        # These are immutable for an acquisition. Avoid recomputing nested
        # layout properties for every padding word of every incoming record.
        record_bytes, stream_channels, padded_channels, payload_words = self._record_layout
        while len(self.buffer) >= record_bytes:
            raw = bytes(self.buffer[:record_bytes])
            del self.buffer[:record_bytes]
            head = struct.unpack_from("<16Q", raw)
            if head[0] != (SCOPE_MAGIC << 32 | HEADER_WORDS):
                raise ValueError("invalid DFD scope header")
            run, ordinal = head[1] >> 32, head[1] & 0xFFFFFFFF
            if self.run_id is None:
                self.run_id = run
            if (
                run != self.run_id
                or ordinal != self.records
                or self.stopped
                or self.records >= layout.total_records
            ):
                raise ValueError("DFD scope run/ordinal mismatch")
            scope, flags = head[2] >> 32, head[2] & 0xFFFFFFFF
            requested, completed = head[3] >> 32, head[3] & 0xFFFFFFFF
            if scope not in SCOPE_NAMES or flags & ~3 or flags & 2 and not flags & 1:
                raise ValueError("invalid DFD scope/flags")
            if not requested or completed > requested or not (flags & 2) and not completed:
                raise ValueError("invalid DFD grouping")
            if bool(flags & 1) != bool(completed < requested) and not flags & 2:
                raise ValueError("incorrect partial-group label")
            if head[5] < head[4]:
                raise ValueError("invalid exposure interval")
            if (
                head[13] & 0xFFFFFFFF != DFD_MAGIC
                or head[14] != (32 << 32 | 91)
                or head[15] != (payload_words << 32 | layout.detector_channels)
            ):
                raise ValueError("inconsistent scope layout")
            if self.trajectory_id is not None and head[13] >> 32 != self.trajectory_id:
                raise ValueError("DFD trajectory mismatch")
            inner = struct.unpack_from("<5Q", raw, HEADER_WORDS * 8)
            if inner[0] != (DFD_MAGIC << 32 | stream_channels << 16 | 91) or inner[1] != head[1]:
                raise ValueError("inconsistent histogram identity")
            if inner[4] != (payload_words << 32 | int(bool(flags & 1))):
                raise ValueError("inconsistent histogram length/partial flag")
            if struct.unpack_from("<Q", raw, len(raw) - 8)[0] != TAIL:
                raise ValueError("invalid DFD3 tail")
            payload = raw[(HEADER_WORDS + 5) * 8 : -8]
            # Scan each padding column with a native iterator. Zero is invariant
            # under byte order, so this check remains valid on either endian.
            # All phase bins are checked, without requiring numpy here.
            words = memoryview(payload).cast("I")
            for channel in range(stream_channels, padded_channels):
                if any(words[channel::padded_channels]):
                    raise ValueError("nonzero DFD3 padding")
            first = tuple(word >> 32 for word in head[6:13])
            last = tuple(word & 0xFFFFFFFF for word in head[6:13])
            record = ScopeRecord(
                run,
                ordinal,
                SCOPE_NAMES[scope],
                bool(flags & 1),
                bool(flags & 2),
                requested,
                completed,
                head[4],
                head[5],
                first,
                last,
                head[13] >> 32,
                payload,
            )
            self.records += 1
            self.stopped = record.stopped
            yield record

    def finish(self, cancelled=False):
        if self.buffer:
            raise ValueError("truncated scoped DFD record")
        if not cancelled and (self.records != self.layout.total_records or self.stopped):
            raise ValueError("incomplete scoped DFD acquisition")
        return dict(completion="cancelled" if cancelled else "complete", records=self.records)
