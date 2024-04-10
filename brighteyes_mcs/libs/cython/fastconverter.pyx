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

    cdef np.uint64_t values_view_0 = 0
    cdef np.uint64_t values_view_1 = 0

    with nogil, cython.boundscheck(False), cython.wraparound(False), parallel():     # For speeding up
                for i in prange(length):
                    j = i * 2
                    values_view_0 = values_view[j]
                    values_view_1 = values_view[j+1]



                    out_view[i, 0] = ((values_view_0 >> 5) & 0b1111)  # 4 bits
                    out_view[i, 1] = ((values_view_0 >> 9) & 0b1111)  # 4 bits
                    out_view[i, 2] = ((values_view_0 >> 13) & 0b1111)  # 4 bits
                    out_view[i, 3] = ((values_view_0 >> 17) & 0b1111)  # 4 bits
                    out_view[i, 4] = ((values_view_0 >> 21) & 0b1111)  # 4 bits
                    out_view[i, 5] = ((values_view_0 >> 25) & 0b1111)  # 4 bits

                    out_view[i, 17] = ((values_view_0 >> 29) & 0b111111)  # 6 bits
                    out_view[i, 18] = ((values_view_0 >> 35) & 0b11111)  # 5 bits
                    out_view[i, 19] = ((values_view_0 >> 40) & 0b1111)  # 4 bits
                    out_view[i, 20] = ((values_view_0 >> 44) & 0b1111)  # 4 bits
                    out_view[i, 21] = ((values_view_0 >> 48) & 0b1111)  # 4 bits
                    out_view[i, 22] = ((values_view_0 >> 52) & 0b1111)  # 4 bits
                    out_view[i, 23] = ((values_view_0 >> 56) & 0b1111)  # 4 bits
                    out_view[i, 24] = ((values_view_0 >> 60) & 0b1111)  # 4 bits

                    out_view[i, 6] = ((values_view_1 >> 5) & 0b11111)  # 5 bits
                    out_view[i, 7] = ((values_view_1 >> 10) & 0b111111)  # 6 bits
                    out_view[i, 8] = ((values_view_1 >> 16) & 0b11111)  # 5 bits
                    out_view[i, 9] = ((values_view_1 >> 21) & 0b1111)  # 4 bits
                    out_view[i, 10] = ((values_view_1 >> 25) & 0b1111)  # 4 bits
                    out_view[i, 11] = ((values_view_1 >> 29) & 0b111111)  # 6 bits
                    out_view[i, 12] = ((values_view_1 >> 35) & 0b1111111111)  # 10 bits
                    out_view[i, 13] = ((values_view_1 >> 45) & 0b111111)  # 6 bits
                    out_view[i, 14] = ((values_view_1 >> 51) & 0b1111)  # 4 bits
                    out_view[i, 15] = ((values_view_1 >> 55) & 0b1111)  # 4 bits
                    out_view[i, 16] = (values_view_1 >> 59)  # 5 bits

                    #Extra Ch
                    out_view[i, 25] = (values_view_0 & 0b11111)  # 5 bits
                    out_view[i, 26] = (values_view_1 & 0b11111)  # 5 bits

    return 0



cpdef int convertRawDataToCountsDirect49(data, start, stop, buffer_out, buffer_sum, fingerprint_saturation, mask) except? -1:
    #.reshape(self.acquisitionThread.databuffer.shape[0] // 2, 2)

    cdef np.uint64_t[:] values_view = data

    cdef np.uint8_t[:] mask_view = mask

    cdef np.uint64_t[:,:] out_view = buffer_out
    cdef np.uint64_t[:] out_view_sum = buffer_sum
    cdef np.uint64_t[:] out_saturation_view = fingerprint_saturation

    cdef int WORDS = 8
    # cdef int WORDS = 2

    cdef int length = (stop - start) // WORDS

    cdef int i = 0
    cdef int j = 0
    cdef int k = 0
    cdef int m = 0

    cdef np.uint64_t values_view_0 = 0
    cdef np.uint64_t values_view_1 = 0
    cdef np.uint64_t values_view_2 = 0
    cdef np.uint64_t values_view_3 = 0
    cdef np.uint64_t values_view_4 = 0
    cdef np.uint64_t values_view_5 = 0
    cdef np.uint64_t values_view_6 = 0
    cdef np.uint64_t values_view_7 = 0

    cdef int start_c = start
    cdef int stop_c = stop
    out_view_sum[:] = 0
    with nogil, cython.boundscheck(False), cython.wraparound(False), parallel():     # For speeding up
                for i in prange(length):
                    j = i * WORDS + start_c

                    values_view_0 = values_view[j]
                    values_view_1 = values_view[j+1]
                    values_view_2 = values_view[j+2]
                    values_view_3 = values_view[j+3]
                    values_view_4 = values_view[j+4]
                    values_view_5 = values_view[j+5]
                    values_view_6 = values_view[j+6]
                    values_view_7 = values_view[j+7]

                    #word0
                    out_view[i, 16] = ( values_view_0        & 0xFFFF)  # 16 bits
                    out_view[i, 17] = ((values_view_0 >> 16) & 0xFFFF)  # 16 bits
                    out_view[i, 18] = ((values_view_0 >> 32) & 0xFFFF)  # 16 bits
                    out_view[i, 23] = ((values_view_0 >> 48) & 0xFFFF)  # 16 bits

                    # word1
                    out_view[i, 25] = ( values_view_1        & 0xFFFF)  # 16 bits
                    out_view[i, 30] = ((values_view_1 >> 16) & 0xFFFF)  # 16 bits
                    out_view[i, 31] = ((values_view_1 >> 32) & 0xFFFF)  # 16 bits
                    out_view[i, 32] = ((values_view_1 >> 48) & 0xFFFF)  # 16 bits

                    # word2
                    out_view[i, 24] = ( values_view_2        & 0xFFFF)  # 16 bits
                    out_view[i, 2]  = ((values_view_2 >> 16) & 0x00FF)  #  8 bits
                    out_view[i, 3]  = ((values_view_2 >> 24) & 0x00FF)  #  8 bits
                    out_view[i, 4]  = ((values_view_2 >> 32) & 0x00FF)  #  8 bits
                    out_view[i, 8]  = ((values_view_2 >> 40) & 0x00FF)  #  8 bits
                    out_view[i, 9]  = ((values_view_2 >> 48) & 0x00FF)  #  8 bits
                    out_view[i, 11] = ((values_view_2 >> 56) & 0x00FF)  #  8 bits

                    # word3
                    out_view[i, 14] = ( values_view_3        & 0x00FF)  # 8 bits
                    out_view[i, 15] = ((values_view_3 >>  8) & 0x00FF)  # 8 bits
                    out_view[i, 19] = ((values_view_3 >> 16) & 0x00FF)  # 8 bits
                    out_view[i, 20] = ((values_view_3 >> 24) & 0x00FF)  # 8 bits
                    out_view[i, 21] = ((values_view_3 >> 32) & 0x00FF)  # 8 bits
                    out_view[i, 27] = ((values_view_3 >> 40) & 0x00FF)  # 8 bits
                    out_view[i, 28] = ((values_view_3 >> 48) & 0x00FF)  # 8 bits
                    out_view[i, 29] = ((values_view_3 >> 56) & 0x00FF)  # 8 bits

                    # word4
                    out_view[i, 33] = ( values_view_4        & 0x00FF)  # 8 bits
                    out_view[i, 34] = ((values_view_4 >>  8) & 0x00FF)  # 8 bits
                    out_view[i, 36] = ((values_view_4 >> 16) & 0x00FF)  # 8 bits
                    out_view[i, 37] = ((values_view_4 >> 24) & 0x00FF)  # 8 bits
                    out_view[i, 39] = ((values_view_4 >> 32) & 0x00FF)  # 8 bits
                    out_view[i, 40] = ((values_view_4 >> 40) & 0x00FF)  # 8 bits
                    out_view[i, 44] = ((values_view_4 >> 48) & 0x00FF)  # 8 bits
                    out_view[i, 45] = ((values_view_4 >> 56) & 0x00FF)  # 8 bits

                    # word5
                    out_view[i,  0] = ( values_view_5        & 0x007F)  # 7 bits
                    out_view[i,  1] = ((values_view_5 >>  7) & 0x007F)  # 7 bits
                    out_view[i,  5] = ((values_view_5 >> 14) & 0x007F)  # 7 bits
                    out_view[i,  6] = ((values_view_5 >> 21) & 0x007F)  # 7 bits
                    out_view[i,  7] = ((values_view_5 >> 28) & 0x007F)  # 7 bits
                    out_view[i, 13] = ((values_view_5 >> 35) & 0x007F)  # 7 bits
                    out_view[i, 35] = ((values_view_5 >> 42) & 0x007F)  # 7 bits
                    out_view[i, 41] = ((values_view_5 >> 49) & 0x007F)  # 7 bits
                    out_view[i, 46] = ((values_view_5 >> 56) & 0x00FF)  # 8 bits

                    # word6
                    out_view[i, 10] = ( values_view_6        & 0x3FFF)  # 14 bits
                    out_view[i, 22] = ((values_view_6 >> 14) & 0x3FFF)  # 14 bits
                    out_view[i, 42] = ((values_view_6 >> 28) & 0x007F)  #  7 bits
                    out_view[i, 43] = ((values_view_6 >> 35) & 0x007F)  #  7 bits
                    out_view[i, 47] = ((values_view_6 >> 42) & 0x007F)  #  7 bits
                    out_view[i, 48] = ((values_view_6 >> 49) & 0x007F)  #  7 bits
                    out_view[i, 12] = ((values_view_6 >> 56) & 0x00FF)  #  8 bits

                    #word7
                    out_view[i, 26] = ( values_view_7        & 0x3FFF)  # 14 bits
                    out_view[i, 38] = ((values_view_7 >> 14) & 0x3FFF)  # 14 bits
                    out_view[i, 49] = ((values_view_7 >> 28) & 0xFFFF)  # 16 bits
                    out_view[i, 50] = ((values_view_7 >> 44) & 0xFFFF)  # 16 bits
                    #dummy          = ((values_view_7 >> 60) & 0x000F)  # 4 bits

                    #word0
                    if out_view[i, 16] == 0xFFFF  : out_saturation_view[16]  += 1  # 16 bits
                    if out_view[i, 17] == 0xFFFF  : out_saturation_view[17]  += 1  # 16 bits
                    if out_view[i, 18] == 0xFFFF  : out_saturation_view[18]  += 1  # 16 bits
                    if out_view[i, 23] == 0xFFFF  : out_saturation_view[23]  += 1  # 16 bits
                    # word1
                    if out_view[i, 25] == 0xFFFF  : out_saturation_view[25]  += 1  # 16 bits
                    if out_view[i, 30] == 0xFFFF  : out_saturation_view[30]  += 1  # 16 bits
                    if out_view[i, 31] == 0xFFFF  : out_saturation_view[31]  += 1  # 16 bits
                    if out_view[i, 32] == 0xFFFF  : out_saturation_view[32]  += 1  # 16 bits
                    # word2
                    if out_view[i, 24] == 0xFFFF  : out_saturation_view[24]  += 1  # 16 bits
                    if out_view[i, 2]  == 0x00FF  : out_saturation_view[2]   += 1  #  8 bits
                    if out_view[i, 3]  == 0x00FF  : out_saturation_view[3]   += 1  #  8 bits
                    if out_view[i, 4]  == 0x00FF  : out_saturation_view[4]   += 1  #  8 bits
                    if out_view[i, 8]  == 0x00FF  : out_saturation_view[8]   += 1  #  8 bits
                    if out_view[i, 9]  == 0x00FF  : out_saturation_view[9]   += 1  #  8 bits
                    if out_view[i, 11] == 0x00FF  : out_saturation_view[11]  += 1  #  8 bits
                    # word3
                    if out_view[i, 14] == 0x00FF  : out_saturation_view[14]  += 1  # 8 bits
                    if out_view[i, 15] == 0x00FF  : out_saturation_view[15]  += 1  # 8 bits
                    if out_view[i, 19] == 0x00FF  : out_saturation_view[19]  += 1  # 8 bits
                    if out_view[i, 20] == 0x00FF  : out_saturation_view[20]  += 1  # 8 bits
                    if out_view[i, 21] == 0x00FF  : out_saturation_view[21]  += 1  # 8 bits
                    if out_view[i, 27] == 0x00FF  : out_saturation_view[27]  += 1  # 8 bits
                    if out_view[i, 28] == 0x00FF  : out_saturation_view[28]  += 1  # 8 bits
                    if out_view[i, 29] == 0x00FF  : out_saturation_view[29]  += 1  # 8 bits
                    # word4
                    if out_view[i, 33] == 0x00FF  : out_saturation_view[33]  += 1  # 8 bits
                    if out_view[i, 34] == 0x00FF  : out_saturation_view[34]  += 1  # 8 bits
                    if out_view[i, 36] == 0x00FF  : out_saturation_view[36]  += 1  # 8 bits
                    if out_view[i, 37] == 0x00FF  : out_saturation_view[37]  += 1  # 8 bits
                    if out_view[i, 39] == 0x00FF  : out_saturation_view[39]  += 1  # 8 bits
                    if out_view[i, 40] == 0x00FF  : out_saturation_view[40]  += 1  # 8 bits
                    if out_view[i, 44] == 0x00FF  : out_saturation_view[44]  += 1  # 8 bits
                    if out_view[i, 45] == 0x00FF  : out_saturation_view[45]  += 1  # 8 bits
                    # word5
                    if out_view[i,  0] == 0x007F  : out_saturation_view[ 0]  += 1  # 7 bits
                    if out_view[i,  1] == 0x007F  : out_saturation_view[ 1]  += 1  # 7 bits
                    if out_view[i,  5] == 0x007F  : out_saturation_view[ 5]  += 1  # 7 bits
                    if out_view[i,  6] == 0x007F  : out_saturation_view[ 6]  += 1  # 7 bits
                    if out_view[i,  7] == 0x007F  : out_saturation_view[ 7]  += 1  # 7 bits
                    if out_view[i, 13] == 0x007F  : out_saturation_view[13]  += 1  # 7 bits
                    if out_view[i, 35] == 0x007F  : out_saturation_view[35]  += 1  # 7 bits
                    if out_view[i, 41] == 0x007F  : out_saturation_view[41]  += 1  # 7 bits
                    if out_view[i, 46] == 0x00FF  : out_saturation_view[46]  += 1  # 8 bits
                    # word6
                    if out_view[i, 10] == 0x3FFF  : out_saturation_view[10]  += 1  # 14 bits
                    if out_view[i, 22] == 0x3FFF  : out_saturation_view[22]  += 1  # 14 bits
                    if out_view[i, 42] == 0x007F  : out_saturation_view[42]  += 1  #  7 bits
                    if out_view[i, 43] == 0x007F  : out_saturation_view[43]  += 1  #  7 bits
                    if out_view[i, 47] == 0x007F  : out_saturation_view[47]  += 1  #  7 bits
                    if out_view[i, 48] == 0x007F  : out_saturation_view[48]  += 1  #  7 bits
                    if out_view[i, 12] == 0x00FF  : out_saturation_view[12]  += 1  #  8 bits
                    # word7
                    if out_view[i, 26] == 0x3FFF  : out_saturation_view[26]  += 1  # 14 bits
                    if out_view[i, 38] == 0x3FFF  : out_saturation_view[38]  += 1  # 14 bits
                    if out_view[i, 49] == 0xFFFF  : out_saturation_view[49]  += 1  # 16 bits
                    if out_view[i, 50] == 0xFFFF  : out_saturation_view[50]  += 1  # 16 bits
                    # if dummy == 0x000F                                             # 4 bits

                    for k in prange(0,49):
                        if (mask_view[k] != 0):
                            out_view_sum[i] += out_view[i,k]

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

    cdef np.uint64_t values_view_0 = 0
    cdef np.uint64_t values_view_1 = 0

    cdef int start_c = start
    cdef int stop_c = stop
    out_view_sum[:] = 0
    with nogil, cython.boundscheck(False), cython.wraparound(False), parallel():     # For speeding up
                for i in prange(length):
                    j = i * 2 + start_c

                    values_view_0 = values_view[j]
                    values_view_1 = values_view[j+1]

                    out_view[i, 0] = ((values_view_0 >> 5) & 0b1111)  # 4 bits
                    out_view[i, 1] = ((values_view_0 >> 9) & 0b1111)  # 4 bits
                    out_view[i, 2] = ((values_view_0 >> 13) & 0b1111)  # 4 bits
                    out_view[i, 3] = ((values_view_0 >> 17) & 0b1111)  # 4 bits
                    out_view[i, 4] = ((values_view_0 >> 21) & 0b1111)  # 4 bits
                    out_view[i, 5] = ((values_view_0 >> 25) & 0b1111)  # 4 bits

                    out_view[i, 17] = ((values_view_0 >> 29) & 0b111111)  # 6 bits
                    out_view[i, 18] = ((values_view_0 >> 35) & 0b11111)  # 5 bits
                    out_view[i, 19] = ((values_view_0 >> 40) & 0b1111)  # 4 bits
                    out_view[i, 20] = ((values_view_0 >> 44) & 0b1111)  # 4 bits
                    out_view[i, 21] = ((values_view_0 >> 48) & 0b1111)  # 4 bits
                    out_view[i, 22] = ((values_view_0 >> 52) & 0b1111)  # 4 bits
                    out_view[i, 23] = ((values_view_0 >> 56) & 0b1111)  # 4 bits
                    out_view[i, 24] = ((values_view_0 >> 60) & 0b1111)  # 4 bits

                    out_view[i, 6] = ((values_view_1 >> 5) & 0b11111)  # 5 bits
                    out_view[i, 7] = ((values_view_1 >> 10) & 0b111111)  # 6 bits
                    out_view[i, 8] = ((values_view_1 >> 16) & 0b11111)  # 5 bits
                    out_view[i, 9] = ((values_view_1 >> 21) & 0b1111)  # 4 bits
                    out_view[i, 10] = ((values_view_1 >> 25) & 0b1111)  # 4 bits
                    out_view[i, 11] = ((values_view_1 >> 29) & 0b111111)  # 6 bits
                    out_view[i, 12] = ((values_view_1 >> 35) & 0b1111111111)  # 10 bits
                    out_view[i, 13] = ((values_view_1 >> 45) & 0b111111)  # 6 bits
                    out_view[i, 14] = ((values_view_1 >> 51) & 0b1111)  # 4 bits
                    out_view[i, 15] = ((values_view_1 >> 55) & 0b1111)  # 4 bits
                    out_view[i, 16] = (values_view_1 >> 59)  # 5 bits

                    out_view[i, 25] = (values_view_0 & 0b11111)  # 5 bits
                    out_view[i, 26] = (values_view_1 & 0b11111)  # 5 bits

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

    cdef np.uint64_t values_view_0 = 0
    cdef int force_positive_c = force_positive

    with nogil, cython.boundscheck(False), cython.wraparound(False), parallel():     # For speeding up
        for i in prange(length):
            j = i + start_c

            values_view_0 = values_view[j]
            out_view[i, 0] =   values_view_0
            out_view[i, 1] =  (values_view_0 >> 32)
            if force_positive_c != 0 :
                if out_view[i, 0] < 0:
                    out_view[i, 0] = 0
                if out_view[i, 1] < 0:
                    out_view[i, 1] = 0
    return 0