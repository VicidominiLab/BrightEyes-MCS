from ..libs.print_dec import  print_dec

import numpy as np
from multiprocessing import shared_memory, Lock
import uuid


class MemorySharedNumpyArray:
    """
    A shared memory-backed NumPy array with optional multiprocessing lock.
    Compatible with the original multiprocessing.Array-based design.
    """

    def __init__(self, dtype, shape, sampling=0, name=None, create=True, lock=True):
        """
        Args:
            dtype (str or np.dtype): NumPy dtype (e.g., 'uint8', 'float32')
            shape (tuple): Shape of the array
            sampling: Metadata (e.g., pixel spacing)
            name (str): Name of the shared memory block to attach to (optional)
            create (bool): If True, create a new block. If False, attach to existing.
            lock (bool): Whether to use a multiprocessing lock
        """
        self.np_dtype = np.dtype(dtype)
        self.np_shape = shape
        self.shape = shape
        self.sampling = sampling
        self.id = str(uuid.uuid1())
        self.size = int(np.prod(shape))
        self._nbytes = self.size * self.np_dtype.itemsize

        self.lock = Lock() if lock else None

        if create:
            self.shm = shared_memory.SharedMemory(create=True, size=self._nbytes, name=name)
        else:
            self.shm = shared_memory.SharedMemory(name=name)
        actual_size = len(self.shm.buf)
        if actual_size < self._nbytes:
            raise ValueError(
                f"[SHM] Buffer size too small: got {actual_size} bytes, "
                f"expected {self._nbytes} bytes for dtype={self.np_dtype}, shape={self.np_shape}"
            )

        print_dec("New shared array created: ", self.shm.name, "bytes ", {self._nbytes}, "bytes for dtype={self.np_dtype}, shape={self.np_shape}" )

    def get_numpy_handle(self, reshape=True):
        """
        Return a NumPy array view into shared memory.

        Args:
            reshape (bool): If True, reshape to original shape.

        Returns:
            np.ndarray
        """
        # Slice only the usable part of the shared memory buffer
        flat = np.frombuffer(self.shm.buf[:self._nbytes], dtype=self.np_dtype)
        if reshape:
            try:
                return flat.reshape(self.np_shape)
            except ValueError as e:
                raise ValueError(
                    f"Cannot reshape array of size {flat.size} to shape {self.np_shape}"
                ) from e
        return flat

    def get_lock(self):
        """Return the multiprocessing lock (if enabled)."""
        return self.lock

    def get_name(self):
        """Return the shared memory block name."""
        return self.shm.name

    def close(self):
        """Close the shared memory block (without unlinking)."""
        self.shm.close()

    def unlink(self):
        """Unlink the shared memory block (only once, usually by the creator)."""
        self.shm.unlink()

    def __del__(self):
        try:
            self.shm.close()
        except Exception:
            pass
