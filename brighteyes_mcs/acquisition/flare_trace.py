"""Integrate Flare counts into complete intensity trace bins across packets."""

from collections import deque
import math

import numpy as np


def records_per_trace_bin(bin_seconds, record_seconds):
    """Round a requested width up to whole records, allowing float roundoff."""
    ratio = float(bin_seconds) / float(record_seconds)
    return max(1, math.ceil(ratio - 1e-12 * max(1.0, abs(ratio))))


class FlareTrace:
    def __init__(self):
        self.times = deque(maxlen=100000)
        self.rates = deque(maxlen=100000)
        self.elapsed = 0.0
        self.pending_counts = 0.0
        self.pending_seconds = 0.0
        self.pending_records = 0
        self.bin_seconds = None
        self.records_per_bin = None

    def update(self, counts, durations, bin_seconds, history_seconds, *, records_per_bin=None):
        bin_seconds = max(float(bin_seconds), 1e-12)
        if self.bin_seconds != bin_seconds or self.records_per_bin != records_per_bin:
            self.reset()
            self.bin_seconds = bin_seconds
            self.records_per_bin = records_per_bin
        counts = np.asarray(counts, dtype=float)
        durations = np.broadcast_to(durations, counts.shape).astype(float)
        count_sum = np.r_[0.0, np.cumsum(counts)]
        time_sum = np.r_[0.0, np.cumsum(durations)]
        start = 0
        while start < len(counts):
            if records_per_bin is not None:
                # DFD records already contain a full phase histogram. Group a
                # fixed number, independent of packet splits or timing roundoff.
                end = start + records_per_bin - self.pending_records
            else:
                required = bin_seconds - self.pending_seconds
                end = int(np.searchsorted(time_sum, time_sum[start] + required * (1 - 1e-12)))
            if end > len(counts):
                break
            end = max(end, start + 1)
            seconds = self.pending_seconds + time_sum[end] - time_sum[start]
            total = self.pending_counts + count_sum[end] - count_sum[start]
            self.times.append(self.elapsed - self.pending_seconds)
            self.rates.append(total / seconds)
            self.elapsed += time_sum[end] - time_sum[start]
            self.pending_counts = self.pending_seconds = 0.0
            self.pending_records = 0
            start = end
        self.pending_counts += count_sum[-1] - count_sum[start]
        self.pending_seconds += time_sum[-1] - time_sum[start]
        self.pending_records += len(counts) - start
        self.elapsed += time_sum[-1] - time_sum[start]
        while self.times and self.times[0] < self.elapsed - history_seconds:
            self.times.popleft()
            self.rates.popleft()

    def reset(self):
        self.times.clear()
        self.rates.clear()
        self.pending_counts = self.pending_seconds = 0.0
        self.pending_records = 0

    def snapshot(self):
        return dict(trace=np.asarray(self.rates), trace_times=np.asarray(self.times))
