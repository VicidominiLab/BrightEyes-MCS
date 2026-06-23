"""SPAD detector pipeline."""

__all__ = ["SpadDetectorPipeline"]


def __getattr__(name):
    if name == "SpadDetectorPipeline":
        from .pipeline import SpadDetectorPipeline

        return SpadDetectorPipeline
    raise AttributeError(name)

