"""Read-only access to preview arrays with correct locking and copy semantics."""

from __future__ import annotations

import numpy as np


class PreviewRepository:
    def __init__(self):
        self.arrays = {}

    def bind(self, arrays) -> None:
        self.arrays = dict(arrays)

    def _copy(self, name):
        shared = self.arrays.get(name)
        if shared is None:
            raise RuntimeError("Preview data is unavailable in RAW stream mode")
        lock = shared.get_lock()
        if lock is None:
            return np.copy(shared.get_numpy_handle())
        with lock:
            return np.copy(shared.get_numpy_handle())

    def get_preview_image(self, projection="xy", rgb=False):
        name = {
            "xy": "shared_image_xy", "yx": "shared_image_xy",
            "xz": "shared_image_xz", "zx": "shared_image_xz",
            "zy": "shared_image_zy", "yz": "shared_image_zy",
        }.get(projection)
        if name is None:
            raise ValueError("Unsupported preview projection: %s" % projection)
        if rgb:
            name = "shared_image_xy_rgb"
        return self._copy(name)

    def get_hcl_image(self):
        return self._copy("shared_image_xy_hcl")

    def get_fingerprint(self, plane=1):
        return self._copy("shared_fingerprint")[plane, :, :]
