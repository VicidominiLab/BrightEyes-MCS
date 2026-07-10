"""Ophyd device for the BrightEyes-MCS low-level FPGA register map."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ophyd import Component, Device, Signal

from .registers import REGISTER_ATTR_BY_NAME, REGISTER_SPECS, REGISTER_SPECS_BY_NAME, RegisterSpec


class RegisterIO:
    """Small adapter interface used by the Ophyd signals."""

    def read_register(self, name: str) -> Any:
        raise NotImplementedError

    def write_register(self, name: str, value: Any) -> None:
        raise NotImplementedError

    def read_fifo(self, name: str, elements: int = 1, timeout: float | None = None) -> Any:
        raise NotImplementedError

    def write_fifo(self, name: str, value: Any, timeout: float | None = None) -> None:
        raise NotImplementedError


class MappingRegisterIO(RegisterIO):
    """In-memory register adapter for tests, demos, and simulated plans."""

    def __init__(self, initial: Mapping[str, Any] | None = None):
        self.values = dict(initial or {})
        self.fifos: dict[str, list[Any]] = {}

    def read_register(self, name: str) -> Any:
        return self.values.get(name)

    def write_register(self, name: str, value: Any) -> None:
        self.values[name] = value

    def read_fifo(self, name: str, elements: int = 1, timeout: float | None = None) -> list[Any]:
        fifo = self.fifos.setdefault(name, [])
        elements = max(0, int(elements))
        data = fifo[:elements]
        del fifo[:elements]
        return data

    def write_fifo(self, name: str, value: Any, timeout: float | None = None) -> None:
        self.fifos.setdefault(name, []).append(value)


class NifpgaRegisterIO(RegisterIO):
    """Adapter for an existing ``nifpga.Session`` instance."""

    def __init__(self, session: Any):
        self.session = session

    @classmethod
    def from_bitfile(cls, bitfile: str, resource: str, **session_kwargs: Any) -> "NifpgaRegisterIO":
        import nifpga

        return cls(nifpga.Session(bitfile, resource, **session_kwargs))

    def read_register(self, name: str) -> Any:
        return self.session.registers[name].read()

    def write_register(self, name: str, value: Any) -> None:
        self.session.registers[name].write(value)

    def read_fifo(self, name: str, elements: int = 1, timeout: float | None = None) -> Any:
        if timeout is None:
            return self.session.fifos[name].read(elements)
        return self.session.fifos[name].read(elements, timeout=timeout)

    def write_fifo(self, name: str, value: Any, timeout: float | None = None) -> None:
        fifo = self.session.fifos[name]
        if timeout is None:
            fifo.write(value)
        else:
            fifo.write(value, timeout=timeout)


def _default_value_for_dtype(dtype: str) -> Any:
    if dtype == "Bool":
        return False
    if dtype.endswith("-Array"):
        return []
    if dtype == "Fxp":
        return 0.0
    return 0


class BrightEyesRegisterSignal(Signal):
    """Signal that proxies one documented BrightEyes FPGA register."""

    def __init__(self, *args: Any, register: str, register_spec: RegisterSpec, **kwargs: Any):
        self.register = register
        self.register_spec = register_spec
        metadata = dict(kwargs.pop("metadata", {}) or {})
        metadata.update(
            {
                "register": register,
                "section": register_spec.section,
                "dtype": register_spec.dtype,
                "access": register_spec.access,
                "description": register_spec.description,
            }
        )
        kwargs.setdefault("value", _default_value_for_dtype(register_spec.dtype))
        kwargs["metadata"] = metadata
        super().__init__(*args, **kwargs)

    @property
    def register_io(self) -> RegisterIO:
        return self.parent.register_io

    def get(self, **kwargs: Any) -> Any:
        value = self.register_io.read_register(self.register)
        super().put(value, force=True)
        return value

    def put(self, value: Any, **kwargs: Any) -> Any:
        if not self.register_spec.writable:
            raise PermissionError(f"Register {self.register!r} is read-only")
        self.register_io.write_register(self.register, value)
        return super().put(value, **kwargs)


class _BrightEyesMCSLLBase(Device):
    register_specs = REGISTER_SPECS
    register_attr_by_name = REGISTER_ATTR_BY_NAME

    def __init__(self, *args: Any, register_io: RegisterIO | None = None, **kwargs: Any):
        self.register_io = register_io or MappingRegisterIO()
        super().__init__(*args, **kwargs)

    def get_signal(self, register_name: str) -> BrightEyesRegisterSignal:
        return getattr(self, self.register_attr_by_name[register_name])

    def read_registers(self, *register_names: str) -> dict[str, Any]:
        names = register_names or tuple(self.register_attr_by_name)
        return {name: self.get_signal(name).get() for name in names}

    def write_registers(self, values: Mapping[str, Any]) -> None:
        for register_name, value in values.items():
            self.get_signal(register_name).put(value)

    def describe_register(self, register_name: str) -> dict[str, Any]:
        spec = REGISTER_SPECS_BY_NAME[register_name]
        return {
            "attr": spec.attr,
            "section": spec.section,
            "dtype": spec.dtype,
            "access": spec.access,
            "description": spec.description,
        }

    def read_fifo(self, fifo_name: str, elements: int = 1, timeout: float | None = None) -> Any:
        return self.register_io.read_fifo(fifo_name, elements=elements, timeout=timeout)

    def write_fifo(self, fifo_name: str, value: Any, timeout: float | None = None) -> None:
        self.register_io.write_fifo(fifo_name, value, timeout=timeout)


def _build_device_class() -> type[_BrightEyesMCSLLBase]:
    attrs: dict[str, Any] = {
        "__module__": __name__,
        "__doc__": "Ophyd device mapping for BrightEyes-MCSLL FPGA registers.",
    }
    for spec in REGISTER_SPECS:
        kind = "config" if spec.writable else "normal"
        attrs[spec.attr] = Component(
            BrightEyesRegisterSignal,
            register=spec.name,
            register_spec=spec,
            kind=kind,
        )
    return type("BrightEyesMCSLLDevice", (_BrightEyesMCSLLBase,), attrs)


BrightEyesMCSLLDevice = _build_device_class()
