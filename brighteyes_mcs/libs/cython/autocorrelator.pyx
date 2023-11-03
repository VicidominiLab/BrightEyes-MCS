
import cython
import numpy as np
cimport numpy as np
from cython.parallel import parallel, prange


class Autocorrelator:

    def __init__(self, maxx=20, log_step=2.):
        self.param_maxx = maxx
        self.log_step = log_step

        self.maxx = np.zeros(1, dtype=np.int64)
        self.NphotTot = np.zeros(1, dtype=np.int64)
        self.total_c = np.zeros(1, dtype=np.int64)


        self.maxx[0] = maxx
        self.delays = np.round(log_step**np.arange(0,self.maxx[0]))
        self.delays = np.unique(self.delays)
        self.delays = self.delays.astype(np.int64)
        self.maxx[0] = len(self.delays)

        self.intensityBin = np.zeros((self.maxx[0], 2), dtype=np.int64)
        self.partialcorrelation = np.zeros(self.maxx[0], dtype=np.int64)
        self.corrout = np.zeros((self.maxx[0]), dtype=np.double)

        self.NphotTot[0] = 0
        self.total_c[0] = 0

        self.col = np.zeros(self.maxx[0], dtype=np.int64)
        self.binfull = np.zeros(self.maxx[0], dtype=np.int64)

    def add(self, yy):

        cdef np.int64_t len_y = len(yy)
        cdef np.int64_t[:] y = yy.astype(np.int64)
        cdef np.int64_t[:] delays_view = self.delays
        cdef np.int64_t[:,:] intensityBin_view = self.intensityBin
        cdef np.int64_t[:] partialcorrelation_view = self.partialcorrelation
        cdef np.int64_t[:] col_view = self.col
        cdef np.int64_t[:] binfull_view = self.binfull
        cdef np.int64_t maxx = self.maxx[0]
        cdef np.int64_t[:] total_c = self.total_c
        cdef np.int64_t[:] NphotTot = self.NphotTot
        cdef np.int64_t c
        cdef np.int64_t i

        with nogil, parallel(), cython.boundscheck(False), cython.wraparound(False), cython.cdivision(True):
            for c in prange(len_y):
                # check which bin (0 or 1)
                for i in prange(0,maxx):
                    col_view[i] = (((c+total_c[0]) % (2*delays_view[i])) >= delays_view[i])

                    # for b in range(self.maxx):
                    # add photons to bin
                    intensityBin_view[i, col_view[i]] += y[c]
                    # check if bin is full
                    binfull_view[i] = ((c+total_c[0]) % delays_view[i]) == (delays_view[i] - 1)
                    if binfull_view[i]:
                        partialcorrelation_view[i] = partialcorrelation_view[i] + (intensityBin_view[i, 0] * intensityBin_view[i, 1])
                        intensityBin_view[i,1-col_view[i]] = 0
                # calculate total detected photons
                NphotTot[0] = NphotTot[0] + y[c]
            total_c[0] = total_c[0] + len_y

    def get_delays(self):
        return self.delays

    def get_correlation_normalized(self):
        cdef np.double_t[:] mysum = np.sum(self.intensityBin[:,:], axis=1, dtype=np.double)
        cdef np.double_t[:] corrout = self.corrout
        cdef np.int64_t[:] partialcorrelation = self.partialcorrelation
        cdef np.int64_t[:] delays = self.delays
        cdef np.int64_t[:] total_c = self.total_c
        cdef np.int64_t[:] NphotTot = self.NphotTot
        cdef np.int64_t maxx = self.maxx[0]
        cdef np.int64_t b
        with nogil, cython.boundscheck(False), cython.wraparound(False), parallel(), cython.cdivision(True):
            for b in prange(maxx):
                corrout[b] = 0
                if NphotTot[0] > mysum[b]:
                    #self.corrout[b] = self.partialcorrelation[b] / (self.NphotTot[0]- mysum[b])**2 * (np.floor(self.total_c[0] / self.delays[b]) - 1) - 1
                    corrout[b] = partialcorrelation[b] * ((total_c[0] // delays[b]) - 1) / ((NphotTot[0] - mysum[b])*(NphotTot[0] - mysum[b]))  - 1
        return self.corrout

    def reset(self):
        self.__init__(maxx=self.param_maxx, log_step=self.log_step)