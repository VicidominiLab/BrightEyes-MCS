"""Canonical detector selection and pipeline implementations."""

__all__ = ["create_detector_pipeline"]


def __getattr__(name):
    """Load the pipeline factory without eagerly importing every pipeline."""

    if name == "create_detector_pipeline":
        from .factory import create_detector_pipeline

        globals()[name] = create_detector_pipeline
        return create_detector_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
