"""Read, write, and translate the stable BrightEyes ``.cfg`` schema."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..acquisition.settings import AcquisitionConfig, DetectorConfig, OutputConfig, ScanGeometry
from ..acquisition.detectors.models import detector_uses_flare
from ..acquisition.detectors.flare.config import FlareSettings


class NumpyJSONEncoder(json.JSONEncoder):
    """Encode NumPy arrays without changing the legacy JSON ``.cfg`` layout."""

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class LegacyConfigurationCodec:
    """Lossless dictionary boundary for legacy JSON-based ``.cfg`` files."""

    @staticmethod
    def loads(text: str) -> dict[str, Any]:
        payload = json.loads(text.replace(", \n", ","))
        if not isinstance(payload, dict):
            raise ValueError("BrightEyes configuration root must be a JSON object")
        return payload

    @classmethod
    def load(cls, filename: str | Path) -> dict[str, Any]:
        return cls.loads(Path(filename).read_text(encoding="utf-8"))

    @staticmethod
    def dumps(payload: Mapping[str, Any], *, encoder=None) -> str:
        kwargs = {"cls": encoder} if encoder is not None else {}
        return json.dumps(dict(payload), **kwargs).replace(",", ",\n")

    @classmethod
    def dump(cls, filename: str | Path, payload: Mapping[str, Any], *, encoder=None) -> None:
        Path(filename).write_text(cls.dumps(payload, encoder=encoder), encoding="utf-8")


class LegacyConfigurationTranslator:
    """Translate typed values without discarding unknown legacy keys."""

    @staticmethod
    def from_legacy(payload: Mapping[str, Any]) -> AcquisitionConfig:
        legacy = deepcopy(dict(payload))
        geometry = ScanGeometry(
            pixels=int(legacy.get("nx", 1)),
            lines=int(legacy.get("ny", 1)),
            frames=int(legacy.get("nframe", 1)),
            repetitions=int(legacy.get("nrep", 1)),
            timebins_per_pixel=int(legacy.get("timebin_per_pixel", 1)),
        )
        detector = DetectorConfig(
            model=str(legacy.get("detector_model", "SPAD Array")),
            channels=int(legacy.get("spad_channels", 25)),
            address=str(legacy.get("niAddr", "RIO0")),
            bitfile=str(legacy.get("bitFile", "")),
            pispad23_host=str(legacy.get("pispad23_host", "127.0.0.1")),
            pispad23_port=int(legacy.get("pispad23_port", 9997)),
            flare=(FlareSettings.from_legacy(legacy) if detector_uses_flare(legacy.get("detector_model"))
                   else FlareSettings()),
        )
        output = OutputConfig(filename=Path(str(legacy.get("filename", "DEFAULT.h5"))))
        return AcquisitionConfig(geometry=geometry, detector=detector, output=output, legacy=legacy)

    @staticmethod
    def to_legacy(config: AcquisitionConfig) -> dict[str, Any]:
        payload = deepcopy(dict(config.legacy))
        payload.update(
            {
                "nx": config.geometry.pixels,
                "ny": config.geometry.lines,
                "nframe": config.geometry.frames,
                "nrep": config.geometry.repetitions,
                "timebin_per_pixel": config.geometry.timebins_per_pixel,
                "detector_model": config.detector.model,
                "spad_channels": str(config.detector.channels),
                "niAddr": config.detector.address,
                "bitFile": config.detector.bitfile,
                "filename": str(config.output.filename),
            }
        )
        if "pispad23_host" in payload or config.detector.pispad23_host != "127.0.0.1":
            payload["pispad23_host"] = config.detector.pispad23_host
        if "pispad23_port" in payload or config.detector.pispad23_port != 9997:
            payload["pispad23_port"] = config.detector.pispad23_port
        if detector_uses_flare(config.detector.model):
            payload.update(config.detector.flare.legacy_values())
        return payload
