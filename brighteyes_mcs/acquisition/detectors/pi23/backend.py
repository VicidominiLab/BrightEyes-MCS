"""PI23 detector TCP source and decoding helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os
import socket
from time import perf_counter_ns

import numpy as np
from numpy.random import default_rng

from brighteyes_mcs.logging_setup import logger


DONE_SENTINEL = b"DONE"
ERROR_SENTINEL = b"ERROR"
DEFAULT_PI23_HOST = "127.0.0.1"
DEFAULT_PI23_PORT = 9997
DEFAULT_PI23_CHANNELS = 23


def pi23_debug_enabled(default=False):
    value = os.environ.get("PI23_DEBUG", os.environ.get("DEBUG"))
    if value is None:
        return bool(default)
    return value.strip().lower() in ("1", "true", "yes", "on", "debug")


def pi23_debug(*objects, enabled=False):
    if pi23_debug_enabled(enabled):
        print("[PI23]", *objects, flush=True)


@dataclass
class Pi23RawBunch:
    """
    PI23-native raw bunch.

    For scanning binary TCP data, ``payload["channel_counts"]`` is a
    ``(sample_count, n_channels)`` array. Samples are already ordered in the
    same X/Y/Z/timebin sequence expected by the shared acquisition loop, but
    they remain detector counts until preprocessing packs them.
    """

    fifo_name: str
    timestamp_ns: int
    sample_count: int
    payload: dict


class Pi23TcpBunchSource:
    """
    TCP client for the Pi Imaging pSPAD ``CS`` scanning-binary command.

    The pSPAD server returns channel image planes as bytes, followed by
    ``DONE``. This source expands those planes into detector-native per-sample
    counts in the same scan order the SPAD acquisition worker already uses.
    """

    def __init__(
        self,
        fifo_chuck_size_digital,
        fifo_chuck_size_analog,
        expected_words_data_digital,
        expected_words_data_analog,
        digital_words_per_sample=2,
        digital_output_channels=25,
        scan_x=1,
        scan_y=1,
        scan_frames=1,
        timebins_per_pixel=1,
        dwell_us=2.0,
        external_frame=0,
        host=None,
        port=None,
        socket_timeout=30.0,
        read_chunk_size=32768,
        packet_samples=65536,
        detector_channels=None,
        shared_dict=None,
        debug=False,
    ):
        read_chunk_size = 8192 #hard-coded to avoid too large reads

        self.fifo_chuck_size_digital = fifo_chuck_size_digital
        self.fifo_chuck_size_analog = fifo_chuck_size_analog
        self.expected_words_data_digital = expected_words_data_digital
        self.expected_words_data_analog = expected_words_data_analog
        self.digital_words_per_sample = max(1, int(digital_words_per_sample))
        self.digital_output_channels = max(1, int(digital_output_channels))
        self.scan_x = max(1, int(scan_x))
        self.scan_y = max(1, int(scan_y))
        self.scan_frames = max(1, int(scan_frames))
        self.timebins_per_pixel = max(1, int(timebins_per_pixel))
        self.dwell_us = 0 if float(dwell_us) == 0.0 else float(dwell_us)
        self.external_frame = int(external_frame)
        self.host = host or os.environ.get("PI23_HOST", DEFAULT_PI23_HOST)
        self.port = int(port or os.environ.get("PI23_PORT", DEFAULT_PI23_PORT))
        self.socket_timeout = float(os.environ.get("PI23_TIMEOUT", socket_timeout))
        self.read_chunk_size = int(os.environ.get("PI23_READ_CHUNK", read_chunk_size))
        self.packet_samples = max(1, int(os.environ.get("PI23_PACKET_SAMPLES", packet_samples)))
        self.detector_channels = int(
            detector_channels or os.environ.get("PI23_CHANNELS", DEFAULT_PI23_CHANNELS)
        )
        self.shared_dict = shared_dict
        self.debug = bool(debug)
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}
        self.started_at_ns = None
        self._counts = None
        self._sample_cursor = 0

    def start(self):
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}
        self.started_at_ns = perf_counter_ns()
        self._counts = None
        self._sample_cursor = 0
        logger.debug("%s %s %s %s %s", "PI23 source start", f"{self.host}:{self.port}", f"scan={self.scan_x}x{self.scan_y}x{self.scan_frames}", f"timebins={self.timebins_per_pixel}", f"dwell_us={self.dwell_us}")
        pi23_debug(
            "source start",
            f"{self.host}:{self.port}",
            f"scan={self.scan_x}x{self.scan_y}x{self.scan_frames}",
            f"timebins={self.timebins_per_pixel}",
            f"dwell_us={self.dwell_us}",
            enabled=self.debug,
        )

    def stop(self):
        logger.debug("PI23 source stop")
        pi23_debug("source stop", enabled=self.debug)
        self.started_at_ns = None
        self._counts = None
        self._sample_cursor = 0

    def read_bunch(self, fifo_name):
        if fifo_name == "FIFOAnalog":
            return None

        if self._counts is None:
            logger.debug("%s %s", "PI23 source receiving scan", fifo_name)
            self._counts = self.pi23_receive_scan_counts()
            self._sample_cursor = 0
            logger.debug("%s %s %s", "PI23 source received scan", f"samples={self._counts.shape[0]}", f"channels={self._counts.shape[1]}")
            pi23_debug(
                "received scan",
                f"samples={self._counts.shape[0]}",
                f"channels={self._counts.shape[1]}",
                enabled=self.debug,
            )

        remaining_samples = self._counts.shape[0] - self._sample_cursor
        if remaining_samples <= 0:
            expected_words = self._expected_words("FIFO")
            generated_words = self.generated_words.get("FIFO", 0)
            if expected_words > 0 and generated_words >= expected_words:
                return None
            logger.debug("%s %s", "PI23 source receiving next scan", fifo_name)
            self._counts = self.pi23_receive_scan_counts()
            self._sample_cursor = 0
            logger.debug("%s %s %s", "PI23 source received next scan", f"samples={self._counts.shape[0]}", f"channels={self._counts.shape[1]}")
            remaining_samples = self._counts.shape[0]
            if remaining_samples <= 0:
                return None

        n_words = self._next_packet_words("FIFO", remaining_samples)
        sample_count = max(1, min(remaining_samples, n_words // self.digital_words_per_sample))
        start = self._sample_cursor
        stop = start + sample_count
        counts = self._counts[start:stop]
        self._sample_cursor = stop

        bunch = Pi23RawBunch(
            fifo_name="FIFO",
            timestamp_ns=perf_counter_ns(),
            sample_count=int(counts.shape[0]),
            payload={
                "channel_counts": counts,
                "source": "tcp_cs_binary",
                "sample_start": start,
            },
        )
        self.generated_words["FIFO"] = self.generated_words.get("FIFO", 0) + (
            bunch.sample_count * self.digital_words_per_sample
        )
        logger.debug("%s %s %s", "PI23 source emit bunch", f"samples={bunch.sample_count}", f"cursor={self._sample_cursor}/{self._counts.shape[0]}")
        pi23_debug(
            "emit bunch",
            f"samples={bunch.sample_count}",
            f"cursor={self._sample_cursor}/{self._counts.shape[0]}",
            enabled=self.debug,
        )
        return bunch

    def pi23_receive_scan_counts(self):
        payload = self._receive_cs_binary_payload()
        planes = self._payload_to_planes(payload)
        counts = self._planes_to_sample_counts(planes)
        return counts

    def _receive_cs_binary_payload(self):
        command = (
            f"CS,{self.dwell_us},{self.scan_frames},"
            f"{self.scan_x},{self.scan_y},{self.external_frame}\n"
        )
        pi23_debug("connect", f"{self.host}:{self.port}", enabled=self.debug)
        logger.debug("%s %s", "PI23 TCP connect", f"{self.host}:{self.port}")
        data = bytearray()
        with socket.create_connection(
            (self.host, self.port),
            timeout=self.socket_timeout,
        ) as tcp:
            tcp.settimeout(self.socket_timeout)
            try:
                greeting = tcp.recv(8192)
            except socket.timeout:
                greeting = b""
            if greeting:
                greeting_decoded = greeting.decode("utf-8", errors="replace").strip()
                if self.shared_dict is not None:
                    self.shared_dict["pi23_greeting_raw"] = greeting.hex(" ")
                    self.shared_dict["pi23_greeting_decoded"] = greeting_decoded
                logger.debug("%s %s", "PI23 TCP greeting", greeting_decoded)
                pi23_debug(
                    "greeting",
                    greeting_decoded,
                    enabled=self.debug,
                )
            pi23_debug("send", command.strip(), enabled=self.debug)
            logger.debug("%s %s", "PI23 TCP send", command.strip())
            tcp.sendall(command.encode("utf-8"))

            while True:
                block = tcp.recv(self.read_chunk_size)
                if not block:
                    raise RuntimeError("PI23 TCP stream closed before DONE")
                data.extend(block)
                if data.endswith(DONE_SENTINEL):
                    data = data[: -len(DONE_SENTINEL)]
                    break
                if data.endswith(ERROR_SENTINEL) or ERROR_SENTINEL in data[-256:]:
                    tail = bytes(data[-512:]).decode("utf-8", errors="replace")
                    raise RuntimeError(f"PI23 TCP server returned ERROR: {tail}")

        pi23_debug("payload bytes", len(data), enabled=self.debug)
        logger.debug("%s %s", "PI23 TCP payload bytes", len(data))
        return bytes(data)

    def _payload_to_planes(self, payload):
        pixels_per_frame = self.scan_x * self.scan_y
        if pixels_per_frame <= 0:
            raise RuntimeError("PI23 invalid scan dimensions")
        if len(payload) % pixels_per_frame != 0:
            raise RuntimeError(
                "PI23 payload length is not aligned to scan pixels: "
                f"bytes={len(payload)} pixels_per_frame={pixels_per_frame}"
            )

        total_planes = len(payload) // pixels_per_frame
        if total_planes % self.scan_frames == 0:
            detector_planes = total_planes // self.scan_frames
        else:
            detector_planes = self.detector_channels
            inferred_frames = total_planes // max(detector_planes, 1)
            if inferred_frames > 0:
                self.scan_frames = inferred_frames

        if detector_planes <= 0:
            raise RuntimeError("PI23 payload contains no image planes")

        if detector_planes != self.detector_channels:
            pi23_debug(
                "detector plane count inferred",
                detector_planes,
                f"(configured {self.detector_channels})",
                enabled=self.debug,
            )
            self.detector_channels = detector_planes

        array = np.frombuffer(payload, dtype=np.uint8)
        expected = self.scan_frames * detector_planes * self.scan_y * self.scan_x
        if array.size != expected:
            raise RuntimeError(
                "PI23 payload size mismatch after inference: "
                f"got={array.size} expected={expected}"
            )
        return array.reshape(self.scan_frames, detector_planes, self.scan_y, self.scan_x)

    def _planes_to_sample_counts(self, planes):
        frames, detector_planes, _scan_y, _scan_x = planes.shape
        output_channels = self.digital_output_channels
        sample_count = frames * self.scan_y * self.scan_x * self.timebins_per_pixel
        counts = np.zeros((sample_count, output_channels), dtype=np.uint16)

        usable_channels = min(detector_planes, output_channels)
        pixel_major = planes[:, :usable_channels, :, :].transpose(0, 2, 3, 1)
        pixel_major = pixel_major.reshape(frames * self.scan_y * self.scan_x, usable_channels)
        counts[0:: self.timebins_per_pixel, :usable_channels] = pixel_major
        return counts

    def _next_packet_words(self, fifo_name, remaining_samples=None):
        chunk = self._chunk_words(fifo_name)
        if chunk <= 0:
            chunk = self.digital_words_per_sample
        target_words = self.packet_samples * self.digital_words_per_sample
        packet_words = max(chunk, target_words, self.digital_words_per_sample)
        if chunk > 0:
            packet_words -= packet_words % chunk

        expected_words = self._expected_words(fifo_name)
        generated_words = self.generated_words.get(fifo_name, 0)
        if expected_words <= 0:
            if remaining_samples is None:
                return int(packet_words)
            return min(int(packet_words), int(remaining_samples) * self.digital_words_per_sample)

        remaining_words = expected_words - generated_words
        if remaining_samples is not None:
            remaining_words = min(remaining_words, int(remaining_samples) * self.digital_words_per_sample)
        if remaining_words <= 0:
            return 0
        if remaining_words < packet_words:
            packet_words = remaining_words
        if remaining_words > chunk and chunk > 0:
            packet_words = max(chunk, packet_words - (packet_words % chunk))
        packet_words -= packet_words % self.digital_words_per_sample
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


def pi23_pack_counts_to_spad25_words(counts):
    counts = np.asarray(counts, dtype=np.uint64)
    if counts.ndim != 2:
        raise ValueError("PI23 channel counts must be a 2-D array")

    sample_count = counts.shape[0]
    padded = np.zeros((sample_count, 25), dtype=np.uint64)
    usable = min(counts.shape[1], 25)
    padded[:, :usable] = counts[:, :usable]

    words = np.zeros(sample_count * 2, dtype=np.uint64)
    word0 = np.zeros(sample_count, dtype=np.uint64)
    word1 = np.zeros(sample_count, dtype=np.uint64)

    def put(target, channel, shift, mask):
        values = np.minimum(padded[:, channel], np.uint64(mask))
        target[:] |= values << np.uint64(shift)

    for channel, shift, mask in (
        (0, 5, 0xF),
        (1, 9, 0xF),
        (2, 13, 0xF),
        (3, 17, 0xF),
        (4, 21, 0xF),
        (5, 25, 0xF),
        (17, 29, 0x3F),
        (18, 35, 0x1F),
        (19, 40, 0xF),
        (20, 44, 0xF),
        (21, 48, 0xF),
        (22, 52, 0xF),
        (23, 56, 0xF),
        (24, 60, 0xF),
    ):
        put(word0, channel, shift, mask)

    for channel, shift, mask in (
        (6, 5, 0x1F),
        (7, 10, 0x3F),
        (8, 16, 0x1F),
        (9, 21, 0xF),
        (10, 25, 0xF),
        (11, 29, 0x3F),
        (12, 35, 0x3FF),
        (13, 45, 0x3F),
        (14, 51, 0xF),
        (15, 55, 0xF),
        (16, 59, 0x1F),
    ):
        put(word1, channel, shift, mask)

    words[0::2] = word0
    words[1::2] = word1
    return words


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

    words_per_sample = max(1, int(digital_words_per_sample))
    if words_per_sample != 2:
        raise NotImplementedError("PI23 TCP scanning currently packs to the 25-channel SPAD word layout")

    counts = np.asarray(raw_bunch.payload["channel_counts"], dtype=np.uint64)
    return pi23_pack_counts_to_spad25_words(counts)


class Pi23RandomBunchSource:
    """In-memory PI23 raw-bunch source used by tests and offline dry-runs."""

    def __init__(
        self,
        fifo_chuck_size_digital,
        fifo_chuck_size_analog,
        expected_words_data_digital,
        expected_words_data_analog,
        digital_words_per_sample=2,
        digital_output_channels=25,
        packet_chunk_multiplier=(1, 4),
        seed=None,
        **_kwargs,
    ):
        self.fifo_chuck_size_digital = fifo_chuck_size_digital
        self.fifo_chuck_size_analog = fifo_chuck_size_analog
        self.expected_words_data_digital = expected_words_data_digital
        self.expected_words_data_analog = expected_words_data_analog
        self.digital_words_per_sample = max(1, int(digital_words_per_sample))
        self.digital_output_channels = max(1, int(digital_output_channels))
        low, high = packet_chunk_multiplier
        self.packet_chunk_multiplier = (max(1, int(low)), max(1, int(high)))
        # Importing numpy.random lazily after Qt widgets have been destroyed can
        # crash some Windows/Python builds during garbage collection.  The
        # module-level import keeps dry-run generation deterministic and safe.
        self.rng = default_rng(seed)
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}

    def start(self):
        self.generated_words = {"FIFO": 0, "FIFOAnalog": 0}

    def stop(self):
        pass

    def read_bunch(self, fifo_name):
        if fifo_name == "FIFOAnalog":
            return None

        n_words = self._next_packet_words("FIFO")
        if n_words <= 0:
            return None

        sample_count = max(1, n_words // self.digital_words_per_sample)
        counts = self.rng.integers(
            0,
            16,
            size=(sample_count, self.digital_output_channels),
            dtype=np.uint16,
        )
        bunch = Pi23RawBunch(
            fifo_name="FIFO",
            timestamp_ns=perf_counter_ns(),
            sample_count=int(sample_count),
            payload={
                "channel_counts": counts,
                "source": "random",
                "sample_start": self.generated_words["FIFO"] // self.digital_words_per_sample,
            },
        )
        self.generated_words["FIFO"] += sample_count * self.digital_words_per_sample
        return bunch

    def _next_packet_words(self, fifo_name):
        expected_words = self._expected_words(fifo_name)
        generated_words = self.generated_words.get(fifo_name, 0)
        if expected_words <= generated_words:
            return 0

        chunk = max(self.digital_words_per_sample, self._chunk_words(fifo_name))
        low, high = self.packet_chunk_multiplier
        multiplier = int(self.rng.integers(low, high + 1))
        packet_words = max(chunk, chunk * multiplier)
        packet_words -= packet_words % self.digital_words_per_sample

        remaining_words = expected_words - generated_words
        if packet_words > remaining_words:
            packet_words = remaining_words
        packet_words -= packet_words % self.digital_words_per_sample
        return int(packet_words)

    def _chunk_words(self, fifo_name):
        if fifo_name == "FIFOAnalog":
            return int(self.fifo_chuck_size_analog.value)
        return int(self.fifo_chuck_size_digital.value)

    def _expected_words(self, fifo_name):
        if fifo_name == "FIFOAnalog":
            return int(self.expected_words_data_analog.value)
        return int(self.expected_words_data_digital.value)
