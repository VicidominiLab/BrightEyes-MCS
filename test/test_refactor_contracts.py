import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import h5py
import numpy as np

from brighteyes_mcs.application.contracts import DetectorPipeline
from brighteyes_mcs.application.paths import ensure_user_configuration, user_config_dir
from brighteyes_mcs.acquisition.detectors import create_detector_pipeline
from brighteyes_mcs.storage.h5 import H5Manager
from brighteyes_mcs.storage.legacy_config import LegacyConfigurationCodec, LegacyConfigurationTranslator
from brighteyes_mcs.storage.h5_schema import (
    DATA_FORMAT_VERSION,
    describe_h5,
    legacy_raw_stream_metadata,
)
from brighteyes_mcs.storage.legacy_names import (
    LEGACY_H5_FIFO_NAME_MAP,
    LEGACY_H5_REGISTER_NAME_MAP,
    translate_metadata_names,
)
from brighteyes_mcs.storage.raw import metadata_filename, raw_output_files


ROOT = Path(__file__).resolve().parents[1]


class TestLegacyConfigurationContract(unittest.TestCase):
    def test_tracked_configs_round_trip_without_losing_unknown_keys(self):
        config_files = sorted((ROOT / "brighteyes_mcs" / "cfg").rglob("*.cfg"))
        self.assertTrue(config_files)
        for filename in config_files:
            with self.subTest(filename=filename):
                payload = LegacyConfigurationCodec.load(filename)
                self.assertEqual(
                    LegacyConfigurationCodec.loads(LegacyConfigurationCodec.dumps(payload)),
                    payload,
                )

    def test_typed_translation_preserves_unknown_keys_and_plugins(self):
        payload = LegacyConfigurationCodec.load(ROOT / "brighteyes_mcs" / "cfg" / "default.cfg")
        payload["future_key"] = {"nested": [1, 2, 3]}
        restored = LegacyConfigurationTranslator.to_legacy(
            LegacyConfigurationTranslator.from_legacy(payload)
        )
        self.assertEqual(restored["future_key"], payload["future_key"])
        self.assertEqual(restored["plugins"], payload["plugins"])
        self.assertEqual(restored["spad_channels"], payload["spad_channels"])

    def test_first_run_copies_legacy_schema_to_user_owned_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"APPDATA": folder}):
            selected = ensure_user_configuration()
            self.assertEqual(selected.parent, user_config_dir())
            payload = LegacyConfigurationCodec.load(selected)
            self.assertEqual(
                LegacyConfigurationCodec.loads(LegacyConfigurationCodec.dumps(payload)), payload
            )
            self.assertTrue((user_config_dir() / "current_system").exists())


class TestAcquisitionFormatContract(unittest.TestCase):
    def test_all_v1_firmware_names_translate_only_at_the_h5_boundary(self):
        runtime_registers = {
            name: index for index, name in enumerate(LEGACY_H5_REGISTER_NAME_MAP)
        }

        translated = translate_metadata_names(
            runtime_registers, LEGACY_H5_REGISTER_NAME_MAP
        )

        self.assertEqual(set(translated), set(LEGACY_H5_REGISTER_NAME_MAP.values()))
        self.assertEqual(len(translated), 179)
        self.assertEqual(
            translate_metadata_names(
                {"stream_out_main": True}, LEGACY_H5_FIFO_NAME_MAP
            ),
            {"FIFO": True},
        )
        self.assertEqual(
            translate_metadata_names({"max_pixel": 10}, None),
            {"max_pixel": 10},
        )

    def test_raw_stream_metadata_keeps_legacy_public_keys(self):
        acquisition = SimpleNamespace(
            registers_configuration={
                "max_time_bins_per_pixel": 2,
                "max_circular_repetition": 3,
                "max_circular_point": 4,
            },
            shared_dict={
                "stream_out_main_bytes_written": 100,
                "pi23_raw_stream_format": "pi23-v1",
            },
            activated_fifos_list=["stream_out_main"],
            clk_multiplier=2,
            dfd_shift=1,
            snake_walk_xy=True,
            snake_walk_z=False,
            dfd_enable=True,
            detector_model="PI 23",
        )

        metadata = legacy_raw_stream_metadata(
            acquisition,
            spad_channels=25,
            clock_base_mhz=40,
            raw_files={"stream_out_main": "scan_FIFO.raw"},
            include_pi23=True,
        )

        self.assertEqual(metadata["effective_timebins_per_pixel"], 24)
        self.assertEqual(metadata["digital_words_per_sample"], 2)
        self.assertEqual(metadata["digital_raw_bytes"], 100)
        self.assertEqual(metadata["detector_model"], "PI 23")
        self.assertEqual(metadata["pi23_raw_stream_format"], "pi23-v1")
        self.assertEqual(metadata["analog_raw_bytes"], 0)

    def test_raw_filenames_remain_legacy_compatible(self):
        metadata = metadata_filename("C:/data/scan.h5")
        self.assertEqual(metadata, "C:/data/scan_only_metadata.h5")
        self.assertEqual(
            raw_output_files(metadata, digital=True, analog=True),
            {
                "stream_out_main": "C:/data/scan_FIFO.raw",
                "stream_out_aux": "C:/data/scan_FIFOAnalog.raw",
            },
        )

    def test_h5_manager_writes_legacy_v001_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / "contract.h5"
            manager = H5Manager(filename)
            manager.init_dataset("data", [2, 3, 1], 4, 5, np.uint16)
            manager.metadata_add_initial("contract")
            manager.metadata_add_dict(
                "configurationSpadFCSmanager",
                {"max_pixel": 2},
                legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP,
            )
            manager.metadata_add_dict(
                "configurationFPGA",
                {"start_command": False},
                legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP,
            )
            manager.metadata_add_dict("configurationGUI", {"spad_number_of_channels": "25"})
            manager.metadata_add_dict("configurationGUI_beforeStart", {"nx": 2})
            manager.close()

            with h5py.File(filename, "r") as h5file:
                schema = describe_h5(h5file)

            self.assertEqual(schema["root_attributes"]["data_format_version"], DATA_FORMAT_VERSION)
            self.assertEqual(schema["objects"]["data"]["shape"], (1, 1, 3, 2, 4, 5))
            self.assertEqual(schema["objects"]["data"]["dtype"], "uint16")
            self.assertEqual(
                schema["objects"]["configurationSpadFCSmanager"]["attributes"]["#pixels"],
                2,
            )
            self.assertFalse(
                schema["objects"]["configurationFPGA"]["attributes"]["Run"]
            )
            self.assertEqual(
                set(schema["objects"]),
                {"data", "configurationSpadFCSmanager", "configurationFPGA", "configurationGUI", "configurationGUI_beforeStart"},
            )


class TestDetectorPipelineContract(unittest.TestCase):
    def test_all_detector_pipelines_satisfy_shared_protocol(self):
        for model in ("SPAD Array", "SPAD_TTM", "PI 23", "PI23TT"):
            with self.subTest(model=model):
                self.assertIsInstance(create_detector_pipeline(model), DetectorPipeline)


if __name__ == "__main__":
    unittest.main()
