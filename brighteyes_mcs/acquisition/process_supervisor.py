"""Consistent registration and shutdown policy for acquisition child processes."""

from __future__ import annotations

from collections import OrderedDict
from ..logging_setup import logger


class ProcessSupervisor:
    def __init__(self):
        self._processes = OrderedDict()
        self._reported_exits = set()

    def register(self, name, process):
        if process is not None:
            self._processes[name] = process
            self._reported_exits.discard(name)
        return process

    def get(self, name):
        return self._processes.get(name)

    def is_alive(self, name) -> bool:
        process = self.get(name)
        try:
            alive = process is not None and process.is_alive()
            if process is not None and not alive:
                code = getattr(process, "exitcode", None)
                if isinstance(code, int) and code != 0 and name not in self._reported_exits:
                    logger.error("Worker exited unexpectedly name=%s pid=%s code=%s hex=0x%08X",
                                 name, getattr(process, "pid", None), code, code & 0xFFFFFFFF)
                    self._reported_exits.add(name)
            return alive
        except Exception:
            return False

    def start(self, name) -> None:
        process = self.get(name)
        if process is not None:
            process.start()
            logger.info("Worker launched name=%s pid=%s", name, getattr(process, "pid", None))

    def stop(self, name, *, timeout=5.0, request_stop=True) -> None:
        process = self._processes.pop(name, None)
        if process is None:
            return
        if request_stop:
            stop = getattr(process, "stop", None)
            if stop is not None:
                stop()
        process.join(timeout=timeout)
        if process.is_alive():
            logger.warning("Worker stop timed out; terminating name=%s pid=%s timeout=%s",
                           name, getattr(process, "pid", None), timeout)
            process.terminate()
            process.join(timeout=2)
        logger.info("Worker stopped name=%s pid=%s exitcode=%s", name,
                    getattr(process, "pid", None), getattr(process, "exitcode", None))

    def clear(self) -> None:
        self._processes.clear()
        self._reported_exits.clear()
