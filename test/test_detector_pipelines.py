import unittest

from brighteyes_mcs.libs.detectors import create_detector_pipeline
from brighteyes_mcs.libs.detectors.pi23.pipeline import Pi23DetectorPipeline
from brighteyes_mcs.libs.detectors.spad.pipeline import SpadDetectorPipeline
from brighteyes_mcs.libs.detector_backends import DETECTOR_PI_23, DETECTOR_SPAD_ARRAY


class TestDetectorPipelines(unittest.TestCase):
    def test_factory_selects_spad_pipeline_by_default(self):
        self.assertIsInstance(
            create_detector_pipeline(DETECTOR_SPAD_ARRAY),
            SpadDetectorPipeline,
        )
        self.assertIsInstance(create_detector_pipeline("unknown"), SpadDetectorPipeline)

    def test_factory_selects_pi23_pipeline(self):
        self.assertIsInstance(
            create_detector_pipeline(DETECTOR_PI_23),
            Pi23DetectorPipeline,
        )


if __name__ == "__main__":
    unittest.main()

