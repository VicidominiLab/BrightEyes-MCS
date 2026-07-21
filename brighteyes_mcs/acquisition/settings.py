"""Typed settings that describe a BrightEyes acquisition run."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ScanGeometry:
    pixels: int = 1
    lines: int = 1
    frames: int = 1
    repetitions: int = 1
    timebins_per_pixel: int = 1


@dataclass(frozen=True)
class DetectorConfig:
    model: str = "SPAD Array"
    channels: int = 25
    address: str = "RIO0"
    bitfile: str = ""
    pi23_host: str = "127.0.0.1"
    pi23_port: int = 9997


@dataclass(frozen=True)
class OutputConfig:
    filename: Path = Path("DEFAULT.h5")
    raw_stream: bool = False
    raw_files: Mapping[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class AcquisitionConfig:
    geometry: ScanGeometry = field(default_factory=ScanGeometry)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    legacy: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)
