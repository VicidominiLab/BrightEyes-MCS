import importlib
import multiprocessing as mp
import queue
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np

from brighteyes_mcs.acquisition.detectors.backends import DETECTOR_PI_23
from brighteyes_mcs.storage.converters.spad import (
    _detect_streams,
    _load_metadata,
    convert_raw_acquisition,
)
from brighteyes_mcs.acquisition.workers.detectors.spad.raw_writer import (
    SpadRawStreamWriterProcess,
)
from brighteyes_mcs.acquisition.manager import create_i64_counter


class TestRawStreamLargeCounters(unittest.TestCase):
    def test_i64_counter_keeps_values_above_u32(self):
        counter = create_i64_counter(2**32 + 10)

        counter.value += 100

        self.assertEqual(counter.value, 2**32 + 110)

    def test_manager_i64_counter_keeps_values_above_u32(self):
        with mp.Manager() as manager:
            counter = manager.Value("q", 2**32 + 10)

            counter.value += 100

            self.assertEqual(counter.value, 2**32 + 110)

    def test_raw_writer_progress_uses_i64_word_counters(self):
        loc_acquired = {
            "stream_out_main": create_i64_counter(2**32 + 5),
            "stream_out_aux": create_i64_counter(),
        }
        loc_previewed = {
            "stream_out_main": create_i64_counter(),
            "stream_out_aux": create_i64_counter(),
        }
        last_preprocessed_len = {
            "stream_out_main": create_i64_counter(),
            "stream_out_aux": create_i64_counter(),
        }
        shared_dict = {
            "expected_words_data_digital": 2**32 + 1000,
            "expected_words_data_analog": 0,
            "expected_words_data_per_frame_digital": 100,
            "expected_words_data_per_frame_analog": 0,
            "shape": [1, 1, 1],
        }
        writer = SpadRawStreamWriterProcess(
            queue.Queue(),
            ["stream_out_main"],
            {"stream_out_main": "unused.raw"},
            loc_acquired,
            loc_previewed,
            last_preprocessed_len,
            acquisition_done=types.SimpleNamespace(clear=lambda: None, set=lambda: None),
            acquisition_almost_done=types.SimpleNamespace(clear=lambda: None, set=lambda: None),
            shared_dict=shared_dict,
        )

        writer._update_progress("stream_out_main", 123, 123 * 8)

        self.assertEqual(loc_acquired["stream_out_main"].value, 2**32 + 128)
        self.assertEqual(loc_previewed["stream_out_main"].value, 2**32 + 128)
        self.assertEqual(last_preprocessed_len["stream_out_main"].value, 123)
        self.assertEqual(shared_dict["stream_out_main_bytes_written"], 123 * 8)
        self.assertEqual(shared_dict["last_packet_size"], 123)

    def test_raw_writer_expected_bytes_are_uint64_words(self):
        shared_dict = {
            "expected_words_data_digital": 2**32 + 1,
            "expected_words_data_analog": 0,
            "expected_words_data_per_frame_digital": 1,
            "expected_words_data_per_frame_analog": 0,
            "shape": [1, 1, 1],
        }
        writer = SpadRawStreamWriterProcess(
            queue.Queue(),
            ["stream_out_main"],
            {"stream_out_main": "unused.raw"},
            {"stream_out_main": create_i64_counter(), "stream_out_aux": create_i64_counter()},
            {"stream_out_main": create_i64_counter(), "stream_out_aux": create_i64_counter()},
            {"stream_out_main": create_i64_counter(), "stream_out_aux": create_i64_counter()},
            acquisition_done=types.SimpleNamespace(clear=lambda: None, set=lambda: None),
            acquisition_almost_done=types.SimpleNamespace(clear=lambda: None, set=lambda: None),
            shared_dict=shared_dict,
        )

        self.assertEqual(writer._expected_bytes("stream_out_main"), (2**32 + 1) * 8)


class TestRustFifoReaderConfiguration(unittest.TestCase):
    def test_rust_fifo_reader_uses_per_fifo_min_packet(self):
        captured = []

        class FakeBitfile:
            signature = "SIG"
            fifos = {"stream_out_main": object(), "stream_out_aux": object()}

            def __init__(self, _bitfile):
                pass

        class FakeFastFifoRecv:
            def __init__(self, *args, **kwargs):
                captured.append(kwargs)

            def get_conf(self):
                return {}

            def thread_start(self):
                pass

        fake_nifpga = types.SimpleNamespace(Bitfile=FakeBitfile)
        fake_recv = types.SimpleNamespace(NifpgaFastFifoRecv=FakeFastFifoRecv)

        with patch.dict(
            sys.modules,
            {"nifpga": fake_nifpga, "nifpga_fast_fifo_recv": fake_recv},
        ):
            sys.modules.pop("brighteyes_mcs.acquisition.fifo", None)
            module = importlib.import_module("brighteyes_mcs.acquisition.fifo")
            module.RustFastFifoReader(
                "bitfile.lvbitx",
                ["stream_out_main", "stream_out_aux"],
                chunk_digital=16,
                chunk_analog=32,
                requested_fifo_depth=1000,
            )

        min_packets = [item["min_packet"] for item in captured]
        self.assertEqual(min_packets, [16, 32])


class TestRawMetadataCompatibility(unittest.TestCase):
    def test_raw_converter_reads_legacy_h5_metadata_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            metadata_filename = folder / "acquisition_only_metadata.h5"
            raw_filename = folder / "acquisition_FIFO.raw"
            np.zeros(2, dtype=np.uint64).tofile(raw_filename)

            with h5py.File(metadata_filename, "w") as h5file:
                mcs_cfg = h5file.create_group("configurationSpadFCSmanager")
                mcs_cfg.attrs["#pixels"] = 1
                mcs_cfg.attrs["#lines"] = 1
                mcs_cfg.attrs["#frames"] = 1
                mcs_cfg.attrs["#repetition"] = 2
                mcs_cfg.attrs["#timebinsPerPixel"] = 1
                mcs_cfg.attrs["#circular_rep"] = 1
                mcs_cfg.attrs["#circular_points"] = 1
                mcs_cfg.attrs["Cx"] = 40

                h5file.create_group("configurationFPGA")

                gui_cfg = h5file.create_group("configurationGUI")
                gui_cfg.attrs["spad_number_of_channels"] = 25

                raw_cfg = h5file.create_group("rawStreamAcquisition")
                raw_cfg.attrs["digital_raw_file"] = str(raw_filename)
                raw_cfg.attrs["digital_channels"] = 25
                raw_cfg.attrs["digital_words_per_sample"] = 2

            meta = _load_metadata(metadata_filename)
            streams = _detect_streams(metadata_filename, meta)

            self.assertEqual(meta["spad_channels_hint"], 25)
            self.assertEqual(streams[0]["spad_channels"], 25)

    def test_raw_converter_dispatches_pi23_metadata_to_pi23_converter(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            metadata_filename = folder / "pi23_only_metadata.h5"

            with h5py.File(metadata_filename, "w") as h5file:
                mcs_cfg = h5file.create_group("configurationSpadFCSmanager")
                mcs_cfg.attrs["#pixels"] = 1
                mcs_cfg.attrs["#lines"] = 1
                mcs_cfg.attrs["#frames"] = 1
                mcs_cfg.attrs["#repetition"] = 2
                mcs_cfg.attrs["#timebinsPerPixel"] = 1
                mcs_cfg.attrs["#circular_rep"] = 1
                mcs_cfg.attrs["#circular_points"] = 1
                mcs_cfg.attrs["Cx"] = 40

                h5file.create_group("configurationFPGA")
                h5file.create_group("configurationGUI")

                raw_cfg = h5file.create_group("rawStreamAcquisition")
                raw_cfg.attrs["detector_model"] = DETECTOR_PI_23

            meta = _load_metadata(metadata_filename)
            self.assertEqual(meta["detector_model"], DETECTOR_PI_23)
            with self.assertRaises(NotImplementedError):
                convert_raw_acquisition(metadata_filename)


if __name__ == "__main__":
    unittest.main()
