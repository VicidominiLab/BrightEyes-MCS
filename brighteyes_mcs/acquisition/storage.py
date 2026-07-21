"""Lifecycle of the dedicated HDF5 writer process."""

from __future__ import annotations

import multiprocessing as mp

from ..storage.h5 import H5ManagerProcess


class AcquisitionStorage:
    def __init__(self):
        self.command_queue = None
        self.response_queue = None
        self.process = None

    def start(self, pending_counter):
        self.command_queue = mp.Queue()
        self.response_queue = mp.Queue()
        self.process = H5ManagerProcess(
            self.command_queue, self.response_queue, shm_number_of_threads_h5=pending_counter
        )
        self.process.daemon = True
        self.process.start()
        return self.command_queue, self.response_queue, self.process

    def disabled(self):
        self.command_queue = self.response_queue = self.process = None
        return None, None, None

    def stop(self, timeout=2):
        process = self.process
        if process is not None:
            process.join(timeout=timeout)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        self.command_queue = self.response_queue = self.process = None
