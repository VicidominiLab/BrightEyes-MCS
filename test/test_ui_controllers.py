import unittest
from types import SimpleNamespace

from brighteyes_mcs.ui.controllers import ConfigurationController, LifecycleController


class TestLifecycleController(unittest.TestCase):
    def test_status_shape_remains_rest_compatible(self):
        window = SimpleNamespace(
            PROGRAM_STATES=("idle", "preview"), program_state="idle",
            program_state_reason="startup", program_state_changed_at="now",
            started_normal=False, started_preview=False, do_not_save=False,
            last_requested_filename=None, last_saved_filename=None,
            last_completed_filename=None, acquisition_run_id=0, preview_run_id=0,
            completed_acquisition_count=0, last_acquisition_started_at=None,
            last_preview_started_at=None, last_acquisition_completed_at=None,
            http_server_thread=None,
        )
        payload = LifecycleController().full_status_payload(window)
        self.assertEqual(payload["program_state"], "idle")
        self.assertFalse(payload["acquisition_running"])
        self.assertIn("last_saved_filename", payload)


class TestConfigurationController(unittest.TestCase):
    def test_save_merge_preserves_unknown_root_and_plugin_keys(self):
        merged = ConfigurationController.merge_for_save(
            {
                "nx": 100,
                "future_key": {"value": 1},
                "plugins": {"autoload": ["old"], "future_plugin_option": True},
            },
            {"nx": 200, "plugins": {"autoload": ["new"]}},
        )
        self.assertEqual(merged["nx"], 200)
        self.assertEqual(merged["future_key"], {"value": 1})
        self.assertEqual(merged["plugins"]["autoload"], ["new"])
        self.assertTrue(merged["plugins"]["future_plugin_option"])


if __name__ == "__main__":
    unittest.main()
