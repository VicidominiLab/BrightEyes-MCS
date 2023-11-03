import cython
import numpy as np
cimport numpy as np
from cython.parallel import parallel, prange

cdef class timeBinner:
    cdef public np.uint64_t bins
    cdef public np.uint64_t sample_per_bins
    cdef public np.uint64_t current_position_bins
    cdef public np.uint64_t current_counter
    cdef public np.int64_t [:] counts
    cdef public np.uint64_t [:] x

    def __init__(self, bins, sample_per_bins):
        self.bins = np.uint64(bins)
        self.sample_per_bins = np.uint64(sample_per_bins)
        self.counts = np.zeros(bins, dtype=np.int64)
        self.x = np.arange(bins, dtype=np.uint64)
        self.current_position_bins = np.uint64(0)
        self.current_counter = np.uint64(0)
    def add(self,  arr_in):
        cdef np.uint64_t l, i, pos, pos_next

        cdef np.uint64_t [:] arr_input = arr_in.astype(np.uint64)
        cdef np.int64_t [:] counts_view = self.counts
        l=len(arr_input)

        with nogil, cython.boundscheck(False), cython.wraparound(False), parallel(), cython.cdivision(True):
            for i in prange(0,l):
                pos = (i+self.current_counter)//self.sample_per_bins % self.bins
                self.current_position_bins = pos
                counts_view[pos] = counts_view[pos] + arr_input[i]
                pos_next=(pos+1)% self.bins
                counts_view[pos_next] = 0
            self.current_counter=self.current_counter+l
    def get_bins(self):
        return np.asarray(self.counts)
    def get_current_position_bins(self):
        return self.current_position_bins
    def get_x(self):
        return np.asarray(self.x)
    def reset(self):
        print("RESET")
        self.__init__(self.bins, self.sample_per_bins)