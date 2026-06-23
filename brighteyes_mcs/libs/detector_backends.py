"""Detector data-source scaffolding for BrightEyes acquisition packets."""

from time import perf_counter_ns

import numpy as np


DETECTOR_SPAD_ARRAY = "SPAD Array"
DETECTOR_PI_23 = "PI 23"
DETECTOR_MODELS = (DETECTOR_SPAD_ARRAY, DETECTOR_PI_23)


def normalize_detector_model(detector_model):
    """Return a supported detector model string."""
    if detector_model in DETECTOR_MODELS:
        return detector_model
    return DETECTOR_SPAD_ARRAY


def detector_uses_nifpga_fifo(detector_model):
    """True when raw data is received from NI FPGA FIFOs."""
    return normalize_detector_model(detector_model) == DETECTOR_SPAD_ARRAY


class Pi23RandomPacketSource:
    """
    Temporary PI 23 packet source.

    The public hook for the real detector is ``pi23_receive_detector_bunch``. Replace
    that method with calls to the PI 23 vendor/library API, then adapt
    ``pi23_convert_detector_bunch_to_fifo_words`` so it returns the BrightEyes raw
    ``uint64`` words consumed by the existing conversion pipeline.
    """

    def __init__(
        self,
        fifo_chuck_size_digital,
        fifo_chuck_size_analog,
        expected_words_data_digital,
        expected_words_data_analog,
        packet_chunk_multiplier=(64, 256),
        seed=None,
    ):
        self.fifo_chuck_size_digital = fifo_chuck_size_digital
        self.fifo_chuck_size_analog = fifo_chuck_size_analog
        self.expected_words_data_digital = expected_words_data_digital
        self.expected_words_data_analog = expected_words_data_analog
        self.packet_chunk_multiplier = packet_chunk_multiplier
        self.rng = np.random.default_rng(seed)
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}
        self.started_at_ns = None

    def start(self):
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}
        self.started_at_ns = perf_counter_ns()

    def stop(self):
        self.started_at_ns = None

    def read_data(self, fifo_name):
        n_words = self._next_packet_words(fifo_name)
        if n_words <= 0:
            return np.array([], dtype=np.uint64)

        detector_bunch = self.pi23_receive_detector_bunch(fifo_name, n_words)
        raw_words = self.pi23_convert_detector_bunch_to_fifo_words(
            fifo_name,
            detector_bunch,
        )
        raw_words = np.asarray(raw_words, dtype=np.uint64)
        self.generated_words[fifo_name] = (
            self.generated_words.get(fifo_name, 0) + raw_words.shape[0]
        )
        return raw_words

    def pi23_receive_detector_bunch(self, fifo_name, n_words):
        """
        Simulate receiving one bunch from the PI 23 detector.

        Replace this function with the real PI 23 library call. Keep the return
        value as a structured detector bunch, then convert it in
        ``pi23_convert_detector_bunch_to_fifo_words``.
        """
        if fifo_name == "FIFOAnalog":
            return self.rng.integers(0, 2**16, size=n_words, dtype=np.uint64)
        return self.rng.integers(0, 2**24, size=n_words, dtype=np.uint64)

    def pi23_convert_detector_bunch_to_fifo_words(self, fifo_name, detector_bunch):
        """
        Convert a detector bunch into BrightEyes FIFO-compatible raw words.

        The simulator already produces compatible ``uint64`` words. The real
        PI 23 implementation should translate the detector library payload here
        so the existing preview/acquisition conversion chain can keep running.
        """
        return detector_bunch

    def _next_packet_words(self, fifo_name):
        chunk = self._chunk_words(fifo_name)
        if chunk <= 0:
            return 0

        min_multiplier, max_multiplier = self.packet_chunk_multiplier
        multiplier = int(self.rng.integers(min_multiplier, max_multiplier + 1))
        packet_words = chunk * multiplier

        expected_words = self._expected_words(fifo_name)
        generated_words = self.generated_words.get(fifo_name, 0)
        if expected_words <= 0:
            return packet_words

        remaining_words = expected_words - generated_words
        if remaining_words <= 0:
            return 0
        if remaining_words < packet_words:
            packet_words = remaining_words
        if remaining_words > chunk:
            packet_words = max(chunk, packet_words - (packet_words % chunk))
        return int(packet_words)

    def _chunk_words(self, fifo_name):
        if fifo_name == "FIFOAnalog":
            return int(self.fifo_chuck_size_analog.value)
        return int(self.fifo_chuck_size_digital.value)

    def _expected_words(self, fifo_name):
        if fifo_name == "FIFOAnalog":
            return int(self.expected_words_data_analog.value)
        return int(self.expected_words_data_digital.value)
