import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from brighteyes_mcs.application.paths import SystemProfile
from brighteyes_mcs.ui.qt.first_run import ShortcutSetupDialog


class TestFirstRunWizard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_wizard_has_sequential_pages_and_default_options(self):
        with tempfile.TemporaryDirectory() as appdata:
            with patch.dict(os.environ, {"APPDATA": appdata}, clear=False):
                wizard = ShortcutSetupDialog()

        titles = [wizard.page(page_id).title() for page_id in wizard.pageIds()]
        self.assertEqual(
            titles,
            [
                "Welcome to BrightEyes-MCS",
                "Microscope system profile",
                "Folder and configuration structure",
                "FPGA firmware",
                "Desktop shortcuts",
                "Ready to finish",
            ],
        )
        self.assertFalse(wizard.firmware_page.download_checkbox.isChecked())
        welcome_text = " ".join(
            label.text()
            for label in wizard.welcome_page.findChildren(QLabel)
        )
        self.assertIn("image-scanning microscopes", welcome_text)
        self.assertIn("GNU General Public License", welcome_text)
        self.assertIn("ABSOLUTELY NO WARRANTY", welcome_text)
        self.assertIn("LICENSE.md", welcome_text)
        self.assertEqual(wizard.firmware_page.branch.text(), "main")
        self.assertFalse(wizard.firmware_page.progress.isVisible())
        self.assertFalse(wizard.firmware_page.license_checkbox.isEnabled())
        self.assertEqual(
            wizard.shortcuts_page.application.isChecked(),
            os.name == "nt",
        )
        self.assertEqual(
            wizard.shortcuts_page.python_prompt.isChecked(),
            os.name == "nt",
        )
        self.assertEqual(
            wizard.shortcuts_page.system_root.isChecked(),
            os.name == "nt",
        )
        wizard.close()

    def test_firmware_download_is_embedded_and_requires_inline_license_acceptance(self):
        with tempfile.TemporaryDirectory() as appdata, patch.dict(
            os.environ,
            {"APPDATA": appdata},
            clear=False,
        ):
            wizard = ShortcutSetupDialog()
            page = wizard.firmware_page
            page.download_checkbox.setChecked(True)

            self.assertTrue(page.branch.isEnabled())
            self.assertTrue(page.license_checkbox.isEnabled())
            self.assertTrue(page.download_button.isEnabled())
            self.assertFalse(page.validatePage())
            self.assertIn("Accept the separate", page.status.text())
            self.assertFalse(page.is_downloading)
            wizard.close()

    def test_embedded_firmware_worker_reports_success_without_another_dialog(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {"APPDATA": str(Path(temporary) / "appdata")},
            clear=False,
        ), patch(
            "brighteyes_mcs.ui.qt.first_run.download_firmware",
            return_value=[Path(temporary) / "firmware/device.lvbitx"],
        ):
            root = Path(temporary) / "microscope"
            wizard = ShortcutSetupDialog()
            wizard.profile_page.editor.set_profile(SystemProfile(root=str(root)))
            page = wizard.firmware_page
            page.download_checkbox.setChecked(True)
            page.license_checkbox.setChecked(True)

            page.start_download()
            thread = page._thread
            deadline = time.monotonic() + 5
            while thread.isRunning() and time.monotonic() < deadline:
                QApplication.processEvents()
                time.sleep(0.01)
            QApplication.processEvents()

            self.assertFalse(page.is_downloading)
            self.assertTrue(page._download_succeeded)
            self.assertIn("Firmware ready", page.status.text())
            self.assertEqual(page.progress.value(), page.progress.maximum())
            wizard.close()

    def test_missing_selected_structure_is_suggested_and_created(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {"APPDATA": str(Path(temporary) / "appdata")},
            clear=False,
        ):
            root = Path(temporary) / "new microscope"
            wizard = ShortcutSetupDialog()
            wizard.profile_page.editor.set_profile(
                SystemProfile(
                    root=str(root),
                    configuration_dir="cfg",
                    default_configuration="default.cfg",
                    plugins_dir="cfg/plugins_cfg",
                    scripts_dir="scripts",
                    bitfiles_dir="firmware",
                )
            )

            wizard.structure_page.initializePage()

            self.assertTrue(wizard.structure_page.create_missing.isChecked())
            self.assertIn("does not yet contain", wizard.structure_page.status.text())
            self.assertIn(str(root), wizard.structure_page.status.text())
            self.assertTrue(wizard.structure_page.validatePage())
            self.assertTrue((root / "cfg/default.cfg").is_file())
            self.assertTrue((root / "cfg/plugins_cfg").is_dir())
            self.assertTrue((root / "scripts").is_dir())
            self.assertTrue((root / "firmware").is_dir())
            wizard.close()


if __name__ == "__main__":
    unittest.main()
