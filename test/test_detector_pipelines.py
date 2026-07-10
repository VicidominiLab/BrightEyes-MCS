import unittest

from brighteyes_mcs.libs.detectors import create_detector_pipeline
from brighteyes_mcs.libs.detectors.pi23.pipeline import Pi23DetectorPipeline
from brighteyes_mcs.libs.detectors.spad.pipeline import SpadDetectorPipeline
from brighteyes_mcs.libs.detector_backends import (
    DETECTOR_PI23_TT,
    DETECTOR_PI_23,
    DETECTOR_SPAD_ARRAY,
    DETECTOR_SPAD_TTM,
)


class TestDetectorPipelines(unittest.TestCase):
    def test_factory_selects_spad_pipeline_by_default(self):
        spad_pipeline = create_detector_pipeline(DETECTOR_SPAD_ARRAY)
        spad_ttm_pipeline = create_detector_pipeline(DETECTOR_SPAD_TTM)

        self.assertIsInstance(spad_pipeline, SpadDetectorPipeline)
        self.assertIsInstance(spad_ttm_pipeline, SpadDetectorPipeline)
        self.assertEqual(spad_ttm_pipeline.detector_model, DETECTOR_SPAD_TTM)
        self.assertIsInstance(create_detector_pipeline("unknown"), SpadDetectorPipeline)

    def test_factory_selects_pi23_pipeline(self):
        pi23_pipeline = create_detector_pipeline(DETECTOR_PI_23)
        pi23tt_pipeline = create_detector_pipeline(DETECTOR_PI23_TT)

        self.assertIsInstance(pi23_pipeline, Pi23DetectorPipeline)
        self.assertIsInstance(pi23tt_pipeline, Pi23DetectorPipeline)
        self.assertEqual(pi23tt_pipeline.detector_model, DETECTOR_PI23_TT)


if __name__ == "__main__":
    unittest.main()

