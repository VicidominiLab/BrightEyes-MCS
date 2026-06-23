import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(1, os.getcwd())

from brighteyes_mcs.gui.main_window import MainWindow


class TestH5MetadataCompatibility(unittest.TestCase):
    def test_gui_config_for_h5_uses_legacy_public_keys_for_spad(self):
        metadata = MainWindow._gui_config_for_h5(
            {
                "spad_channels": "25",
                "spad_cmd_length": "25",
                "spad_cmd_data": "33554431",
                "spad_cmd_invert": False,
                "detector_model": "SPAD Array",
            }
        )

        self.assertEqual(metadata["spad_number_of_channels"], "25")
        self.assertEqual(metadata["spadCmdLength"], "25")
        self.assertEqual(metadata["spadCmdData"], "33554431")
        self.assertFalse(metadata["spadCmdInvert"])
        self.assertNotIn("detector_model", metadata)
        self.assertNotIn("spad_channels", metadata)
        self.assertNotIn("spad_cmd_length", metadata)

    def test_gui_config_for_h5_keeps_non_spad_detector_model(self):
        metadata = MainWindow._gui_config_for_h5({"detector_model": "PI 23"})

        self.assertEqual(metadata["detector_model"], "PI 23")


if __name__ == "__main__":
    unittest.main()
