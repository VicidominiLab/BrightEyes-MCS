import multiprocessing as mp
import numpy as np
from ..print_dec import print_dec, set_debug

# from ..is_parent_alive import CheckParentAlive
import os
import time


class DataPreProcess(mp.Process):
    def __init__(
        self,
        queue_in,
        dict_of_shared_loc,
        last_preprocessed_len,
        dict_of_queue_array_out,
        dict_of_dtype_queue_array_out,
        len_buffer=0,
        debug=False,
        use_rust_fifo=True,
    ):
        super().__init__()

        """
        :param queue_in: this is the queue from the fpgahandleprocess each elements contains ["FIFONAME", data]
        :param dict_of_shared_loc: {'FIFONAME':shared_loc_fifo,...}
        :param dict_of_queue_array_out: {'FIFONAME':shared_queue_array_out,...}
        :param dict_of_dtype_queue_array_out: {'FIFONAME':dtype_shared_queue_array_out,...}
        """
        # def __init__(self, queue_in, buffer, loc, dict_of_queue_array_out):
        set_debug(debug)
        print_dec("DataPreProcess INIT")
        self.queue_in = queue_in
        self.dict_of_shared_loc = dict_of_shared_loc
        self.last_preprocessed_len = last_preprocessed_len
        # self.shm_data = buffer

        self.index = 0
        # print("I",id(self.databuffer))
        self.stop_event = mp.Event()
        self.stop_event.clear()

        self.stop_event_done = mp.Event()
        self.stop_event_done.clear()

        self.dict_of_queue_array_out = dict_of_queue_array_out
        self.dict_of_dtype_queue_array_out = dict_of_dtype_queue_array_out

        self.len_buffer = len_buffer
        self.timeout = 0.2

        self.use_rust_fifo = False  # use_rust_fifo

    def run(self):
        print_dec("DataPreProcess RUN - PID:", os.getpid(), self.use_rust_fifo)

        len_buffer = self.len_buffer
        timeout = self.timeout

        pre_buffer_list = {}
        pre_buffer_len = {}

        delta_time = {}
        time_stop = {}
        time_start = {}

        counter_total_len = {}

        # fifo_lists = []
        if self.use_rust_fifo == False:
            while not self.stop_event.is_set():
                # databuffer = self.shm_data.get_numpy_handle()
                if not self.queue_in.empty():
                    dict_from_queue = self.queue_in.get()
                    # print_dec(dict_from_queue.keys())
                    #fifo_name = list(dict_from_queue.keys())[0]
                    for fifo_name in dict_from_queue.keys():
                        data, len_values = dict_from_queue[fifo_name]
                        if not (fifo_name in pre_buffer_list):
                            pre_buffer_list[fifo_name] = []
                            pre_buffer_len[fifo_name] = 0
                            counter_total_len[fifo_name] = 0
                            time_start[fifo_name] = time.time()
                            # fifo_lists.append(fifo_name)
                        #pre_buffer_list[fifo_name] += data #not compatible with nifpga-fast-fifo-recv-0.101.6
                        pre_buffer_list[fifo_name] += data.tolist()
                        pre_buffer_len[fifo_name] += len_values
                        counter_total_len[fifo_name] += len_values

                # print_dec("fifo_lists", fifo_lists)
                # print_dec("pre_buffer_list", pre_buffer_list.keys())
                for fifo_name in pre_buffer_list.keys():
                    time_stop[fifo_name] = time.time()
                    delta_time[fifo_name] = time_stop[fifo_name] - time_start[fifo_name]
                    # print(delta_time[fifo_name])
                    if (
                        pre_buffer_len[fifo_name] > len_buffer
                        or delta_time[fifo_name] > timeout
                    ) and (pre_buffer_len[fifo_name] > 0):
                        time_start[fifo_name] = time.time()
                        data_as_array = np.fromiter(
                            pre_buffer_list[fifo_name],
                            dtype=np.uint64,
                            count=pre_buffer_len[fifo_name],
                        ).astype(self.dict_of_dtype_queue_array_out[fifo_name])

                        self.dict_of_queue_array_out[fifo_name].put(data_as_array)
                        self.dict_of_shared_loc[fifo_name].value = (
                            self.dict_of_shared_loc[fifo_name].value
                            + pre_buffer_len[fifo_name]
                        )
                        self.last_preprocessed_len[fifo_name].value = pre_buffer_len[fifo_name]
                        # print("-> ", self.dict_of_shared_loc[fifo_name].value)
                        pre_buffer_list[fifo_name] = []
                        pre_buffer_len[fifo_name] = 0

        print_dec("counter_total_len ", counter_total_len)
        self.stop_event.clear()
        self.stop_event_done.set()
        print_dec("DataPreProcess self.stop_event.clear() PID: ", os.getpid())
        return

    def stop(self):
        # databuffer = self.shm_data.get_numpy_handle()
        print_dec("DataPreProcess STOP")
        self.stop_event.set()
        print_dec("waiting for self.stop_event_done")
        self.stop_event_done.wait(5000)
        print_dec("waiting for self.stop_event_done DONE")
        self.terminate()

    def terminate(self) -> None:
        print_dec("DataPreProcess.terminate()")
        time.sleep(0.1)
        super().terminate()
