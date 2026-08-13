import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brighteyes_mcs.application.paths import (
    SystemProfile,
    current_system_path,
    default_configuration_path,
    expand_environment_variables,
    generate_system_configuration,
    load_system_profile,
    profile_directory,
    resolve_legacy_path,
    system_root,
    writable_config_path,
    write_default_pointer,
    write_system_profile,
)


class TestSystemProfilePaths(unittest.TestCase):
    def _profile_tree(self, base: Path) -> tuple[Path, SystemProfile]:
        root = base / "microscope-1"
        for relative in ("configurations", "settings/plugins", "automation", "firmware"):
            (root / relative).mkdir(parents=True, exist_ok=True)
        (root / "configurations/main.cfg").write_text("{}", encoding="utf-8")
        (root / "configurations/secondary.cfg").write_text("{}", encoding="utf-8")
        (root / "settings/plugins/dfd.cfg").write_text("{}", encoding="utf-8")
        (root / "automation/calibrate.py").write_text("pass", encoding="utf-8")
        (root / "firmware/device.lvbitx").write_text("firmware", encoding="utf-8")
        return root, SystemProfile(
            root="%PROFILE_ROOT%",
            configuration_dir="configurations",
            default_configuration="main.cfg",
            plugins_dir="settings/plugins",
            scripts_dir="${PROFILE_ROOT}/automation",
            bitfiles_dir="$PROFILE_ROOT/firmware",
        )

    def test_profile_round_trip_and_custom_subfolders(self):
        with tempfile.TemporaryDirectory() as appdata, tempfile.TemporaryDirectory() as shared:
            root, profile = self._profile_tree(Path(shared))
            with patch.dict(
                os.environ,
                {"APPDATA": appdata, "PROFILE_ROOT": str(root)},
                clear=False,
            ):
                pointer = write_system_profile(profile)
                self.assertEqual(pointer, Path(appdata) / "BrightEyes-MCS/current_system")
                self.assertEqual(load_system_profile(), profile)
                self.assertEqual(system_root(), root)
                self.assertEqual(default_configuration_path(), root / "configurations/main.cfg")
                self.assertEqual(profile_directory("scripts"), root / "automation")
                self.assertEqual(profile_directory("bitfiles"), root / "firmware")
                self.assertEqual(
                    writable_config_path("cfg/plugins_cfg/dfd.cfg"),
                    root / "settings/plugins/dfd.cfg",
                )

    def test_aliases_resolve_all_profile_resource_folders(self):
        with tempfile.TemporaryDirectory() as appdata, tempfile.TemporaryDirectory() as shared:
            root, profile = self._profile_tree(Path(shared))
            with patch.dict(
                os.environ,
                {"APPDATA": appdata, "PROFILE_ROOT": str(root)},
                clear=False,
            ):
                write_system_profile(profile)
                self.assertEqual(
                    resolve_legacy_path("cfg/secondary.cfg"),
                    root / "configurations/secondary.cfg",
                )
                self.assertEqual(
                    resolve_legacy_path("scripts/calibrate.py"),
                    root / "automation/calibrate.py",
                )
                self.assertEqual(
                    resolve_legacy_path("bitfiles/device.lvbitx"),
                    root / "firmware/device.lvbitx",
                )

    def test_legacy_cfg_pointer_remains_supported(self):
        with tempfile.TemporaryDirectory() as appdata, tempfile.TemporaryDirectory() as shared:
            root, _profile = self._profile_tree(Path(shared))
            with patch.dict(
                os.environ,
                {"APPDATA": appdata, "PROFILE_ROOT": str(root)},
                clear=False,
            ):
                pointer = current_system_path()
                pointer.parent.mkdir(parents=True)
                pointer.write_text(
                    "# legacy active configuration\n"
                    "%PROFILE_ROOT%\\configurations\\secondary.cfg\n",
                    encoding="utf-8",
                )
                profile = load_system_profile()
                self.assertEqual(system_root(profile), root / "configurations")
                self.assertEqual(profile.default_configuration, "secondary.cfg")
                self.assertEqual(default_configuration_path(profile), root / "configurations/secondary.cfg")

    def test_changing_default_preserves_profile_folders(self):
        with tempfile.TemporaryDirectory() as appdata, tempfile.TemporaryDirectory() as shared:
            root, profile = self._profile_tree(Path(shared))
            with patch.dict(
                os.environ,
                {"APPDATA": appdata, "PROFILE_ROOT": str(root)},
                clear=False,
            ):
                write_system_profile(profile)
                write_default_pointer(root / "configurations/secondary.cfg")
                updated = load_system_profile()
                self.assertEqual(updated.root, profile.root)
                self.assertEqual(updated.plugins_dir, profile.plugins_dir)
                self.assertEqual(updated.scripts_dir, profile.scripts_dir)
                self.assertEqual(updated.bitfiles_dir, profile.bitfiles_dir)
                self.assertEqual(updated.default_configuration, "secondary.cfg")

    def test_environment_expansion_supports_windows_and_unix_notation(self):
        with patch.dict(os.environ, {"BRIGHTEYES_TEST_ROOT": "example-root"}, clear=False):
            self.assertEqual(
                expand_environment_variables("%BRIGHTEYES_TEST_ROOT%/cfg"),
                os.path.expanduser("example-root/cfg"),
            )
            self.assertEqual(
                expand_environment_variables("${BRIGHTEYES_TEST_ROOT}/cfg"),
                os.path.expanduser("example-root/cfg"),
            )

    def test_generate_system_configuration_creates_custom_profile_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "shared" / "microscope-2"
            profile = SystemProfile(
                root=str(root),
                configuration_dir="configurations",
                default_configuration="startup/default.cfg",
                plugins_dir="settings/plugins",
                scripts_dir="automation",
                bitfiles_dir="firmware",
            )
            copied = generate_system_configuration(profile)

            self.assertIn(root / "configurations/startup/default.cfg", copied)
            self.assertTrue((root / "configurations/startup/default.cfg").is_file())
            self.assertTrue((root / "settings/plugins").is_dir())
            self.assertTrue((root / "automation").is_dir())
            self.assertTrue((root / "firmware").is_dir())

            default = root / "configurations/startup/default.cfg"
            default.write_text("preserve me", encoding="utf-8")
            generate_system_configuration(profile)
            self.assertEqual(default.read_text(encoding="utf-8"), "preserve me")


if __name__ == "__main__":
    unittest.main()
