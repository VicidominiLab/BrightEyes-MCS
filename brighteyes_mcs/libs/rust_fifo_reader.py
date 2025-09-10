import nifpga
import nifpga_fast_fifo_recv
from .print_dec import print_dec


class RustFastFifoReader:
    def __init__(self, bitfile, list_fifo, chunk=2, requested_depth=10000, nifpga_addr="RIO0", delay_us=50):
        self.fast_fifo_recv_inst = {}
        print_dec(list_fifo)

        # Obtaining the signature by using the standard python nifpga library
        self.bitfile_reader = nifpga.Bitfile(bitfile)
        bitfile_signature = self.bitfile_reader.signature

        self.bitfile_fifo_number = {
            i: n for n, i in enumerate(self.bitfile_reader.fifos.keys())
        }

        for fifo in list_fifo:
            if fifo.endswith("In"):
                continue

            dma_buffer_size = (50 * requested_depth // 8) * 8  # (500000//8)*8
            fifo_buffer_size = (requested_depth // 8) * 8  # (10000//8)*8
            fifo_number = self.bitfile_fifo_number[fifo]

            configuration = {
                "bitfile" : bitfile,
                "signature" : bitfile_signature,
                "ni_address" : nifpga_addr,
                "run" : False,
                "close_on_reset" : True,
                "fifo" : fifo_number,
                "dma_buffer_size" : dma_buffer_size,
                "fifo_reading_buffer" : fifo_buffer_size,
                "min_packet" : chunk,
                "delay_us" : delay_us,
                "debug" : False
                }

            print_dec("rust NI FIFO reader", configuration)

            self.fast_fifo_recv_inst[fifo] = nifpga_fast_fifo_recv.NifpgaFastFifoRecv(
                bitfile,
                signature=bitfile_signature,
                ni_address=nifpga_addr,
                run=False,
                close_on_reset=True,
                fifo=fifo_number,
                dma_buffer_size=dma_buffer_size,
                fifo_reading_buffer=fifo_buffer_size,
                min_packet=chunk,
                delay_us=delay_us,
                debug=False
            )
            print("RUST: %s" % fifo, self.fast_fifo_recv_inst[fifo].get_conf())
            self.fast_fifo_recv_inst[fifo].thread_start()
            print_dec("nifpga_fast_fifo_recv.thread_started ", fifo)
        print_dec(self.fast_fifo_recv_inst)

    def read_data(self, fifo="FIFO"):
        read_data = self.fast_fifo_recv_inst[fifo].get_data()
        # print_dec("read_data len:", len(read_data))
        return read_data

    def close(self):
        print_dec("Trying to close", self.fast_fifo_recv_inst.keys())
        for i in self.fast_fifo_recv_inst:
            try:
                print_dec("trying fast_fifo_recv_inst[%s].thread_stop() " % i)
                self.fast_fifo_recv_inst[i].thread_stop()
                print_dec("fast_fifo_recv_inst[%s].thread_stop() done " % i)
            except Exception as e:
                print_dec(
                    "fast_fifo_recv_inst[%s].thread_stop() already closed(?) %s"
                    % (i, e)
                )

    def __del__(self):
        for i in self.fast_fifo_recv_inst:
            try:
                print_dec("trying fast_fifo_recv_inst[%s].thread_stop() " % i)
                self.fast_fifo_recv_inst[i].thread_stop()
                print_dec("fast_fifo_recv_inst[%s].thread_stop() done " % i)
            except Exception as e:
                print_dec(
                    "fast_fifo_recv_inst[%s].thread_stop() already closed(?) %s"
                    % (i, e)
                )
