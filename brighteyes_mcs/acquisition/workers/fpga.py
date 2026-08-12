import multiprocessing as mp
from threading import Thread
import nifpga
from brighteyes_mcs.logging_setup import logger
from time import perf_counter_ns, sleep
from ..detectors.models import (
    DETECTOR_SPAD_ARRAY,
    detector_uses_nifpga_fifo,
    normalize_detector_model,
)

import os, psutil


REQUIRED_FPGA_CONTROL_REGISTERS = frozenset(
    ("stop_command", "start_command", "debug_scan_fsm_status")
)


def validate_fpga_interface(available_registers, available_fifos, required_fifos):
    """Reject a bitfile that does not expose the interface used by the app."""
    missing_registers = sorted(
        REQUIRED_FPGA_CONTROL_REGISTERS.difference(available_registers)
    )
    missing_fifos = sorted(set(required_fifos).difference(available_fifos))
    if not missing_registers and not missing_fifos:
        return

    details = []
    if missing_registers:
        details.append("missing registers: " + ", ".join(missing_registers))
    if missing_fifos:
        details.append("missing DMA FIFOs: " + ", ".join(missing_fifos))
    raise RuntimeError(
        "The selected FPGA firmware is incompatible with BrightEyes-MCS ("
        + "; ".join(details)
        + ")."
    )

def emptyQueue(queue):
    while not queue.empty():
        _ = queue.get()


class FpgaHandleProcess(mp.Process):
    def __init__(self, configuration, debug=True, use_rust_fifo=True):
        super().__init__()

        logger.debug("NI FPGA control/FIFO process INIT")
        # debug("=> configuration", configuration)
        # for i in configuration:
        #     print("==", i, "==")
        #     print(configuration[i])
        self.configuration = configuration
        self.timeout_fifos = self.configuration["timeout_fifos"]
        self.bitfile = self.configuration["bitfile"]
        self.ni_address = self.configuration["ni_address"]
        self.requested_fifo_depth = self.configuration["requested_fifo_depth"]
        self.stop_event = self.configuration["stop_event"]
        self.stop_done_event = self.configuration["stop_done_event"]
        self.print_event = self.configuration["print_event"]
        # self.queueRegisterWrite = self.configuration['queueRegisterWrite']
        # self.queueRegisterReadReq = self.configuration['queueRegisterReadReq']
        # self.queueRegisterRead = self.configuration['queueRegisterRead']
        self.queueFifoWrite = self.configuration["queueFifoWrite"]
        self.queueFifoReadReq = self.configuration["queueFifoReadReq"]
        self.queueFifoRead = self.configuration["queueFifoRead"]
        self.is_connected = self.configuration["is_connected"]
        self.is_readytorun = self.configuration["is_readytorun"]
        self.initialization_error = self.configuration["initialization_error"]
        self.list_registers = self.configuration["list_registers"]
        self.actual_fifo_depth = self.configuration["actual_fifo_depth"]
        self.fpgarunning = self.configuration["fpgarunning"]
        self.fpga_started = self.configuration["fpga_started"]
        self.list_fifos_to_read_continously = self.configuration[
            "list_fifos_to_read_continously"
        ]

        self.fifo_chuck_size_digital = self.configuration["fifo_chuck_size_digital"]
        self.fifo_chuck_size_analog = self.configuration["fifo_chuck_size_analog"]
        self.expected_words_data_digital = self.configuration["expected_words_data_digital"]
        self.expected_words_data_analog = self.configuration["expected_words_data_analog"]
        self.initial_registers = self.configuration["initial_registers"]
        self.detector_model = normalize_detector_model(
            self.configuration.get("detector_model", DETECTOR_SPAD_ARRAY)
        )
        if self._uses_nifpga_fifo():
            self.process_label = f"NI FPGA control + FIFO reader ({self.detector_model})"
        else:
            self.process_label = f"NI FPGA control only ({self.detector_model})"
        logger.debug(self.configuration)

        # mp_mng = mp.Manager()

        self.list_fifos = []  # mp_mng.list()
        self.fifo_last_read_time = {}
        self.fifo_element_remaining = {}

        self.nifpga_session = None
        self.use_rust_fifo = use_rust_fifo
        self.rust_reader_ready = mp.Event()
        self.detector_source_ready = mp.Event()
        
        self.fpgarunning_internal = False
        logger.debug("%s %s", self.process_label, "INIT done")

        # self.rust_subprocess = None

    def loop_run_check(self):
        if self._uses_rust_fifo_reader():
            from ..fifo import RustFastFifoReader

            try:

                self.rust_fifo_reader = RustFastFifoReader(
                    self.bitfile,
                    self.list_fifos,
                    self.fifo_chuck_size_digital.value,
                    self.fifo_chuck_size_analog.value,
                    self.requested_fifo_depth,
                    self.ni_address
                )
                self.rust_reader_ready.set()

            except Exception as e:
                import traceback

                print("Error while creating RustFastFifoReader:")
                print(f"{type(e).__name__}: {e}")
                traceback.print_exc()

                self.stop_event.set()


        while not self.stop_event.is_set():
            if self.fpgarunning.is_set() and not self.fpgarunning_internal:
                self.nifpga_session.run()
                self.fpgarunning_internal = True
                self.fpga_started.set()
                logger.debug("%s %s", self.process_label, "nifpga_session.run()")
                self.fpgarunning.clear()                
        logger.debug("self.stop_event.is_set()")

        if self._uses_rust_fifo_reader():
            self.rust_reader_ready.clear()
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
                        logger.debug("%s %s %s %s %s", "self.queueRegisterWrite", repr(e), " ERROR", current_register, command[current_register])
                        try:
                            logger.debug("%s %s %s", "self.queueRegisterWrite SECOND ATTEMPT", current_register, command[current_register])
                            self.nifpga_session.registers[current_register].write(
                                command[current_register]
                            )
                        except Exception as e:
                            logger.debug("%s %s %s %s %s", "self.queueRegisterWrite 2nd attempt", repr(e), " ERROR", current_register, command[current_register])
        logger.debug("self.stop_event.is_set()")

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
                        logger.debug("%s %s %s %s", "self.queueRegisterReadReq", repr(e), "ERROR", command)
                self.queueRegisterRead.put(out_dict)
        logger.debug("self.stop_event.is_set()")

    def loop_fifoWrite(self):
        while not self.stop_event.is_set():
            if not self.queueFifoWrite.empty():
                command = self.queueFifoWrite.get()
                logger.debug("%s %s", "loop_fifoWrite", command)
                for current_fifo in command:
                    self.nifpga_session.fifos[current_fifo].write(command[current_fifo])
        logger.debug("self.stop_event.is_set()")

    def loop_fifoRead(self):
        while not self.stop_event.is_set():
            if not self.queueFifoReadReq.empty():
                out_dict = {}
                command = self.queueFifoReadReq.get()
                logger.debug(command)
                for current_fifo in command:
                    if current_fifo == "stream_out_main":
                        chunk = self.fifo_chuck_size_digital.value
                    elif current_fifo == "stream_out_aux":
                        chunk = self.fifo_chuck_size_analog.value
                    else:
                        logger.debug("BUG")
                        chunk = self.fifo_chuck_size_digital.value
                    elements_to_be_read = (
                        self.fifo_element_remaining[current_fifo] // chunk
                    ) * chunk
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
                            self.queueFifoRead.put_nowait(out_dict)

                    except nifpga.FifoTimeoutError:
                        pass
        logger.debug("self.stop_event.is_set()")

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
                    if current_fifo == "stream_out_main":
                        chunk = self.fifo_chuck_size_digital.value
                    elif current_fifo == "stream_out_aux":
                        chunk = self.fifo_chuck_size_analog.value
                    else:
                        logger.debug("BUG")
                        chunk = self.fifo_chuck_size_digital.value
                    elements_to_be_read = (
                        self.fifo_element_remaining[current_fifo] // chunk
                    ) * chunk
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
                    if current_fifo == "stream_out_main":
                        chunk = self.fifo_chuck_size_digital.value
                    elif current_fifo == "stream_out_aux":
                        chunk = self.fifo_chuck_size_analog.value
                    else:
                        logger.debug("BUG")
                        chunk = self.fifo_chuck_size_digital.value
                    elements_to_be_read = (
                        self.fifo_element_remaining[current_fifo] // chunk
                    ) * chunk
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
                            out_dict[current_fifo] = [read_data, length]
                            self.queueFifoRead.put(out_dict)

        logger.debug("self.stop_event.is_set()")



    def loop_fifoReadContinously_Rust_fifo(self, current_fifo):
        out_dict = {}
        self.rust_reader_ready.wait() 
        while not self.stop_event.is_set():
            current_time = perf_counter_ns()
            delta_time = current_time - self.fifo_last_read_time[current_fifo]
            if delta_time > self.timeout_fifos:
                read_data = self.rust_fifo_reader.read_data(current_fifo)
                self.fifo_last_read_time[current_fifo] = current_time
                length = len(read_data)
                if length > 0:
                    out_dict[current_fifo] = [read_data, length]
                    self.queueFifoRead.put_nowait(out_dict)
        logger.debug("self.stop_event.is_set()")

    def _uses_nifpga_fifo(self):
        return detector_uses_nifpga_fifo(self.detector_model)

    def _uses_rust_fifo_reader(self):
        return self._uses_nifpga_fifo() and self.use_rust_fifo == True

    def run(self):
        # self.thread_check_parent = CheckParentAlive(self, self.stop_event, note="FpgaHandleProcess")

        p = psutil.Process(os.getpid())
        p.nice(psutil.HIGH_PRIORITY_CLASS)
        logger.debug("%s %s %s %s", self.process_label, "RUN - PID:", os.getpid(), p.nice())

        logger.debug("nifpga.Session(self.bitfile, self.ni_address)")
        # print(self.configuration)
        try:
            self.nifpga_session = nifpga.Session(self.bitfile, self.ni_address)
            logger.debug("nifpga.Session(self.bitfile, self.ni_address) DONE!")
            available_registers = set(self.nifpga_session.registers.keys())
            available_fifos = set(self.nifpga_session.fifos.keys())
            required_fifos = (
                list(self.list_fifos_to_read_continously)
                if self._uses_nifpga_fifo()
                else []
            )
            validate_fpga_interface(
                available_registers,
                available_fifos,
                required_fifos,
            )
            self.is_connected.set()

        except Exception as e:
            message = str(e) or repr(e)
            self.initialization_error["message"] = message
            logger.exception("FPGA initialization failed: %s", message)
            self.is_connected.clear()
            # Wake the parent handshake immediately so the GUI can report the
            # real error instead of waiting for an opaque timeout.
            self.is_readytorun.set()

        if self.is_connected.is_set():


            self.stop_done_event.clear()

            if self._uses_nifpga_fifo():
                self.list_fifos[:] = list(self.nifpga_session.fifos.keys())
            else:
                self.list_fifos[:] = []
            self.list_registers[:] = list(self.nifpga_session.registers.keys())

            if self._uses_nifpga_fifo():
                logger.debug("%s %s", "NI FPGA FIFOs available: ", self.list_fifos)
            else:
                logger.debug("%s %s", self.process_label, "FIFOs disabled")
            logger.debug("%s %s", "Registers: ", self.list_registers)

            # self.nifpga_session = nifpga.Session(self.bitfile, self.ni_address)

            self.nifpga_session.reset()

            if self._uses_nifpga_fifo():
                for fifo in self.list_fifos:
                    if self.use_rust_fifo == False:
                        self.actual_fifo_depth.value = self.nifpga_session.fifos[fifo].configure(
                            self.requested_fifo_depth
                        )
                        self.nifpga_session.fifos[fifo].configure(self.requested_fifo_depth)
                        self.nifpga_session.fifos[fifo].start()
                    logger.debug("%s %s %s %s %s %s", "stream_out_main", fifo, "req:", self.requested_fifo_depth, "actual:", self.actual_fifo_depth.value)
                    self.fifo_element_remaining[fifo] = 0
            else:
                self.actual_fifo_depth.value = 0
                self.list_fifos_to_read_continously[:] = []
                self.fifo_element_remaining.clear()
                for register in ("stream_out_aux_enable", "stream_out_main_enable", "dfd_enable"):
                    if register in self.initial_registers:
                        self.initial_registers[register] = False

            # debug(self.fifo_element_remaining)
            # Here we assume the configured depth is the same for all FIFOs.

            logger.debug("%s %s", self.process_label, "started")
            for register in dict(self.initial_registers):
                try:
                    if self.initial_registers[register] is not None:
                        self.nifpga_session.registers[register].write(
                            self.initial_registers[register]
                        )
                    logger.debug("%s %s %s", "initial_registers: ", register, self.initial_registers[register])
                except Exception as e:
                    logger.debug("%s %s %s %s %s %s", "initial_registers - self.queueRegisterWrite", repr(e), " ERROR", register, "========", self.initial_registers)
            logger.debug("initial_registers done")

            # emptyQueue(self.queueRegisterWrite)
            # emptyQueue(self.queueRegisterReadReq)
            # emptyQueue(self.queueRegisterRead)
            emptyQueue(self.queueFifoWrite)
            emptyQueue(self.queueFifoReadReq)
            emptyQueue(self.queueFifoRead)

            self.is_readytorun.set()

            for fifo in self.list_fifos:
                self.fifo_last_read_time[fifo] = perf_counter_ns()  # time

            logger.debug("ready to run")

            if not self._uses_nifpga_fifo():
                threads = [
                    (Thread(target=self.loop_run_check), "loop_run_check"),
                ]
            elif self.use_rust_fifo == True:
                threads = [
                    (Thread(target=self.loop_run_check), "loop_run_check"),
                    (Thread(target=self.loop_fifoWrite), "loop_fifoWrite"),
                    #(Thread(target=self.loop_fifoReadContinously_Rust),"loop_fifoReadContinously"),
                    # (Thread(target=self.loop_fifoReadContinously), "loop_fifoReadContinously"),
                    # (Thread(target=self.loop_fifoRead), "loop_fifoRead"),  #OLD NOT USED
                    # (Thread(target=self.loop_writeReg), "loop_writeReg"),  #OLD NOT USED
                    # (Thread(target=self.loop_readReq), "loop_readReq"),    #OLD NOT USED
                ]
                for fifo in self.list_fifos:
                    threads.append( (Thread(target=self.loop_fifoReadContinously_Rust_fifo, args=(fifo,)),"loop_fifoReadContinously_Rust_fifo "+fifo))
            else:
                threads = [
                    (Thread(target=self.loop_run_check), "loop_run_check"),
                    (Thread(target=self.loop_fifoWrite), "loop_fifoWrite"),
                    (Thread(target=self.loop_fifoReadContinously),"loop_fifoReadContinously"),
                    # (Thread(target=self.loop_fifoReadContinously), "loop_fifoReadContinously"),
                    # (Thread(target=self.loop_fifoRead), "loop_fifoRead"),  #OLD NOT USED
                    # (Thread(target=self.loop_writeReg), "loop_writeReg"),  #OLD NOT USED
                    # (Thread(target=self.loop_readReq), "loop_readReq"),    #OLD NOT USED
                ]

            for th, name in threads:
                th.start()
                logger.debug("%s %s", self.process_label, name + ".start()")

            self.stop_event.wait(-1)

            logger.debug("stop_event.wait DONE")

            for th, name in threads:
                th.join()
                logger.debug("%s %s", self.process_label, name + ".join()")

            logger.debug("stop_event.wait DONE")
            if self._uses_rust_fifo_reader():
                self.rust_fifo_reader.close()
            self.detector_source_ready.clear()

        self.stop_event.set() #in the case fail force it

        if self.nifpga_session is not None:
            self.nifpga_session.abort()
            self.nifpga_session.reset()
            self.nifpga_session.close()

        self.stop_done_event.set()
        logger.debug("self.nifpga_session.reset()\nself.nifpga_session.close()")
        self.is_connected.clear()
        self.fpgarunning_internal = False
        self.fpga_started.clear()
        self.fpgarunning.clear()
        self.stop_event.clear()
        logger.debug("%s %s", self.process_label, "stopped")

    def stop(self):
        self.stop_event.set()

    def terminate(self) -> None:
        self.stop()

        try:
            self.nifpga_session.abort()
            self.nifpga_session.reset()
            self.nifpga_session.close()
        except:
            logger.debug("nifpga_session was already terminated.")

        if self.stop_done_event.wait(timeout=1.0):
            logger.debug("%s %s", self.process_label, "STOP nicely")
        else:
            logger.debug("%s %s", self.process_label, "STOP BADLY")
        self.stop_done_event.clear()
        super().terminate()


class NiFpgaControlProcess(FpgaHandleProcess):
    """NI-FPGA register/control process, with FIFO reading enabled for SPAD data."""
