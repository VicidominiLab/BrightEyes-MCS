"""PI23 detector pipeline."""

<<<<<<< HEAD
__all__ = ["Pi23DetectorPipeline"]


def __getattr__(name):
    if name == "Pi23DetectorPipeline":
        from .pipeline import Pi23DetectorPipeline

        return Pi23DetectorPipeline
    raise AttributeError(name)

=======
from .pipeline import Pi23DetectorPipeline

__all__ = ["Pi23DetectorPipeline"]

>>>>>>> 619fdf7fdf53bf0ecff498d62b7597014e19b4f1
