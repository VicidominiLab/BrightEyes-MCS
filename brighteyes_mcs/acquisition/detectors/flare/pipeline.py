"""Explicit native Flare dispatch; never fall back to the NI packed-word path."""

from ..models import DETECTOR_FLARE


class FlareDetectorPipeline:
    detector_model = DETECTOR_FLARE

    def make_receiver_queue(self, acquisition, *args, **kwargs):
        raise RuntimeError("Flare uses FlareAcquisition, not the legacy NI acquisition manager")

    make_receiver_process = make_data_preprocess = make_acquisition_loop = (
        make_raw_stream_writer
    ) = make_receiver_queue
