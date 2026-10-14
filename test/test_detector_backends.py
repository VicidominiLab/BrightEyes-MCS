import unittest

import numpy as np

from brighteyes_mcs.acquisition.detectors.backends import (
    DETECTOR_PISPAD23_TT,
    DETECTOR_PISPAD23,
    DETECTOR_SPAD_ARRAY,
    DETECTOR_SPAD_TTM,
    PISPAD23RandomBunchSource,
    PISPAD23RawBunch,
    detector_uses_pispad23_pipeline,
    detector_uses_nifpga_fifo,
    detector_uses_spad_pipeline,
    normalize_detector_model,
    pispad23_decode_raw_bunch_to_spad_preview_words,
)


class Counter:
    def __init__(self, value):
        self.value = value


class TestDetectorBackends(unittest.TestCase):
    def test_detector_model_normalization(self):
        self.assertEqual(normalize_detector_model(DETECTOR_PISPAD23), DETECTOR_PISPAD23)
        self.assertEqual(normalize_detector_model(DETECTOR_PISPAD23_TT), DETECTOR_PISPAD23_TT)
        self.assertEqual(normalize_detector_model(DETECTOR_SPAD_TTM), DETECTOR_SPAD_TTM)
        self.assertEqual(normalize_detector_model("PISPAD23"), DETECTOR_PISPAD23)
        self.assertEqual(normalize_detector_model("SPAD"), DETECTOR_SPAD_ARRAY)
        self.assertEqual(normalize_detector_model("TCP/IP - PI SPAD23R (Intensity)"), DETECTOR_PISPAD23)
        self.assertEqual(normalize_detector_model("FPGA - SPAD"), DETECTOR_SPAD_ARRAY)
        self.assertEqual(normalize_detector_model("unknown"), DETECTOR_SPAD_ARRAY)
        self.assertTrue(detector_uses_nifpga_fifo(DETECTOR_SPAD_ARRAY))
        self.assertTrue(detector_uses_nifpga_fifo(DETECTOR_SPAD_TTM))
        self.assertFalse(detector_uses_nifpga_fifo(DETECTOR_PISPAD23))
        self.assertFalse(detector_uses_nifpga_fifo(DETECTOR_PISPAD23_TT))
        self.assertTrue(detector_uses_spad_pipeline(DETECTOR_SPAD_TTM))
        self.assertTrue(detector_uses_pispad23_pipeline(DETECTOR_PISPAD23_TT))

    def test_pispad23_random_source_returns_raw_bunches_until_expected_words(self):
        source = PISPAD23RandomBunchSource(
            fifo_chuck_size_digital=Counter(4),
            fifo_chuck_size_analog=Counter(2),
            expected_words_data_digital=Counter(20),
            expected_words_data_analog=Counter(0),
            digital_words_per_sample=2,
            packet_chunk_multiplier=(1, 3),
            seed=1,
        )
        source.start()

        first_bunch = source.read_bunch("stream_out_main")
        self.assertIsInstance(first_bunch, PISPAD23RawBunch)
        self.assertIsInstance(first_bunch.payload, dict)
        self.assertIn("channel_counts", first_bunch.payload)
        self.assertNotIsInstance(first_bunch, np.ndarray)

        first_packet = pispad23_decode_raw_bunch_to_spad_preview_words(
            first_bunch,
            digital_words_per_sample=2,
        )
        self.assertEqual(first_packet.dtype, np.uint64)
        self.assertGreater(first_packet.shape[0], 0)
        self.assertEqual(first_packet.shape[0] % 4, 0)

        received = first_packet.shape[0]
        while True:
            bunch = source.read_bunch("stream_out_main")
            if bunch is None:
                break
            packet = pispad23_decode_raw_bunch_to_spad_preview_words(
                bunch,
                digital_words_per_sample=2,
            )
            received += packet.shape[0]

        self.assertEqual(received, 20)


if __name__ == "__main__":
    unittest.main()
