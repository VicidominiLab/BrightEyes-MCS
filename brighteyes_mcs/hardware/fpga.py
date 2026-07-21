"""Thin process/controller wrapper around the NI FPGA reader backends."""

import multiprocessing as mp
import time

import psutil
import nifpga
import os
from datetime import datetime
from brighteyes_mcs.logging_setup import logger, set_debug
from ..acquisition.workers.fpga import NiFpgaControlProcess
from ..acquisition.detectors.models import (
    DETECTOR_SPAD_ARRAY,
    detector_uses_nifpga_control,
    normalize_detector_model,
)

class FpgaHandle(object):
    def __init__(
        self,
        bitfile,
        ni_address,
        mp_manager,
        timeout_fifos=10e6,
        requested_fifo_depth=10000,
        list_fifos=None,
        initial_registers_dict=None,
        debug=True,
        use_rust_fifo=True,
        bitfile2="",
        ni_address2="",
        detector_model=DETECTOR_SPAD_ARRAY,
    ):
        set_debug(debug)
        self.mp_manager = mp_manager

        p = psutil.Process(os.getpid())
        # p.nice(psutil.REALTIME_PRIORITY_CLASS)
        logger.debug("%s %s %s", "FpgaHandle RUN - PID:", os.getpid(), p.nice())

        p = psutil.Process(self.mp_manager._process.pid)
        p.nice(psutil.HIGH_PRIORITY_CLASS)
        logger.debug("%s %s %s", "self.mp_manager - PID:", self.mp_manager._process.pid, p.nice())

        self.nifpga_obj = None
        self.nifpga_obj2 = None
        self.fpga_handle_process = None

        if list_fifos is None:
            list_fifos = []
        if initial_registers_dict is None:
            initial_registers_dict = {}

        self.configuration = {
            "timeout_fifos": timeout_fifos,
            "bitfile": bitfile,
            "ni_address": ni_address,
            "bitfile2": bitfile2,
            "ni_address2": ni_address2,
            "requested_fifo_depth": requested_fifo_depth,
            "list_fifos_to_read_continously": self.mp_manager.list(list(list_fifos)),
            "stop_event": self.mp_manager.Event(),
            "stop_done_event": self.mp_manager.Event(),
            "print_event": self.mp_manager.Event(),
            "queueFifoWrite": self.mp_manager.Queue(),
            "queueFifoReadReq": self.mp_manager.Queue(),
            "queueFifoRead": self.mp_manager.Queue(),
            "is_connected": self.mp_manager.Event(),
            "is_readytorun": self.mp_manager.Event(),
            "list_registers": self.mp_manager.list(),
            "actual_fifo_depth": self.mp_manager.Value("I", 0),
            "fpgarunning": self.mp_manager.Event(),
            "fifo_chuck_size_digital": self.mp_manager.Value("I", 0),
            "fifo_chuck_size_analog": self.mp_manager.Value("I", 0),
            "expected_words_data_digital": self.mp_manager.Value("q", 0),
            "expected_words_data_analog": self.mp_manager.Value("q", 0),
            "initial_registers": initial_registers_dict,  # self.mp_manager.dict()
            "detector_model": normalize_detector_model(detector_model),
        }

        self.use_rust_fifo = use_rust_fifo

        def __del__(self):
            self.stop()

        # self.fpga_handle_process = NiFpgaControlProcess(self.configuration)
        # print("NiFpgaControlProcess(self.configuration)")

    def run(self, initial_registers=None):
        if initial_registers is None:
            initial_registers = {}
        self.configuration["initial_registers"].clear()
        self.configuration["initial_registers"].update(initial_registers)
        if not detector_uses_nifpga_control(self.configuration["detector_model"]):
            logger.debug("Detector selected without NI FPGA control; skipping NI FPGA session startup")
            self.configuration["is_connected"].set()
            self.configuration["is_readytorun"].set()
            self.fpga_handle_process = None
            self.nifpga_obj = None
            self.nifpga_obj2 = None
            return

        logger.debug("self.fpga_handle_process.start()")
        logger.debug("initial_registers")
        logger.debug(initial_registers)
        self.fpga_handle_process = NiFpgaControlProcess(
            self.configuration, use_rust_fifo=self.use_rust_fifo
        )

        self.fpga_handle_process.daemon = True

        logger.debug(self.configuration["is_readytorun"].is_set())
        self.fpga_handle_process.start()
        logger.debug("Waiting for the ready to run")
        tstart = datetime.now()
        flag = self.configuration["is_readytorun"].wait(timeout=5.)
        if flag != True:
            raise ("TIMEOUT")
        tstop = datetime.now()
        logger.debug("%s %s %s", "self.configuration['is_readytorun'] now is up after ", (tstop - tstart).microseconds * 1e-6, "s")
        logger.debug("self.fpga_handle_process.start() done")

        if ((self.configuration["bitfile2"] != "") and
            (self.configuration["ni_address2"] != "")):

            self.nifpga_obj2 = nifpga.Session(
                bitfile=self.configuration["bitfile2"],
                resource=self.configuration["ni_address2"],
                no_run=False,      # Must run directly !!
                reset_if_last_session_on_exit=False,
            )
            if self.nifpga_obj2.fpga_vi_state != nifpga.FpgaViState.Running:
                raise("FPGA2 NOT STARTED")
            logger.debug("FPGA2 started")

        # Session(bitfile, resource, no_run=False, reset_if_last_session_on_exit=False, **kwargs)
        self.nifpga_obj = nifpga.Session(
            bitfile=self.configuration["bitfile"],
            resource=self.configuration["ni_address"],
            no_run=True,
            reset_if_last_session_on_exit=False,
        )
        logger.debug("FPGA1 configured")


    def fpga_handle_process_isAlive(self):
        try:
            return self.fpga_handle_process.is_alive()
        except:
            return False

    def runfpga(self):
        logger.debug("nifpga_session.run()")
        self.configuration["fpgarunning"].set()

    def stop(self):
        self.configuration["stop_event"].set()
        if self.fpga_handle_process is not None and self.fpga_handle_process.is_alive():
            self.fpga_handle_process.terminate()
        logger.debug("self.fpga_handle_process.join() stopped")
        if self.nifpga_obj is not None:
            self.nifpga_obj.abort()
            self.nifpga_obj.reset()
            self.nifpga_obj.close()

        logger.debug("nifpga_obj killed")

        if self.nifpga_obj2 is not None:
            self.nifpga_obj2.abort()
            self.nifpga_obj2.reset()
            self.nifpga_obj2.close()

        logger.debug("nifpga_obj2 killed")

    # SLOW VERSION
    # def register_read(self, register, timeout=1000):
    #     debug("register_read.empty before?",self.configuration['queueRegisterReadReq'].empty())
    #     self.configuration['queueRegisterReadReq'].put((register,))
    #     ret=self.configuration['queueRegisterRead'].get(timeout=timeout)
    #     debug("register_read", register, ret)
    #     return ret
    #
    # def register_read_all(self, timeout=1000):
    #     mydict = {}
    #     debug(self.configuration['list_registers'])
    #     for i in self.configuration['list_registers']:
    #         mydict.update(self.register_read(i, timeout))
    #
    #     debug(mydict)
    #     return mydict

    def register_read(self, register, timeout=1000):
        if not detector_uses_nifpga_control(self.configuration["detector_model"]):
            initial_registers = self.configuration["initial_registers"]
            return {name: initial_registers.get(name) for name in list(register)}

        register = list(register)
        ret = {}
        for i in register:
            ret.update({i: self.nifpga_obj.registers[i].read()})

        l = list(ret.keys())
        if not (list(register) == register):
            raise ("ERROR register_read", register, l)

        return ret

    def register_read_all(self, timeout=5000):
        if not detector_uses_nifpga_control(self.configuration["detector_model"]):
            return dict(self.configuration["initial_registers"])

        mydict = {}
        mydict = self.register_read(list(self.configuration["list_registers"]), timeout)
        return mydict

    def register_write(self, register, data):
        if not detector_uses_nifpga_control(self.configuration["detector_model"]):
            self.configuration["initial_registers"][register] = data
            return

        try:
            self.nifpga_obj.registers[register].write(data)
        except Exception as e:
            print("ERROR:", register, data, e)
        # self.configuration['queueRegisterWrite'].put({register: data})
    #
    # def fifo_read(self, fifoname, timeout):
    #     self.configuration["queueFifoReadReq"].put(
    #         [
    #             fifoname,
    #         ]
    #     )
    #     return self.configuration["queueFifoRead"].get(timeout=timeout)
    #
    # def read_fifo(self, fifo, timeout):
    #     return self.configuration["queueFifoRead"].get(timeout)

    def set_fifo_chuck_size_digital(self, fifo_chuck_size_digital):
        logger.debug("%s %s", "set_fifo_chuck_size_digital", fifo_chuck_size_digital)
        self.configuration["fifo_chuck_size_digital"].value = fifo_chuck_size_digital

    def set_fifo_chuck_size_analog(self, fifo_chuck_size_analog):
        logger.debug("%s %s", "set_fifo_chuck_size_analog", fifo_chuck_size_analog)
        self.configuration["fifo_chuck_size_analog"].value = fifo_chuck_size_analog

    def set_expected_words_data_digital(self, expected_words_data_digital):
        logger.debug("%s %s", "set_expected_words_data_digital", expected_words_data_digital)
        self.configuration["expected_words_data_digital"].value = expected_words_data_digital

    def set_expected_words_data_analog(self, expected_words_data_analog):
        logger.debug("%s %s", "set_expected_words_data_analog", expected_words_data_analog)
        self.configuration["expected_words_data_analog"].value = expected_words_data_analog

    def set_list_fifos_to_read_continously(
        self, list_fifos_to_read_continously=["FIFO"]
    ):
        self.configuration["list_fifos_to_read_continously"][:] = []
        self.configuration["list_fifos_to_read_continously"][:] = list(
            list_fifos_to_read_continously
        )

    def set_detector_model(self, detector_model=DETECTOR_SPAD_ARRAY):
        self.configuration["detector_model"] = normalize_detector_model(detector_model)

    def get_actual_fifo_depth(self):
        return self.configuration["actual_fifo_depth"].value

    def get_actual_depth(self):
        return self.get_actual_fifo_depth()

