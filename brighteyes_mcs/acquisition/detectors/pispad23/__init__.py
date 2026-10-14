"""PISPAD23 detector implementation."""

__all__ = ["PISPAD23DetectorPipeline"]


def __getattr__(name):
    """Keep backend imports independent from the worker-based pipeline."""

    if name == "PISPAD23DetectorPipeline":
        from .pipeline import PISPAD23DetectorPipeline

        globals()[name] = PISPAD23DetectorPipeline
        return PISPAD23DetectorPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
