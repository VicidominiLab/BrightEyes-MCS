"""Process completed 25-channel dwells into scan images and fingerprints.

Counts are already decoded by Rust. Keep their uint32 precision instead of
packing them into the limited-width SPAD FIFO format. Scan coordinates come
from dwell headers; detector channels remain independent of scan pixels.
"""

from collections import deque

import numpy as np


class MicroimagePreview:
    def __init__(self, width, height, *, snake=False, shared_objects=None):
        if width <= 0 or height <= 0 or width * height > 16_777_216:
            raise ValueError("Invalid PI23 microimage scan dimensions")
        self.width, self.height = int(width), int(height)
        self.snake = snake
        self.shared_objects = shared_objects or {}
        self.frame = None
        self.counts = np.zeros((height, width, 25), dtype=np.uint64)
        self.accumulated = np.zeros_like(self.counts)
        self.seen = np.zeros((height, width), dtype=bool)
        self.fingerprints = np.zeros((6, 5, 5), dtype=np.uint64)
        self.recent = deque(maxlen=10000)
        self.frame_dwells = 0
        self.last_frame_dwells = 0
        self.total_dwells = 0

    def consume(self, snapshot):
        """Consume a completed dwell once, including zero-photon dwells."""
        if snapshot.flags & 3 != 3:
            return False
        if not (0 <= snapshot.x < self.width and 0 <= snapshot.y < self.height):
            return False  # PI23/FPGA trailing synchronization dwells.
        if self.frame is not None and snapshot.frame < self.frame:
            raise ValueError("PI23 microimage frame order reversed")
        if snapshot.frame != self.frame:
            if self.frame is not None:
                self.fingerprints[3] = self.fingerprints[0]
                self.last_frame_dwells = self.frame_dwells
            self.frame = snapshot.frame
            # Keep the last value at each scan pixel until its next dwell arrives.
            # Only per-frame bookkeeping resets at a frame boundary.
            self.seen.fill(False)
            self.fingerprints[0].fill(0)
            self.frame_dwells = 0
        x = self.width - 1 - snapshot.x if self.snake and snapshot.y % 2 else snapshot.x
        if self.seen[snapshot.y, x]:
            return False
        counts = snapshot.counts.astype(np.uint64).reshape(5, 5)
        self.seen[snapshot.y, x] = True
        self.counts[snapshot.y, x] = counts.ravel()
        self.accumulated[snapshot.y, x] += counts.ravel()
        self.fingerprints[0] += counts
        self.fingerprints[1] = counts
        if len(self.recent) == self.recent.maxlen:
            self.fingerprints[2] -= self.recent[0]
        self.recent.append(counts)
        self.fingerprints[2] += counts
        self.fingerprints[4] += (counts == np.iinfo(np.uint32).max)
        self.frame_dwells += 1
        self.total_dwells += 1
        if self.frame_dwells == self.width * self.height:
            self.fingerprints[3] = self.fingerprints[0]
            self.last_frame_dwells = self.frame_dwells
        return True

    def image(self, channel="Sum", *, mask=None, accumulate=False):
        counts = self.accumulated if accumulate else self.counts
        if channel == "Sum":
            if mask is None:
                return counts.sum(axis=2, dtype=np.uint64)
            return counts[:, :, np.asarray(mask).reshape(25) != 0].sum(axis=2, dtype=np.uint64)
        channel = int(channel)
        if not 0 <= channel < 25:
            raise ValueError("Microimages provide detector IDs 0 through 24")
        return counts[:, :, channel].copy()

    def publish(self, channel="Sum", *, mask=None, accumulate=False):
        """Publish through the same shared preview arrays as SPAD/intensity."""
        image = self.image(channel, mask=mask, accumulate=accumulate)
        for name, data in (("shared_image_xy", image), ("shared_fingerprint", self.fingerprints)):
            shared = self.shared_objects.get(name)
            if shared is not None:
                with shared.get_lock():
                    shared.get_numpy_handle()[:] = data
        return image

    def fingerprint_rate(self, mode, dwell_seconds):
        plane, dwells = {
            0: (0, self.frame_dwells),
            1: (2, len(self.recent)),
            2: (3, self.last_frame_dwells),
        }[mode]
        return self.fingerprints[plane] / max(dwells * dwell_seconds, 1e-12)
