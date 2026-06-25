"""SPAD detector pipeline."""

<<<<<<< HEAD
__all__ = ["SpadDetectorPipeline"]


def __getattr__(name):
    if name == "SpadDetectorPipeline":
        from .pipeline import SpadDetectorPipeline

        return SpadDetectorPipeline
    raise AttributeError(name)

=======
from .pipeline import SpadDetectorPipeline

__all__ = ["SpadDetectorPipeline"]

>>>>>>> 619fdf7fdf53bf0ecff498d62b7597014e19b4f1
