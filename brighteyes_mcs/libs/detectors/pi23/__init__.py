"""PI23 detector pipeline."""

__all__ = ["Pi23DetectorPipeline"]


def __getattr__(name):
    if name == "Pi23DetectorPipeline":
        from .pipeline import Pi23DetectorPipeline

        return Pi23DetectorPipeline
    raise AttributeError(name)

