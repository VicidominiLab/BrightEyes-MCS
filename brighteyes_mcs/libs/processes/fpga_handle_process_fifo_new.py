import multiprocessing as mp
from threading import Thread
import nifpga
from ..print_dec import print_dec
from time import perf_counter_ns

import os, psutil

def emptyQueue(queue):
    while not queue.empty():
        _ = queue.get()


class FpgaHandleProcess(mp.Process):
    def __init__(self, configuration, debug=True, use_rust_fifo=True):
        super().__init__()

        print_dec("FpgaHandleProcess INIT")
        # print_dec("=> configuration", configuration)
        # for i in configuration:
        #     print("==", i, "==")
        #     print(configuration[i])
        self.configuration = configuration
        self.timeout_fifos = self.configuration["timeout_fifos"]
        self.bitfile = self.configuration["bitfile"]
        self.ni_address = self.configuration["ni_address"]
        self.requested_depth = self.configuration["requested_depth"]
        self.stop_event = self.configuration["stop_event"]
        self.stop_done_event = self.configuration["stop_done_event"]
        self.print_event = self.configuration["print_event"]
        # self.queueRegisterWrite = self.configuration['queueRegisterWrite']
        # self.queueRegisterReadReq = self.configuration['queueRegisterReadReq']
        # self.queueRegisterRead = self.configuration['queueRegisterRead']
        self.queueFifoWrite = self.configuration["queueFifoWrite"]
        self.queueFifoReadReq = self.configuration["queueFifoReadReq"]
        self.queueFifoRead = self.configuration["queueFifoRead"]
        self.queueFifoReadCircularBuffer = self.configuration["queueFifoReadCircularBuffer"]
        self.is_connected = self.configuration["is_connected"]
        self.is_readytorun = self.configuration["is_readytorun"]
        self.list_registers = self.configuration["list_registers"]
        self.actual_depth = self.configuration["actual_depth"]
        self.fpgarunning = self.configuration["fpgarunning"]
        self.list_fifos_to_read_continously = self.configuration[
            "list_fifos_to_read_continously"
        ]
        self.fifo_chuck_size = self.configuration["fifo_chuck_size"]
        self.expected_raw_data = self.configuration["expected_raw_data"]
        self.initial_registers = self.configuration["initial_registers"]



        print(self.configuration)

        # mp_mng = mp.Manager()

        self.list_fifos = []  # mp_mng.list()
        self.fifo_last_read_time = {}
        self.fifo_element_remaining = {}

        self.nifpga_session = None
        self.use_rust_fifo = use_rust_fifo

        self.fpgarunning_internal = False
        print_dec("FpgaHandleProcess INIT done")

        # self.rust_subprocess = None

    def loop_run_check(self):
        if self.use_rust_fifo == True:
            from ..rust_fifo_reader import RustFastFifoReader

            self.rust_fifo_reader = RustFastFifoReader(
                self.bitfile,
                self.list_fifos,
                self.fifo_chuck_size.value,
                self.requested_depth,
                self.ni_address
            )

        while not self.stop_event.is_set():
            if self.fpgarunning.is_set() and not self.fpgarunning_internal:
                self.nifpga_session.run()
                self.fpgarunning_internal = True
                print_dec("FPGA self.nifpga_session.run()")
                self.fpgarunning.clear()
        print_dec("self.stop_event.is_set()")

        if self.use_rust_fifo == True:
            self.rust_fifo_reader.close()

    def loop_writeReg(self):
        while not self.stop_event.is_set():
            if not self.queueRegisterWrite.empty():
                command = self.queueRegisterWrite.get()

                for current_register in command:
                    try:
                        self.nifpga_session.registers[current_register].write(
                            command[current_register]
                        )
                    except Exception as e:
                        print_dec(
                            "self.queueRegisterWrite",
                            repr(e),
                            " ERROR",
                            current_register,
                            command[current_register],
                        )
                        try:
                            print_dec(
                                "self.queueRegisterWrite SECOND ATTEMPT",
                                current_register,
                                command[current_register],
                            )
                            self.nifpga_session.registers[current_register].write(
                                command[current_register]
                            )
                        except Exception as e:
                            print_dec(
                                "self.queueRegisterWrite 2nd attempt",
                                repr(e),
                                " ERROR",
                                current_register,
                                command[current_register],
                            )
        print_dec("self.stop_event.is_set()")

    def loop_readReq(self):
        while not self.stop_event.is_set():
            if not self.queueRegisterReadReq.empty():
                out_dict = {}
                command = self.queueRegisterReadReq.get()
                for current_register in command:
                    try:
                        out_dict[current_register] = self.nifpga_session.registers[
                            current_register
                        ].read()
                    except Exception as e:
                        print_dec(
                            "self.queueRegisterReadReq", repr(e), "ERROR", command
                        )
                self.queueRegisterRead.put(out_dict)
        print_dec("self.stop_event.is_set()")

    def loop_fifoWrite(self):
        while not self.stop_event.is_set():
            if not self.queueFifoWrite.empty():
                command = self.queueFifoWrite.get()
                print_dec("loop_fifoWrite", command)
                for current_fifo in command:
                    self.nifpga_session.fifos[current_fifo].write(command[current_fifo])
        print_dec("self.stop_event.is_set()")

    def loop_fifoRead(self):
        while not self.stop_event.is_set():
            if not self.queueFifoReadReq.empty():
                out_dict = {}
                command = self.queueFifoReadReq.get()
                print_dec(command)
                for current_fifo in command:
                    chuck = self.fifo_chuck_size.value
                    elements_to_be_read = (
                        self.fifo_element_remaining[current_fifo] // chuck
                    ) * chuck
                    # if elements_to_be_read > 0:
                    try:
                        read_data = self.nifpga_session.fifos[current_fifo].read(
                            elements_to_be_read, self.timeout_fifos
                        )
                        length = len(read_data.data)
                        self.fifo_element_remaining[
                            current_fifo
                        ] = read_data.elements_remaining

                        if length > 0:
                            out_dict[current_fifo] = [read_data.data, length]
                            self.queueFifoRead.put(out_dict)

                    except nifpga.FifoTimeoutError:
                        pass
        print_dec("self.stop_event.is_set()")

    def loop_fifoReadContinously(self):
        while not self.stop_event.is_set():
            temp_list = list(self.list_fifos_to_read_continously)
            if self.fpgarunning_internal and len(temp_list) != 0:
                out_dict = {}
                for current_fifo in temp_list:
                    # with self.semaphore:
                    #     with self.queueFifoRead._rlock:
                    #         read_data = self.nifpga_session.fifos[current_fifo].read(0, 0)
                    #         if read_data.elements_remaining > 0:
                    # print("E ", read_data.elements_remaining)
                    chuck = self.fifo_chuck_size.value
                    elements_to_be_read = (
                        self.fifo_element_remaining[current_fifo] // chuck
                    ) * chuck
                    # if elements_to_be_read > 0:
                    try:
                        read_data = self.nifpga_session.fifos[current_fifo].read(
                            elements_to_be_read, self.timeout_fifos
                        )
                        length = len(read_data.data)
                        self.fifo_element_remaining[
                            current_fifo
                        ] = read_data.elements_remaining

                        if length > 0:
                            out_dict[current_fifo] = [read_data.data, length]
                            self.queueFifoReadCircularBuffer.put(read_data.data)
                            #self.queueFifoRead.put(out_dict)

                    except nifpga.FifoTimeoutError:
                        pass

    def loop_fifoReadContinously_Rust(self):
        while not self.stop_event.is_set():
            temp_list = list(self.list_fifos_to_read_continously)
            if self.fpgarunning_internal and len(temp_list) != 0:
                out_dict = {}
                for current_fifo in temp_list:
                    current_time = perf_counter_ns()
                    delta_time = current_time - self.fifo_last_read_time[current_fifo]
                    if delta_time > self.timeout_fifos:
                        read_data = self.rust_fifo_reader.read_data(current_fifo)
                        self.fifo_last_read_time[current_fifo] = current_time
                        length = len(read_data)
                        # print(delta_time, length)

                        if length > 0:
                            # out_dict[current_fifo] = [read_data, length]
                            print(read_data)
                            self.queueFifoReadCircularBuffer[current_fifo].put(read_data)

        print_dec("self.stop_event.is_set()")

    def run(self):
        # self.thread_check_parent = CheckParentAlive(self, self.stop_event, note="FpgaHandleProcess")

        p = psutil.Process(os.getpid())
        p.nice(psutil.HIGH_PRIORITY_CLASS)
        print_dec("FpgaHandleProcess RUN - PID:", os.getpid(), p.nice())

        print_dec("nifpga.Session(self.bitfile, self.ni_address)")
        # print(self.configuration)
        try:
            self.nifpga_session = nifpga.Session(self.bitfile, self.ni_address)
        except Exception as e:
            print_dec("FPGA Connection failed Error", repr(e))
            self.is_connected.clear()
            raise ("FPGA ERROR")
        print_dec("nifpga.Session(self.bitfile, self.ni_address) DONE!")
        self.is_connected.set()

        self.stop_done_event.clear()

        self.list_fifos[:] = list(self.nifpga_session.fifos.keys())
        self.list_registers[:] = list(self.nifpga_session.registers.keys())

        print_dec("FIFOs: ", self.list_fifos)
        print_dec("Registers: ", self.list_registers)

        # self.nifpga_session = nifpga.Session(self.bitfile, self.ni_address)

        self.nifpga_session.reset()

        for fifo in self.list_fifos:
            if self.use_rust_fifo == False:
                self.actual_depth.value = self.nifpga_session.fifos[fifo].configure(
                    self.requested_depth
                )
                self.nifpga_session.fifos[fifo].configure(self.requested_depth)
                self.nifpga_session.fifos[fifo].start()
            print_dec(
                "FIFO",
                fifo,
                "req:",
                self.requested_depth,
                "actual:",
                self.actual_depth.value,
            )
            self.fifo_element_remaining[fifo] = 0

        # print_dec(self.fifo_element_remaining)
        # here I assume that self.actual_depth is the same for all FIFOs

        print_dec("fpgaManagerProcess.run() started")
        for register in dict(self.initial_registers):
            try:
                if self.initial_registers[register] is not None:
                    self.nifpga_session.registers[register].write(
                        self.initial_registers[register]
                    )
                print_dec("initial_registers: ", register, self.initial_registers[register])
            except Exception as e:
                print_dec(
                    "initial_registers - self.queueRegisterWrite",
                    repr(e),
                    " ERROR",
                    register,
                    "========",
                    self.initial_registers,
                )
        print_dec("initial_registers done")

        # emptyQueue(self.queueRegisterWrite)
        # emptyQueue(self.queueRegisterReadReq)
        # emptyQueue(self.queueRegisterRead)
        emptyQueue(self.queueFifoWrite)
        emptyQueue(self.queueFifoReadReq)
        emptyQueue(self.queueFifoRead)

        self.is_readytorun.set()

        for fifo in self.list_fifos:
            self.fifo_last_read_time[fifo] = perf_counter_ns()  # time

        print_dec("ready to run")

        if self.use_rust_fifo == True:
            threads = [
                (Thread(target=self.loop_run_check), "loop_run_check"),
                (Thread(target=self.loop_fifoWrite), "loop_fifoWrite"),
                (
                    Thread(target=self.loop_fifoReadContinously_Rust),
                    "loop_fifoReadContinously",
                ),
                # (Thread(target=self.loop_fifoReadContinously), "loop_fifoReadContinously"),
                # (Thread(target=self.loop_fifoRead), "loop_fifoRead"),  #OLD NOT USED
                # (Thread(target=self.loop_writeReg), "loop_writeReg"),  #OLD NOT USED
                # (Thread(target=self.loop_readReq), "loop_readReq"),    #OLD NOT USED
            ]
        else:
            threads = [
                (Thread(target=self.loop_run_check), "loop_run_check"),
                (Thread(target=self.loop_fifoWrite), "loop_fifoWrite"),
                (
                    Thread(target=self.loop_fifoReadContinously),
                    "loop_fifoReadContinously",
                ),
                # (Thread(target=self.loop_fifoReadContinously), "loop_fifoReadContinously"),
                # (Thread(target=self.loop_fifoRead), "loop_fifoRead"),  #OLD NOT USED
                # (Thread(target=self.loop_writeReg), "loop_writeReg"),  #OLD NOT USED
                # (Thread(target=self.loop_readReq), "loop_readReq"),    #OLD NOT USED
            ]

        for th, name in threads:
            th.start()
            print_dec(name + ".start()")

        # BLOCK HERE
        self.stop_event.wait(-1)

        print_dec("stop_event.wait DONE")

        for th, name in threads:
            th.join()
            print_dec(name + ".join()")

        print_dec("stop_event.wait DONE")
        if self.use_rust_fifo == True:
            self.rust_fifo_reader.close()

        self.nifpga_session.abort()
        self.nifpga_session.reset()
        self.nifpga_session.close()
        self.stop_done_event.set()
        print_dec("self.nifpga_session.reset()\nself.nifpga_session.close()")
        self.is_connected.clear()
        self.fpgarunning_internal = False
        self.fpgarunning.clear()
        self.stop_event.clear()
        print_dec("fpgaManagerProcess.run() stopped")

    def stop(self):
        self.stop_event.set()

    def terminate(self) -> None:
        self.stop()

        try:
            self.nifpga_session.abort()
            self.nifpga_session.reset()
            self.nifpga_session.close()
        except:
            print_dec("nifpga_session was already terminated.")

        if self.stop_done_event.wait(timeout=1.0):
            print_dec("FpgaHandleProcess STOP nicely")
        else:
            print_dec("FpgaHandleProcess STOP BADLY")
        self.stop_done_event.clear()
        super().terminate()
