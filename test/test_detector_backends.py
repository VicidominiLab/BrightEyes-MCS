import unittest

import numpy as np

from brighteyes_mcs.libs.detector_backends import (
    DETECTOR_PI_23,
    DETECTOR_SPAD_ARRAY,
    Pi23RandomPacketSource,
    detector_uses_nifpga_fifo,
    normalize_detector_model,
)


class Counter:
    def __init__(self, value):
        self.value = value


class TestDetectorBackends(unittest.TestCase):
    def test_detector_model_normalization(self):
        self.assertEqual(normalize_detector_model(DETECTOR_PI_23), DETECTOR_PI_23)
        self.assertEqual(normalize_detector_model("unknown"), DETECTOR_SPAD_ARRAY)
        self.assertTrue(detector_uses_nifpga_fifo(DETECTOR_SPAD_ARRAY))
        self.assertFalse(detector_uses_nifpga_fifo(DETECTOR_PI_23))

    def test_pi23_random_source_returns_uint64_until_expected_words(self):
        source = Pi23RandomPacketSource(
            fifo_chuck_size_digital=Counter(4),
            fifo_chuck_size_analog=Counter(2),
            expected_words_data_digital=Counter(20),
            expected_words_data_analog=Counter(0),
            packet_chunk_multiplier=(1, 3),
            seed=1,
        )
        source.start()

        first_packet = source.read_data("FIFO")
        self.assertEqual(first_packet.dtype, np.uint64)
        self.assertGreater(first_packet.shape[0], 0)
        self.assertEqual(first_packet.shape[0] % 4, 0)

        received = first_packet.shape[0]
        while True:
            packet = source.read_data("FIFO")
            if packet.shape[0] == 0:
                break
            received += packet.shape[0]

        self.assertEqual(received, 20)


if __name__ == "__main__":
    unittest.main()
