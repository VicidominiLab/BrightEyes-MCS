import numpy as np
from functools import reduce
import multiprocessing as mp
import ctypes
import uuid


class MemorySharedNumpyArray(object):
    """
    A shared array (based on multiprocessing Array). Also, you can get a Numpy handle
    to the shared array with the get_numpy_handle() method. If you need the locking etc.
    capabilities of the mp.Array, you can access the data attribute directly.

    Attributes:
        data (mp.Array): the shared array
        sampling: information about the physical spacing between elements
        (e.g. pixel size). The information will be the same for all array
        views. Make sure that when slicing, the dimensionality is appropriate.
        id (str): a unique identifier (tag) for an array instance. Makes dealing with
        array views a little bit more straightforward
        np_shape (tuple): the shape of the array
        size (int): the size of the flattened array
        np.dtype (str): the Numpy dtype string
    """

    def __init__(self, dtype, shape, sampling, lock=True):
        """
        Args:
            dtype (str): a Numpy data type string ('uint32' etc.). You can also use the
            constants defined in Numpy (np.uint32 etc.)
            shape (tuple): the shape of the array (e.g. (20, 50, 200))
            sampling:  sampling info, e.g. tuple of pixel spacings in an image

        Keyword Args:
            lock: Apply a process lock.
        """

        self.shape = shape
        size = reduce(lambda x, y: x * y, shape)
        ctype = self._get_typecodes()[np.dtype(dtype).str]

        if lock:
            self.lock = mp.Lock()
            self.data = mp.Array(ctype, size, lock=self.lock)
        else:
            print("not lock")
            self.data = mp.Array(ctype, size, lock=False)
            self.lock = mp.data.get_lock()
        # add the new attribute to the created instance
        self.sampling = sampling
        self.id = str(uuid.uuid1())
        self.np_dtype = dtype
        self.size = size
        self.np_shape = shape

    @staticmethod
    def _get_typecodes():
        """Get a ctypes type from a Numpy dtype. This function is included in
        the ctypeslib from Numpy >1.16, but we are using an older version here.a
        """
        ct = ctypes
        simple_types = [
            ct.c_byte,
            ct.c_short,
            ct.c_int,
            ct.c_long,
            ct.c_longlong,
            ct.c_ubyte,
            ct.c_ushort,
            ct.c_uint,
            ct.c_ulong,
            ct.c_ulonglong,
            ct.c_float,
            ct.c_double,
        ]

        return {np.dtype(ctype).str: ctype for ctype in simple_types}

    def get_numpy_handle(self, reshape=True):
        """Return a Numpy array handle to the shared array.

        Returns:
            np.ndarray -- the array reshaped to the original shape definition
        """
        if reshape:
            return np.frombuffer(self.data.get_obj(), dtype=self.np_dtype).reshape(
                self.np_shape
            )
        else:
            return np.frombuffer(self.data.get_obj(), dtype=self.np_dtype)
            # return np.ndarray(shape=shape, dtype=self.np_dtype, buffer=self.data.get_obj())

    def get_lock(self):
        return self.lock
