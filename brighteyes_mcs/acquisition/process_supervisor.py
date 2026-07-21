"""Consistent registration and shutdown policy for acquisition child processes."""

from __future__ import annotations

from collections import OrderedDict


class ProcessSupervisor:
    def __init__(self):
        self._processes = OrderedDict()

    def register(self, name, process):
        if process is not None:
            self._processes[name] = process
        return process

    def get(self, name):
        return self._processes.get(name)

    def is_alive(self, name) -> bool:
        process = self.get(name)
        try:
            return process is not None and process.is_alive()
        except Exception:
            return False

    def start(self, name) -> None:
        process = self.get(name)
        if process is not None:
            process.start()

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
            process.terminate()
            process.join(timeout=2)

    def clear(self) -> None:
        self._processes.clear()
