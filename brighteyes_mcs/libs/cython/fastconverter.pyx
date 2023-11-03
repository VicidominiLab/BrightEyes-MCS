import cython
import numpy as np
cimport numpy as np
from cython.parallel import parallel, prange
from libcpp cimport bool


cpdef int convertRawDataToCounts(values, out) except? -1:
    #.reshape(self.acquisitionThread.databuffer.shape[0] // 2, 2)

    cdef np.uint64_t[:] values_view = values

    cdef np.uint64_t[:,:] out_view = out
    cdef int length = values.shape[0] // 2

    cdef int i = 0
    cdef int j = 0
    cdef int k = 0

    cdef np.uint64_t values_view_A = 0
    cdef np.uint64_t values_view_B = 0

    with nogil, cython.boundscheck(False), cython.wraparound(False), parallel():     # For speeding up
                for i in prange(length):
                    j = i * 2
                    values_view_A = values_view[j]
                    values_view_B = values_view[j+1]



                    out_view[i, 0] = ((values_view_A >> 5) & 0b1111)  # 4 bits
                    out_view[i, 1] = ((values_view_A >> 9) & 0b1111)  # 4 bits
                    out_view[i, 2] = ((values_view_A >> 13) & 0b1111)  # 4 bits
                    out_view[i, 3] = ((values_view_A >> 17) & 0b1111)  # 4 bits
                    out_view[i, 4] = ((values_view_A >> 21) & 0b1111)  # 4 bits
                    out_view[i, 5] = ((values_view_A >> 25) & 0b1111)  # 4 bits

                    out_view[i, 17] = ((values_view_A >> 29) & 0b111111)  # 6 bits
                    out_view[i, 18] = ((values_view_A >> 35) & 0b11111)  # 5 bits
                    out_view[i, 19] = ((values_view_A >> 40) & 0b1111)  # 4 bits
                    out_view[i, 20] = ((values_view_A >> 44) & 0b1111)  # 4 bits
                    out_view[i, 21] = ((values_view_A >> 48) & 0b1111)  # 4 bits
                    out_view[i, 22] = ((values_view_A >> 52) & 0b1111)  # 4 bits
                    out_view[i, 23] = ((values_view_A >> 56) & 0b1111)  # 4 bits
                    out_view[i, 24] = ((values_view_A >> 60) & 0b1111)  # 4 bits

                    out_view[i, 6] = ((values_view_B >> 5) & 0b11111)  # 5 bits
                    out_view[i, 7] = ((values_view_B >> 10) & 0b111111)  # 6 bits
                    out_view[i, 8] = ((values_view_B >> 16) & 0b11111)  # 5 bits
                    out_view[i, 9] = ((values_view_B >> 21) & 0b1111)  # 4 bits
                    out_view[i, 10] = ((values_view_B >> 25) & 0b1111)  # 4 bits
                    out_view[i, 11] = ((values_view_B >> 29) & 0b111111)  # 6 bits
                    out_view[i, 12] = ((values_view_B >> 35) & 0b1111111111)  # 10 bits
                    out_view[i, 13] = ((values_view_B >> 45) & 0b111111)  # 6 bits
                    out_view[i, 14] = ((values_view_B >> 51) & 0b1111)  # 4 bits
                    out_view[i, 15] = ((values_view_B >> 55) & 0b1111)  # 4 bits
                    out_view[i, 16] = (values_view_B >> 59)  # 5 bits

                    #Extra Ch
                    out_view[i, 25] = (values_view_A & 0b11111)  # 5 bits
                    out_view[i, 26] = (values_view_B & 0b11111)  # 5 bits

    return 0

cpdef int convertRawDataToCountsDirect(data, start, stop, buffer_out, buffer_sum, fingerprint_saturation, mask) except? -1:
    #.reshape(self.acquisitionThread.databuffer.shape[0] // 2, 2)

    cdef np.uint64_t[:] values_view = data

    cdef np.uint8_t[:] mask_view = mask

    cdef np.uint64_t[:,:] out_view = buffer_out
    cdef np.uint64_t[:] out_view_sum = buffer_sum
    cdef np.uint64_t[:] out_saturation_view = fingerprint_saturation

    cdef int length = (stop - start) // 2

    cdef int i = 0
    cdef int j = 0
    cdef int k = 0
    cdef int m = 0

    cdef np.uint64_t values_view_A = 0
    cdef np.uint64_t values_view_B = 0

    cdef int start_c = start
    cdef int stop_c = stop
    out_view_sum[:] = 0
    with nogil, cython.boundscheck(False), cython.wraparound(False), parallel():     # For speeding up
                for i in prange(length):
                    j = i * 2 + start_c

                    values_view_A = values_view[j]
                    values_view_B = values_view[j+1]

                    out_view[i, 0] = ((values_view_A >> 5) & 0b1111)  # 4 bits
                    out_view[i, 1] = ((values_view_A >> 9) & 0b1111)  # 4 bits
                    out_view[i, 2] = ((values_view_A >> 13) & 0b1111)  # 4 bits
                    out_view[i, 3] = ((values_view_A >> 17) & 0b1111)  # 4 bits
                    out_view[i, 4] = ((values_view_A >> 21) & 0b1111)  # 4 bits
                    out_view[i, 5] = ((values_view_A >> 25) & 0b1111)  # 4 bits

                    out_view[i, 17] = ((values_view_A >> 29) & 0b111111)  # 6 bits
                    out_view[i, 18] = ((values_view_A >> 35) & 0b11111)  # 5 bits
                    out_view[i, 19] = ((values_view_A >> 40) & 0b1111)  # 4 bits
                    out_view[i, 20] = ((values_view_A >> 44) & 0b1111)  # 4 bits
                    out_view[i, 21] = ((values_view_A >> 48) & 0b1111)  # 4 bits
                    out_view[i, 22] = ((values_view_A >> 52) & 0b1111)  # 4 bits
                    out_view[i, 23] = ((values_view_A >> 56) & 0b1111)  # 4 bits
                    out_view[i, 24] = ((values_view_A >> 60) & 0b1111)  # 4 bits

                    out_view[i, 6] = ((values_view_B >> 5) & 0b11111)  # 5 bits
                    out_view[i, 7] = ((values_view_B >> 10) & 0b111111)  # 6 bits
                    out_view[i, 8] = ((values_view_B >> 16) & 0b11111)  # 5 bits
                    out_view[i, 9] = ((values_view_B >> 21) & 0b1111)  # 4 bits
                    out_view[i, 10] = ((values_view_B >> 25) & 0b1111)  # 4 bits
                    out_view[i, 11] = ((values_view_B >> 29) & 0b111111)  # 6 bits
                    out_view[i, 12] = ((values_view_B >> 35) & 0b1111111111)  # 10 bits
                    out_view[i, 13] = ((values_view_B >> 45) & 0b111111)  # 6 bits
                    out_view[i, 14] = ((values_view_B >> 51) & 0b1111)  # 4 bits
                    out_view[i, 15] = ((values_view_B >> 55) & 0b1111)  # 4 bits
                    out_view[i, 16] = (values_view_B >> 59)  # 5 bits

                    out_view[i, 25] = (values_view_A & 0b11111)  # 5 bits
                    out_view[i, 26] = (values_view_B & 0b11111)  # 5 bits

                    if out_view[i, 0]  ==  0b1111     :  out_saturation_view[0]  += 1              # 4 bits
                    if out_view[i, 1]  ==  0b1111     :  out_saturation_view[1]  += 1              # 4 bits
                    if out_view[i, 2]  ==  0b1111     :  out_saturation_view[2]  += 1              # 4 bits
                    if out_view[i, 3]  ==  0b1111     :  out_saturation_view[3]  += 1              # 4 bits
                    if out_view[i, 4]  ==  0b1111     :  out_saturation_view[4]  += 1              # 4 bits
                    if out_view[i, 5]  ==  0b1111     :  out_saturation_view[5]  += 1              # 4 bits

                    if out_view[i, 17] == 0b111111    :  out_saturation_view[17] += 1              # 6 bits
                    if out_view[i, 18] == 0b11111     :  out_saturation_view[18] += 1              # 5 bits
                    if out_view[i, 19] == 0b1111      :  out_saturation_view[19] += 1              # 4 bits
                    if out_view[i, 20] == 0b1111      :  out_saturation_view[20] += 1              # 4 bits
                    if out_view[i, 21] == 0b1111      :  out_saturation_view[21] += 1              # 4 bits
                    if out_view[i, 22] == 0b1111      :  out_saturation_view[22] += 1              # 4 bits
                    if out_view[i, 23] == 0b1111      :  out_saturation_view[23] += 1              # 4 bits
                    if out_view[i, 24] == 0b1111      :  out_saturation_view[24] += 1              # 4 bits

                    if out_view[i, 6]  == 0b11111     :  out_saturation_view[6]  += 1               # 5 bits
                    if out_view[i, 7]  == 0b111111    :  out_saturation_view[7]  += 1               # 6 bits
                    if out_view[i, 8]  == 0b11111     :  out_saturation_view[8]  += 1               # 5 bits
                    if out_view[i, 9]  == 0b1111      :  out_saturation_view[9]  += 1               # 4 bits
                    if out_view[i, 10] == 0b1111      :  out_saturation_view[10] += 1               # 4 bits
                    if out_view[i, 11] == 0b111111    :  out_saturation_view[11] += 1               # 6 bits
                    if out_view[i, 12] == 0b1111111111:  out_saturation_view[12] += 1               # 10 bits
                    if out_view[i, 13] == 0b111111    :  out_saturation_view[13] += 1               # 6 bits
                    if out_view[i, 14] == 0b1111      :  out_saturation_view[14] += 1               # 4 bits
                    if out_view[i, 15] == 0b1111      :  out_saturation_view[15] += 1               # 4 bits
                    if out_view[i, 16] == 0b11111     :  out_saturation_view[16] += 1               # 5 bits

                    #extra channel
                    if out_view[i, 25] == 0b11111     :  out_saturation_view[25] += 1               # 5 bits
                    if out_view[i, 26] == 0b11111     :  out_saturation_view[26] += 1               # 5 bits

                    for k in prange(0,25):
                        if (mask_view[k] != 0):
                            out_view_sum[i] += out_view[i,k]

    return 0

cpdef int convertDataFromAnalogFIFO(data, start, stop, buffer_out, force_positive = 0) except? -1:
    #.reshape(self.acquisitionThread.databuffer.shape[0] // 2, 2)

    cdef np.uint64_t[:] values_view = data
    cdef np.int32_t[:,:] out_view = buffer_out

    cdef int start_c = start
    cdef int stop_c = stop
    cdef int length = (stop_c - start_c)

    cdef int i = 0
    cdef int j = 0

    cdef np.uint64_t values_view_A = 0
    cdef int force_positive_c = force_positive

    with nogil, cython.boundscheck(False), cython.wraparound(False), parallel():     # For speeding up
        for i in prange(length):
            j = i + start_c

            values_view_A = values_view[j]
            out_view[i, 0] =   values_view_A
            out_view[i, 1] =  (values_view_A >> 32)
            if force_positive_c != 0 :
                if out_view[i, 0] < 0:
                    out_view[i, 0] = 0
                if out_view[i, 1] < 0:
                    out_view[i, 1] = 0
    return 0