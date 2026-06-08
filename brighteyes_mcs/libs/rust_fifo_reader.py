import nifpga
import nifpga_fast_fifo_recv
import numpy as np

from .print_debug import print_debug


class RustFastFifoReader:
    def __init__(self, bitfile, list_fifo, chunk_digital=2, chunk_analog=4, requested_fifo_depth=10000, nifpga_addr="RIO0", delay_us=1):
        self.fast_fifo_recv_inst = {}
        print_debug(list_fifo)


        # Obtaining the signature by using the standard python nifpga library
        self.bitfile_reader = nifpga.Bitfile(bitfile)
        bitfile_signature = self.bitfile_reader.signature

        self.bitfile_fifo_number = {
            i: n for n, i in enumerate(self.bitfile_reader.fifos.keys())
        }

        for fifo in list_fifo:
            if fifo.endswith("In"):
                continue

            dma_read_buffer_size = (50 * requested_fifo_depth // 8) * 8
            fifo_read_buffer_size = (requested_fifo_depth // 8) * 8
            fifo_number = self.bitfile_fifo_number[fifo]

            if fifo=="FIFOAnalog":
                delay = delay_us * 20
                chunk = chunk_analog
            else:
                delay = delay_us
                chunk = chunk_digital

            configuration = {
                "bitfile" : bitfile,
                "signature" : bitfile_signature,
                "ni_address" : nifpga_addr,
                "run" : False,
                "close_on_reset" : True,
                "fifo" : fifo_number,
                "dma_read_buffer_size" : dma_read_buffer_size,
                "fifo_read_buffer_size" : fifo_read_buffer_size,
                "min_packet" : chunk,
                "delay_us" : delay,
                "debug" : False
                }

            print_debug("rust NI FIFO reader", fifo,  configuration)

            self.fast_fifo_recv_inst[fifo] = nifpga_fast_fifo_recv.NifpgaFastFifoRecv(
                bitfile,
                signature=bitfile_signature,
                ni_address=nifpga_addr,
                run=False,
                close_on_reset=True,
                fifo=fifo_number,
                dma_buffer_size=dma_read_buffer_size,
                fifo_reading_buffer=fifo_read_buffer_size,
                min_packet=chunk,
                delay_us=delay,
                debug=False
            )

            print_debug("RUST: %s" % fifo, self.fast_fifo_recv_inst[fifo].get_conf())
            self.fast_fifo_recv_inst[fifo].thread_start()
            print_debug("nifpga_fast_fifo_recv.thread_started ", fifo)
        print_debug(self.fast_fifo_recv_inst)

    def read_data(self, fifo="FIFO"):
        try:
            read_data = self.fast_fifo_recv_inst[fifo].get_data_as_numpy()
        except KeyError as e:
            return np.array([],np.uint64)
        # print_debug("read_data", fifo, read_data.shape)
        # read_data = self.fast_fifo_recv_inst[fifo].get_data() #not compatible with nifpga-fast-fifo-recv-0.101.6
        # print_debug("read_data len:", len(read_data))
        return read_data

    def close(self):
        print_debug("Trying to close", self.fast_fifo_recv_inst.keys())
        for i in self.fast_fifo_recv_inst:
            try:
                print_debug("trying fast_fifo_recv_inst[%s].thread_stop() " % i)
                self.fast_fifo_recv_inst[i].thread_stop()
                print_debug("fast_fifo_recv_inst[%s].thread_stop() done " % i)
            except Exception as e:
                print_debug(
                    "fast_fifo_recv_inst[%s].thread_stop() already closed(?) %s"
                    % (i, e)
                )

    def __del__(self):
        for i in self.fast_fifo_recv_inst:
            try:
                print_debug("trying fast_fifo_recv_inst[%s].thread_stop() " % i)
                self.fast_fifo_recv_inst[i].thread_stop()
                print_debug("fast_fifo_recv_inst[%s].thread_stop() done " % i)
            except Exception as e:
                print_debug(
                    "fast_fifo_recv_inst[%s].thread_stop() already closed(?) %s"
                    % (i, e)
                )

