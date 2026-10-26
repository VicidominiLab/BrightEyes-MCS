"""Serialize Flare GUI writes with configuration without blocking Qt."""

from datetime import datetime
import threading


class FlareLiveControls:
    def __init__(self):
        self.io_lock = threading.RLock()
        self._lock = threading.Lock()
        self._requested = {}
        self._pending = {}
        self._geometry = None
        self._applied_geometry = None
        self._events = []

    def request(self, registers, *, geometry=None):
        with self._lock:
            self._requested.update(registers)
            self._pending.update(registers)
            if geometry is not None:
                self._geometry = dict(geometry)

    def has_pending(self):
        with self._lock:
            return bool(self._pending)

    def discard_pending(self):
        with self._lock:
            self._pending.clear()

    def geometry(self):
        with self._lock:
            return dict(self._applied_geometry) if self._applied_geometry is not None else None

    def events(self, start=0):
        with self._lock:
            return [dict(event) for event in self._events[start:]]

    def begin_run(self):
        with self._lock:
            self._events.clear()

    def _write(self, client, name, value):
        event = {
            "name": name, "value": value,
            "requested_at": datetime.now().astimezone().isoformat(),
        }
        try:
            result = client.write_register(name, value)
            event["readback"] = result["value"]
            return result
        except Exception as error:
            event["error"] = str(error)
            raise
        finally:
            event["finished_at"] = datetime.now().astimezone().isoformat()
            with self._lock:
                self._events.append(event)

    def write(self, client, name, value):
        with self.io_lock:
            return self._write(client, name, value)

    def apply(self, client, *, restore=False):
        with self.io_lock:
            with self._lock:
                registers = dict(self._requested if restore else self._pending)
                geometry = dict(self._geometry) if self._geometry is not None else None
                # Consume before I/O: edits arriving during the request stay pending.
                self._pending.clear()
            results = {}
            axes = ("axis_start_offset_volts", "axis_calibration_volts_per_step")
            for name, value in registers.items():
                results[name] = self._write(client, name, value)["value"]
            if any(name in registers for name in axes):
                results["command"] = self._write(client, "command", 1)["value"]
                with self._lock:
                    self._applied_geometry = geometry
            return results
