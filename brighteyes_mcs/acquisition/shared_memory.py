"""Creation and naming of the preview shared-memory arrays."""

from __future__ import annotations

import numpy as np

from .memory.shared_array import MemorySharedNumpyArray


class SharedMemoryRegistry:
    def __init__(self):
        self.arrays = {}

    def allocate_preview(self, *, dim_x, dim_y, dim_z, detector_dim, autocorrelation_maxx, trace_bins, dfd_bins):
        self.arrays = {
            "shared_autocorrelation": MemorySharedNumpyArray(dtype=float, shape=[2, autocorrelation_maxx], lock=True),
            "shared_trace": MemorySharedNumpyArray(dtype=np.int64, shape=[2, trace_bins], lock=True),
            "shared_trace_dfd": MemorySharedNumpyArray(dtype=np.int64, shape=[3, dfd_bins], lock=True),
            "shared_image_xy_rgb": MemorySharedNumpyArray(dtype=np.int64, shape=[dim_y, dim_x, 3], lock=True),
            "shared_image_xy_hcl": MemorySharedNumpyArray(dtype=np.float64, shape=[dim_y, dim_x, 3], lock=True),
            "shared_image_xy": MemorySharedNumpyArray(dtype=np.int64, shape=[dim_y, dim_x], lock=True),
            "shared_image_xz": MemorySharedNumpyArray(dtype=np.int64, shape=[dim_z, dim_x], lock=True),
            "shared_image_zy": MemorySharedNumpyArray(dtype=np.int64, shape=[dim_y, dim_z], lock=True),
            "shared_fingerprint": MemorySharedNumpyArray(dtype=np.uint64, shape=[6, detector_dim, detector_dim], sampling=0, lock=True),
            "shared_fingerprint_mask": MemorySharedNumpyArray(dtype=np.uint8, shape=[detector_dim * detector_dim], sampling=0, lock=True),
        }
        self.arrays["shared_fingerprint_mask"].get_numpy_handle()[:] = np.ones(
            detector_dim * detector_dim, dtype=np.uint8
        )
        return dict(self.arrays)

    def disabled_preview(self):
        self.arrays = {name: None for name in (
            "shared_autocorrelation", "shared_trace", "shared_trace_dfd",
            "shared_image_xy_rgb", "shared_image_xy_hcl", "shared_image_xy",
            "shared_image_xz", "shared_image_zy", "shared_fingerprint",
            "shared_fingerprint_mask",
        )}
        return dict(self.arrays)
