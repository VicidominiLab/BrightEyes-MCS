"""FPGA control without detector receivers, processing, or storage."""

from .models import DETECTOR_DISABLED


class DisabledDetectorPipeline:
    detector_model = DETECTOR_DISABLED

    def make_receiver_queue(self, acquisition):
        return None

    def make_receiver_process(self, acquisition, receiver_queue, start_event):
        return None

    def make_data_preprocess(self, acquisition, receiver_queue):
        return None

    def make_acquisition_loop(self, acquisition, do_not_save):
        return None

    def make_raw_stream_writer(self, acquisition, receiver_queue):
        return None
