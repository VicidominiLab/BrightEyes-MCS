import multiprocessing as mp
import time
import numpy as np

from ..libs.mp_circular_shm import CircularSharedBuffer

import psutil
import nifpga
import os
from datetime import datetime
from .print_dec import print_dec, set_debug
from .processes.fpga_handle_process_fifo_new import FpgaHandleProcess

class FpgaHandle(object):
    def __init__(
        self,
        bitfile,
        ni_address,
        mp_manager,
        timeout_fifos=10e6,
        requested_depth=10000,
        list_fifos=[],
        initial_registers_dict={},
        debug=True,
        use_rust_fifo=True,
        bitfile2="",
        ni_address2="",
    ):
        set_debug(debug)
        self.mp_manager = mp_manager

        p = psutil.Process(os.getpid())
        # p.nice(psutil.REALTIME_PRIORITY_CLASS)
        print_dec("FpgaHandle RUN - PID:", os.getpid(), p.nice())

        p = psutil.Process(self.mp_manager._process.pid)
        p.nice(psutil.HIGH_PRIORITY_CLASS)
        print_dec("self.mp_manager - PID:", self.mp_manager._process.pid, p.nice())

        self.nifpga_obj = None
        self.nifpga_obj2 = None



        self.configuration = {
            "timeout_fifos": timeout_fifos,
            "bitfile": bitfile,
            "ni_address": ni_address,
            "bitfile2": bitfile2,
            "ni_address2": ni_address2,
            "requested_depth": requested_depth,
            "list_fifos_to_read_continously": self.mp_manager.list(list(list_fifos)),
            "stop_event": self.mp_manager.Event(),
            "stop_done_event": self.mp_manager.Event(),
            "print_event": self.mp_manager.Event(),
            "queueFifoWrite": self.mp_manager.Queue(),
            "queueFifoReadReq": self.mp_manager.Queue(),
            "queueFifoRead": self.mp_manager.Queue(),
            "queueFifoReadCircularBuffer": {
                                "FIFO" : CircularSharedBuffer(1024*1024*64, dtype=np.uint64),
                                "FIFOAnalog": CircularSharedBuffer(1024*1024*64, dtype=np.uint64)
                             },
            "is_connected": self.mp_manager.Event(),
            "is_readytorun": self.mp_manager.Event(),
            "list_registers": self.mp_manager.list(),
            "actual_depth": self.mp_manager.Value("I", 0),
            "fpgarunning": self.mp_manager.Event(),
            "fifo_chuck_size": self.mp_manager.Value("I", 0),
            "expected_raw_data": self.mp_manager.Value("I", 0),
            "initial_registers": initial_registers_dict,  # self.mp_manager.dict()
        }

        self.use_rust_fifo = use_rust_fifo

        def __del__(self):
            self.stop()

        # self.fpga_handle_process = FpgaHandleProcess(self.configuration)
        # print("FpgaHandleProcess(self.configuration)")

    def run(self, initial_registers={}):
        self.configuration["initial_registers"].clear()
        self.configuration["initial_registers"].update(initial_registers)
        print_dec("self.fpga_handle_process.start()")
        print_dec("initial_registers")
        print_dec(initial_registers)
        self.fpga_handle_process = FpgaHandleProcess(
            self.configuration, use_rust_fifo=self.use_rust_fifo
        )

        self.fpga_handle_process.daemon = True

        print_dec(self.configuration["is_readytorun"].is_set())
        self.fpga_handle_process.start()
        print_dec("Waiting for the ready to run")
        tstart = datetime.now()
        flag = self.configuration["is_readytorun"].wait(timeout=1000)
        if flag != True:
            raise ("TIMEOUT")
        tstop = datetime.now()
        print_dec(
            "self.configuration['is_readytorun'] now is up after ",
            (tstop - tstart).microseconds * 1e-6,
            "s",
        )
        print_dec("self.fpga_handle_process.start() done")

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
            print_dec("FPGA2 started")

        # Session(bitfile, resource, no_run=False, reset_if_last_session_on_exit=False, **kwargs)
        self.nifpga_obj = nifpga.Session(
            bitfile=self.configuration["bitfile"],
            resource=self.configuration["ni_address"],
            no_run=True,
            reset_if_last_session_on_exit=False,
        )
        print_dec("FPGA1 configured")


    def fpga_handle_process_isAlive(self):
        try:
            return self.fpga_handle_process.is_alive()
        except:
            return False

    def runfpga(self):
        print_dec("nifpga_session.run()")
        self.configuration["fpgarunning"].set()

    def stop(self):
        self.configuration["stop_event"].set()
        if self.fpga_handle_process.is_alive():
            self.fpga_handle_process.terminate()
        print_dec("self.fpga_handle_process.join() stopped")
        self.nifpga_obj.abort()
        self.nifpga_obj.reset()
        self.nifpga_obj.close()

        print_dec("nifpga_obj killed")

        if self.nifpga_obj2 is not None:
            self.nifpga_obj2.abort()
            self.nifpga_obj2.reset()
            self.nifpga_obj2.close()

        print_dec("nifpga_obj2 killed")

    # SLOW VERSION
    # def register_read(self, register, timeout=1000):
    #     print_dec("register_read.empty before?",self.configuration['queueRegisterReadReq'].empty())
    #     self.configuration['queueRegisterReadReq'].put((register,))
    #     ret=self.configuration['queueRegisterRead'].get(timeout=timeout)
    #     print_dec("register_read", register, ret)
    #     return ret
    #
    # def register_read_all(self, timeout=1000):
    #     mydict = {}
    #     print_dec(self.configuration['list_registers'])
    #     for i in self.configuration['list_registers']:
    #         mydict.update(self.register_read(i, timeout))
    #
    #     print_dec(mydict)
    #     return mydict

    def register_read(self, register, timeout=1000):
        register = list(register)
        ret = {}
        for i in register:
            ret.update({i: self.nifpga_obj.registers[i].read()})

        l = list(ret.keys())
        if not (list(register) == register):
            raise ("ERROR register_read", register, l)

        return ret

    def register_read_all(self, timeout=5000):
        mydict = {}
        mydict = self.register_read(list(self.configuration["list_registers"]), timeout)
        return mydict

    def register_write(self, register, data):
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

    def set_fifo_chuck_size(self, fifo_chuck_size):
        self.configuration["fifo_chuck_size"].value = fifo_chuck_size

    def set_expected_raw_data(self, expected_raw_data):
        self.configuration["expected_raw_data"].value = expected_raw_data

    def set_list_fifos_to_read_continously(
        self, list_fifos_to_read_continously=["FIFO"]
    ):
        self.configuration["list_fifos_to_read_continously"][:] = []
        self.configuration["list_fifos_to_read_continously"][:] = list(
            list_fifos_to_read_continously
        )

    def get_actual_depth(self):
        return self.configuration["actual_depth"].value
