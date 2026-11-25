import unittest


from brighteyes_mcs.acquisition.detectors.backends import (
    DETECTOR_PISPAD23_TT,
    DETECTOR_PISPAD23,
    DETECTOR_SPAD_ARRAY,
    DETECTOR_SPAD_TTM,
    detector_uses_pispad23_pipeline,
    detector_uses_nifpga_fifo,
    detector_uses_spad_pipeline,
    normalize_detector_model,
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
