
import numpy as np
from multiprocessing import shared_memory, Lock, Value

class CircularSharedBuffer:
    def __init__(self, size, dtype=np.float64, name=None, create=True, head=None, tail=None, count=None, lock=None):
        self.size = size
        self.dtype = np.dtype(dtype)
        self.itemsize = self.dtype.itemsize
        nbytes = size * self.itemsize

        if create:
            self.shm = shared_memory.SharedMemory(create=True, size=nbytes, name=name)
            self.buffer = np.ndarray((size,), dtype=self.dtype, buffer=self.shm.buf)
            self.buffer[:] = 0  # init
            self.head = Value('i', 0)   # index where next put will write
            self.tail = Value('i', 0)   # index where next put will write
            self.lock = Lock() if lock is None else lock
        else:
            if name is None:
                raise ValueError("Must provide name when attaching to existing buffer")
            self.shm = shared_memory.SharedMemory(name=name)
            self.buffer = np.ndarray((size,), dtype=self.dtype, buffer=self.shm.buf)
            self.head = head
            self.tail = tail
            self.lock = lock

    @property
    def available_data(self):
        return (self.tail.value - self.head.value) % self.size


    def qsize(self):
        return self.available_data

    @property
    def available_space(self):
        return self.size - ((self.tail.value - self.head.value) % self.size)

    def put(self, value):
        """Insert either a single scalar or a 1D array of values.
        Raises BufferError if not enough free space is available."""
        arr = np.atleast_1d(value).astype(self.dtype, copy=False)
        n = arr.shape[0]

        with self.lock:

            if n > self.available_space:
                raise BufferError(f"Not enough space in buffer (needed {n}, available {self.available_space})")

            idx = self.tail.value
            end = idx + n

            if end <= self.size:
                # fits without wraparound
                self.buffer[idx:end] = arr
                self.head.value = idx
                self.tail.value = end
            else:
                # wraparound
                first = self.size - idx
                self.buffer[idx:] = arr[:first]
                self.buffer[:end % self.size] = arr[first:]
                self.head.value = idx
                self.tail.value = end % self.size

        # print_dec("CircularShardBuffer - get()")
        #print_dec("available_data",self.available_data, self.size, self.available_data/self.size )
        #
        # print("CircularShardBuffer - put()")
        # print_dec("self.size",  self.size)
        # print_dec("self.head.value", self.head.value)
        # print_dec("self.tail.value", self.tail.value)
        # print_dec("self.available_space()", self.available_space)

    def get(self, n=-1):
        """Return a copy of all valid elements in insertion order (non-destructive)."""
        ret = None
        # print_dec("CircularShardBuffer - get()")
        qsize = self.qsize()
        if n > qsize:
            print("Too large")
            return np.array([], dtype=self.dtype)

        with self.lock:
            if n == -1:
                n = qsize

            start = self.head.value

            if n == 0:
                ret = np.array([], dtype=self.dtype)
            elif start + n <= self.size:
                ret = self.buffer[start:start + n].copy()
                self.head.value = start + n
                self.tail.value = start + n
            else:
                first = self.size - start
                ret = np.concatenate((
                    self.buffer[start:].copy(),
                    self.buffer[:n - first].copy()
                ))
                self.head.value = n - first
                self.tail.value = n - first


        #
        # print_dec("self.size",  self.size)
        # print_dec("n", n)
        # print_dec("self.head.value", self.head.value)
        # print_dec("self.tail.value", self.tail.value)
        # print_dec("self.available_space()", self.available_space)
        return ret

    def empty(self):
        return self.qsize() == 0

    def full(self):
        return self.qsize() == self.size

    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()

    # --- Pickling support ---
    def __getstate__(self):
        # Only store the shared memory name and shared metadata
        state = {
            'size': self.size,
            'dtype': self.dtype.str,
            'name': self.shm.name,
            'head': self.head,
            'tail': self.tail,
            'full': self.full,
            'lock': self.lock,
        }
        return state

    def __setstate__(self, state):
        self.size = state['size']
        self.dtype = np.dtype(state['dtype'])
        self.itemsize = self.dtype.itemsize
        self.shm = shared_memory.SharedMemory(name=state['name'])
        self.buffer = np.ndarray((self.size,), dtype=self.dtype, buffer=self.shm.buf)
        self.head = state['head']
        self.tail = state['tail']
        self.full = state['full']
        self.lock = state['lock']