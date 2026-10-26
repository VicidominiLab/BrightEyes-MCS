"""Incremental FLR4 decoder preserving all U32 counts."""

import numpy as np

from .config import bin_bytes, total_bins


class FlareDecoder:
    def __init__(self, configuration, run_id):
        self.configuration = dict(configuration)
        self.channels = configuration["channels"]
        self.bin_bytes = bin_bytes(self.channels)
        self.run_id = int(run_id) & 255
        self.expected_bins = total_bins(configuration)
        self.index = 0
        self.pending = bytearray()

    def feed(self, chunk):
        self.pending.extend(chunk)
        count = len(self.pending) // self.bin_bytes
        if not count:
            return np.empty((0, self.channels), dtype=np.uint32)
        if self.index + count > self.expected_bins:
            raise ValueError("Extra Flare bins after expected acquisition length")
        size = count * self.bin_bytes
        records = np.frombuffer(bytes(self.pending[:size]), dtype=np.uint8).reshape(
            count, self.bin_bytes
        )
        header = records[:, :8]
        n = np.arange(self.index, self.index + count, dtype=np.uint64)
        expected = {0: self.channels, 6: self.run_id, 7: 0xA2}
        for byte, field in (
            (1, "bins_per_pixel"),
            (5, "pixels"),
            (4, "lines"),
            (3, "frames"),
            (2, "repetitions"),
        ):
            expected[byte] = (n % self.configuration[field]) & 255
            n = n // self.configuration[field]
        if any(not np.all(header[:, byte] == value) for byte, value in expected.items()):
            raise ValueError(f"Flare header, run ID or order mismatch at bin {self.index}")
        padding = records[:, 8 + 4 * self.channels : self.bin_bytes - 8]
        tail = records[:, -8:].copy().view("<u8").reshape(-1)
        if np.any(padding) or np.any(tail != 0x465047415F454E44):
            raise ValueError(f"Flare padding or tail mismatch at bin {self.index}")
        counts = (
            records[:, 8 : 8 + 4 * self.channels].copy().view("<u4").reshape(count, self.channels)
        )
        del self.pending[:size]
        self.index += count
        return counts

    def finish(self):
        if self.pending or self.index != self.expected_bins:
            raise ValueError(
                f"Incomplete Flare capture: {self.index}/{self.expected_bins} bins, {len(self.pending)} trailing bytes"
            )
