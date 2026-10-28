# SPDX-License-Identifier: MIT
"""Immutable DFD1/DFD2 layouts and strict incremental framing for capture clients.

Adapted from brighteyes-flare software/dfd_format.py, revision f47d6c4 (MIT).

No hardware support is implied by this module. Layouts must be negotiated before
opening a receiver; TCP chunks and DMA packets are not record boundaries.
"""
from dataclasses import dataclass
import math
import struct

MAGIC = 0x44464431
TAIL = 0x4446445F454E4421
UINT32_MAX = (1 << 32) - 1
DMA_MAX_BYTES = (1 << 23) - 1


def integer(name, value, low=1, high=UINT32_MAX):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in {low}..{high}')
    return value


@dataclass(frozen=True)
class Layout:
    detector_channels: int
    pixels: int
    lines: int = 1
    frames: int = 1
    repetitions: int = 1
    histogram_bins: int = 91
    format_version: int = 1

    def __post_init__(self):
        if type(self.format_version) is not int or self.format_version not in (1, 2):
            raise ValueError('unsupported DFD format version')
        if type(self.detector_channels) is not int or self.detector_channels not in (25, 49):
            raise ValueError('DFD requires 25 or 49 physical detectors')
        if type(self.histogram_bins) is not int or self.histogram_bins != 91:
            raise ValueError('unsupported DFD bin count')
        for name in ('pixels', 'lines', 'frames', 'repetitions'):
            integer(name, getattr(self, name))
        integer('total_records', self.total_records)

    @classmethod
    def from_metadata(cls, metadata):
        """Parse negotiated effective layout with accepted raster geometry."""
        version = metadata.get('stream_format_version')
        if type(version) is not int or version not in (1, 2) or metadata.get('stream_format') != f'DFD{version}':
            raise ValueError('expected negotiated DFD1 or DFD2 layout')
        layout = cls(**{k: metadata[k] for k in
                        ('detector_channels', 'pixels', 'lines', 'frames', 'repetitions', 'histogram_bins')}, format_version=version)
        expected = dict(record_bytes=layout.record_bytes, stream_channels=layout.stream_channels,
                        reference_channel_index=layout.reference_channel_index, count_bits=16,
                        total_records=layout.total_records, total_bytes=layout.total_bytes)
        for key, value in expected.items():
            if type(metadata.get(key)) is not int or metadata[key] != value:
                raise ValueError(f'inconsistent negotiated {key}')
        if version == 2:
            for key, value in (('extra_channel_count', 1), ('extra_channel_index', layout.extra_channel_index),
                               ('padded_channels', layout.padded_channels)):
                if type(metadata.get(key)) is not int or metadata[key] != value:
                    raise ValueError(f'inconsistent negotiated {key}')
            if metadata.get('extra_channel_physical_io') is not False:
                raise ValueError('extra channel has no physical I/O')
            padding = metadata.get('padding_channel_indices')
            if (not isinstance(padding, list) or any(type(i) is not int for i in padding) or
                padding != list(range(layout.stream_channels, layout.padded_channels))):
                raise ValueError('inconsistent DFD2 padding metadata')
            if metadata.get('channel_roles') != ['detector'] * layout.detector_channels + ['extra', 'laser_reference']:
                raise ValueError('inconsistent DFD2 channel roles')
        return layout

    @property
    def magic(self):
        return 0x44464430 + self.format_version

    @property
    def reference_channel_index(self):
        return self.stream_channels - 1

    @property
    def extra_channel_index(self):
        return self.detector_channels if self.format_version == 2 else None

    @property
    def stream_channels(self):
        return self.detector_channels + self.format_version

    @property
    def padded_channels(self):
        return ((self.stream_channels + 3) // 4) * 4

    @property
    def payload_words(self):
        return self.histogram_bins * self.padded_channels // 4

    @property
    def record_bytes(self):
        return 8 * (6 + self.payload_words)

    @property
    def max_packet_records(self):
        return min(4096, DMA_MAX_BYTES // self.record_bytes)

    @property
    def total_records(self):
        return math.prod((self.pixels, self.lines, self.frames, self.repetitions))

    @property
    def total_bytes(self):
        return self.total_records * self.record_bytes

    def coordinates(self, ordinal):
        x = ordinal % self.pixels
        ordinal //= self.pixels
        y = ordinal % self.lines
        ordinal //= self.lines
        z = ordinal % self.frames
        return x, y, z, ordinal // self.frames


def pixel_cycles(dwell, bins_per_pixel, *, internal=False, sys_hz=100000000):
    integer('sys_hz', sys_hz)
    integer('dwell', dwell, high=UINT32_MAX if internal else 0x7fffffff)
    integer('bins_per_pixel', bins_per_pixel, high=0x7fffffff)
    if internal:
        if bins_per_pixel != 1:
            raise ValueError('internal timing requires bins_per_pixel=1')
        cycles = (dwell * sys_hz + 119999999) // 120000000
    else:
        cycles = dwell * bins_per_pixel
    return integer('effective pixel cycles', cycles, high=0x7fffffff)


def pack_sequence(sequence, slots=6):
    if type(slots) is not int or slots not in (3, 6) or len(sequence) != slots:
        raise ValueError('sequence must match the discovered 3 or 6 slots')
    word = 0
    for mask in sequence:
        word = (word << 4) | integer('laser mask', mask, 0, 15)
    return word


@dataclass(frozen=True)
class Record:
    run_id: int
    pixel_index: int
    coordinates: tuple
    partial: bool
    raw: bytes

    def counts(self, layout):
        """Return owned bin-major U16 counts, excluding padding."""
        import numpy as np
        return np.frombuffer(self.raw, dtype='<u2', offset=40,
                             count=layout.histogram_bins * layout.padded_channels).reshape(
                                 layout.histogram_bins, layout.padded_channels)[:, :layout.stream_channels].copy()


class Decoder:
    """Strict ordered decoder; a framing error permanently invalidates the run.

    feed() yields records so buffering remains bounded to one record even for
    large receives. Fully consume its iterator before calling feed() again.
    """
    def __init__(self, layout, run_id=None):
        self.layout = layout
        self.run_id = None if run_id is None else integer('run_id', run_id, 0)
        self.buffer = bytearray()
        self.records = 0
        self.failed = False
        self.closed = False
        self.partial_seen = False

    def feed(self, chunk):
        if self.failed or self.closed:
            raise ValueError('decoder is failed or closed')
        view = memoryview(chunk)
        offset = 0
        try:
            while offset < len(view):
                target = 40 if len(self.buffer) < 40 else self.layout.record_bytes
                take = min(target - len(self.buffer), len(view) - offset)
                self.buffer.extend(view[offset:offset + take])
                offset += take
                if len(self.buffer) < target:
                    continue
                w0, w1, w2, w3, w4 = struct.unpack_from('<5Q', self.buffer)
                layout = self.layout
                if w0 != (layout.magic << 32 | layout.stream_channels << 16 | layout.histogram_bins):
                    raise ValueError('DFD magic or dimensions disagree with layout')
                if w4 >> 32 != layout.payload_words or w4 & 0xfffffffe:
                    raise ValueError('invalid DFD length or flags')
                if len(self.buffer) == 40:
                    continue
                run, index = w1 >> 32, w1 & UINT32_MAX
                coords = (w2 >> 32, w2 & UINT32_MAX, w3 >> 32, w3 & UINT32_MAX)
                if self.records >= layout.total_records or index != self.records or self.partial_seen:
                    raise ValueError('unexpected DFD pixel ordinal or extra record')
                if self.run_id is not None and run != self.run_id:
                    raise ValueError('DFD run ID changed')
                if coords != layout.coordinates(index):
                    raise ValueError('DFD coordinates disagree with raster')
                if struct.unpack_from('<Q', self.buffer, layout.record_bytes - 8)[0] != TAIL:
                    raise ValueError('invalid DFD tail')
                for phase in range(layout.histogram_bins):
                    start = 40 + 2 * (phase * layout.padded_channels + layout.stream_channels)
                    if any(self.buffer[start:40 + 2 * (phase + 1) * layout.padded_channels]):
                        raise ValueError('nonzero DFD padding')
                raw = bytes(self.buffer)
                self.buffer.clear()
                self.run_id = run
                self.records += 1
                self.partial_seen = bool(w4 & 1)
                yield Record(run, index, coords, self.partial_seen, raw)
        except Exception:
            self.failed = True
            raise

    def finish(self, *, cancelled=False):
        if self.failed or self.closed:
            raise ValueError('decoder is failed or closed')
        self.closed = True
        discarded = len(self.buffer)
        self.buffer.clear()
        if not cancelled and (discarded or self.records != self.layout.total_records or self.partial_seen):
            raise ValueError('incomplete DFD acquisition at EOF')
        return dict(records=self.records, discarded_suffix_bytes=discarded,
                    completion='cancelled' if cancelled else 'complete')
