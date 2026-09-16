"""PI23 detector implementation."""

__all__ = ["Pi23DetectorPipeline"]


def __getattr__(name):
    """Keep backend imports independent from the worker-based pipeline."""

    if name == "Pi23DetectorPipeline":
        from .pipeline import Pi23DetectorPipeline

        globals()[name] = Pi23DetectorPipeline
        return Pi23DetectorPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
