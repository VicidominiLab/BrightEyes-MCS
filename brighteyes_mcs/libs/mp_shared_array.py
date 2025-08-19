from ..libs.print_dec import  print_dec

from functools import reduce
import multiprocessing as mp
import ctypes
import uuid


import numpy as np
from multiprocessing import shared_memory, Lock, Array
import uuid


class MemorySharedNumpyArray_ShmMem:
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

class MemorySharedNumpyArray_CTypes:
    """
    A shared array based on multiprocessing.Array. You can get a Numpy handle
    to the shared array with get_numpy_handle().

    Attributes:
        data (mp.Array): the shared array
        sampling: info about the spacing between elements (e.g., pixel size)
        id (str): a unique identifier for the array instance
        np_shape (tuple): shape of the array
        size (int): size of the flattened array
        np_dtype (str): the Numpy dtype string
    """

    def __init__(self, dtype, shape, sampling=0, lock=True):
        """
        Args:
            dtype (str or np.dtype): Numpy data type (e.g., 'uint32' or np.uint32)
            shape (tuple): shape of the array
            sampling: optional spacing info
            lock (bool): whether to use a process lock
        """
        self.shape = shape
        self.size = reduce(lambda x, y: x * y, shape)
        self.np_dtype = np.dtype(dtype)

        # Get the corresponding ctypes type
        ctype = self._get_typecodes()[self.np_dtype.str]

        # Create multiprocessing.Array with or without lock
        if lock:
            self.lock = mp.Lock()
            self.data = mp.Array(ctype, self.size, lock=self.lock)
        else:
            self.data = mp.Array(ctype, self.size, lock=False)
            self.lock = None  # No lock used

        self.sampling = sampling
        self.id = str(uuid.uuid1())
        self.np_shape = shape

    @staticmethod
    def _get_typecodes():
        """Map Numpy dtypes to ctypes types."""
        ct = ctypes
        simple_types = [
            ct.c_byte, ct.c_short, ct.c_int, ct.c_long, ct.c_longlong,
            ct.c_ubyte, ct.c_ushort, ct.c_uint, ct.c_ulong, ct.c_ulonglong,
            ct.c_float, ct.c_double
        ]
        return {np.dtype(t).str: t for t in simple_types}

    def get_numpy_handle(self, reshape=True):
        """Return a NumPy array view of the shared memory."""
        arr = np.frombuffer(self.data.get_obj(), dtype=self.np_dtype)
        if reshape:
            arr = arr.reshape(self.np_shape)
        return arr

    def get_lock(self):
        """Return the lock if present, else None."""
        return self.lock


MemorySharedNumpyArray = MemorySharedNumpyArray_CTypes
