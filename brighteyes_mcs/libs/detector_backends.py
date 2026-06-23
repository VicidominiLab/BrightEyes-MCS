"""Detector model constants and detector-source scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns

import numpy as np


DETECTOR_SPAD_ARRAY = "SPAD Array"
DETECTOR_PI_23 = "PI 23"
DETECTOR_MODELS = (DETECTOR_SPAD_ARRAY, DETECTOR_PI_23)


def normalize_detector_model(detector_model):
    """Return a supported detector model string, defaulting old configs to SPAD."""
    if detector_model in DETECTOR_MODELS:
        return detector_model
    return DETECTOR_SPAD_ARRAY


def detector_uses_nifpga_fifo(detector_model):
    """True when detector data is received from NI FPGA FIFOs."""
    return normalize_detector_model(detector_model) == DETECTOR_SPAD_ARRAY


@dataclass
class Pi23RawBunch:
    """
    Mock PI23 raw bunch.

    This is intentionally not the SPAD FIFO raw-word format. Replace
    ``Pi23RandomBunchSource.pi23_receive_raw_bunch`` and
    ``pi23_decode_raw_bunch_to_spad_preview_words`` when the real PI23 library
    and raw packet layout are available.
    """

    fifo_name: str
    timestamp_ns: int
    sample_count: int
    payload: dict


class Pi23RandomBunchSource:
    """
    Temporary PI23 source that simulates detector-native raw bunches.

    The receiver returns ``Pi23RawBunch`` instances. The downstream PI23
    preprocessing step is responsible for decoding those raw bunches into the
    normalized preview/acquisition representation currently consumed by the
    shared acquisition loop.
    """

    def __init__(
        self,
        fifo_chuck_size_digital,
        fifo_chuck_size_analog,
        expected_words_data_digital,
        expected_words_data_analog,
        digital_words_per_sample=2,
        digital_output_channels=25,
        packet_chunk_multiplier=(64, 256),
        seed=None,
    ):
        self.fifo_chuck_size_digital = fifo_chuck_size_digital
        self.fifo_chuck_size_analog = fifo_chuck_size_analog
        self.expected_words_data_digital = expected_words_data_digital
        self.expected_words_data_analog = expected_words_data_analog
        self.digital_words_per_sample = max(1, int(digital_words_per_sample))
        self.digital_output_channels = max(1, int(digital_output_channels))
        self.packet_chunk_multiplier = packet_chunk_multiplier
        self.rng = np.random.default_rng(seed)
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}
        self.started_at_ns = None

    def start(self):
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}
        self.started_at_ns = perf_counter_ns()

    def stop(self):
        self.started_at_ns = None

    def read_bunch(self, fifo_name):
        n_words = self._next_packet_words(fifo_name)
        if n_words <= 0:
            return None

        sample_count = self._word_count_to_sample_count(fifo_name, n_words)
        bunch = self.pi23_receive_raw_bunch(fifo_name, sample_count)
        self.generated_words[fifo_name] = (
            self.generated_words.get(fifo_name, 0)
            + self._sample_count_to_word_count(fifo_name, bunch.sample_count)
        )
        return bunch

    def pi23_receive_raw_bunch(self, fifo_name, sample_count):
        """
        Simulate receiving one PI23-native raw bunch.

        Replace this function with the real PI23 library call. Keep its return
        value detector-native; do not translate to SPAD FIFO raw words here.
        """
        if fifo_name == "FIFOAnalog":
            payload = {
                "analog_samples": self.rng.integers(
                    -(2**15),
                    2**15,
                    size=(sample_count, 2),
                    dtype=np.int32,
                )
            }
        else:
            payload = {
                "channel_counts": self.rng.poisson(
                    lam=0.2,
                    size=(sample_count, self.digital_output_channels),
                ).astype(np.uint16),
                "extra_flags": self.rng.integers(
                    0,
                    2,
                    size=(sample_count, 2),
                    dtype=np.uint8,
                ),
            }

        return Pi23RawBunch(
            fifo_name=fifo_name,
            timestamp_ns=perf_counter_ns(),
            sample_count=int(sample_count),
            payload=payload,
        )

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
            return int(packet_words)

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

    def _word_count_to_sample_count(self, fifo_name, word_count):
        if fifo_name == "FIFOAnalog":
            return int(word_count)
        return int(word_count) // self.digital_words_per_sample

    def _sample_count_to_word_count(self, fifo_name, sample_count):
        if fifo_name == "FIFOAnalog":
            return int(sample_count)
        return int(sample_count) * self.digital_words_per_sample


def pi23_decode_raw_bunch_to_spad_preview_words(
    raw_bunch,
    digital_words_per_sample=2,
):
    """
    Decode a PI23 raw bunch into the current normalized preview word stream.

    The normalized stream is a temporary compatibility boundary for the existing
    preview/H5 writer. The input remains PI23-native, so the real PI23 decoder
    can replace this function without touching the receiver or manager.
    """
    if raw_bunch is None or raw_bunch.sample_count <= 0:
        return np.array([], dtype=np.uint64)

    if raw_bunch.fifo_name == "FIFOAnalog":
        analog = np.asarray(raw_bunch.payload["analog_samples"], dtype=np.int32)
        high = analog[:, 0].astype(np.uint32).astype(np.uint64) << np.uint64(32)
        low = analog[:, 1].astype(np.uint32).astype(np.uint64)
        return high | low

    counts = np.asarray(raw_bunch.payload["channel_counts"], dtype=np.uint64)
    extra = np.asarray(raw_bunch.payload["extra_flags"], dtype=np.uint64)
    words_per_sample = max(1, int(digital_words_per_sample))
    sample_count = counts.shape[0]
    words = np.empty(sample_count * words_per_sample, dtype=np.uint64)
    sample_sum = counts.sum(axis=1, dtype=np.uint64)
    extra_sum = extra.sum(axis=1, dtype=np.uint64)
    for word_idx in range(words_per_sample):
        rotated = np.roll(counts, shift=word_idx, axis=1)
        weighted = rotated[:, word_idx % counts.shape[1]] << np.uint64(word_idx % 16)
        words[word_idx::words_per_sample] = (
            sample_sum
            ^ weighted
            ^ (extra_sum << np.uint64(48))
            ^ np.uint64(word_idx)
        )
    return words
