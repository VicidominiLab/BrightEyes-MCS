"""Lifecycle states for acquisition coordination."""

from enum import Enum


class AcquisitionState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    READY = "ready"
    PREVIEWING = "previewing"
    ACQUIRING = "acquiring"
    STOPPING = "stopping"
    ERROR = "error"
