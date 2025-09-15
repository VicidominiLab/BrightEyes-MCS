
import numpy as np
from multiprocessing import shared_memory, Lock, Value

class CircularSharedBuffer:
    def __init__(self, size, dtype=np.float64, name=None, create=True, head=None, tail=None, lock=None):
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
        with self.lock:
            return self.available_data

    def qspace(self):
        with self.lock:
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
            #print(n, self.available_data , self.size, self.head, self.tail)

            if n > self.available_space:
                raise BufferError(f"Not enough space in buffer (needed {n}, available {self.available_space})")

            start = self.tail.value
            stop = start + n

            if stop <= self.size:
                # fits without wraparound
                self.buffer[start:stop] = arr
                self.tail.value = stop
            else:
                # wraparound
                first = self.size - start
                self.buffer[start:] = arr[:first]
                self.buffer[:stop % self.size] = arr[first:]
                self.tail.value = stop % self.size

    def get(self, n=-1):
        """Return a copy of all valid elements in insertion order (non-destructive)."""
        ret = None
        # print_dec("CircularShardBuffer - get()")
        with self.lock:
            available_data = self.available_data
            if n > available_data:
                raise BufferError(f"Too large")
                return np.array([], dtype=self.dtype)


            if n == -1:
                n = available_data

            start = self.head.value

            if n == 0:
                ret = np.array([], dtype=self.dtype)
            elif start + n <= self.size:      # no wrap
                ret = self.buffer[start:(start + n) % self.size].copy()
                self.head.value = (start + n) % self.size
            else:                             # wrap
                first = self.size - start
                ret = np.concatenate((
                    self.buffer[start:].copy(),
                    self.buffer[:n - first].copy()
                ))
                self.head.value = n - first

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