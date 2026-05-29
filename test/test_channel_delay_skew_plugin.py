import os
import sys
import tempfile
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(1, os.getcwd())

import h5py
import numpy as np
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QComboBox

from brighteyes_mcs.plugins.channel_delay_skew import channel_delay_skew_extractor
from brighteyes_mcs.plugins.channel_delay_skew.channel_delay_skew_widget import (
    ChannelDelaySkewWidget,
    TWENTY_FIVE_TO_FORTY_NINE,
)


class DummyMainWindow:
    def __init__(self):
        self.plugin_configuration = {}
        self.ui = SimpleNamespace()
        self.ui.comboBox_channels = QComboBox()
        self.ui.comboBox_channels.addItems(["25", "49"])
        self.ui.comboBox_channels.setCurrentText("25")


class TestChannelDelaySkewWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.main_window = DummyMainWindow()
        self.widget = ChannelDelaySkewWidget(main_window=self.main_window)

    def _wait_for_analysis(self, timeout_ms=3000):
        if not self.widget.analysis_lock:
            return
        loop = QEventLoop()
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        check = QTimer()
        check.timeout.connect(lambda: (not self.widget.analysis_lock) and loop.quit())
        deadline.start(timeout_ms)
        check.start(10)
        while self.widget.analysis_lock and deadline.isActive():
            loop.exec()
        check.stop()
        self.assertFalse(self.widget.analysis_lock)

    def test_exports_25_and_49_arrays_with_expected_mapping(self):
        table = self.widget.get_delay_skew_table_numpy()
        table[:49, 2] = np.arange(49, dtype=float)
        self.widget.table_skew.set_data(table)

        np.testing.assert_array_equal(
            self.widget.get_channel_delay_skew_array(49),
            np.arange(49, dtype=float),
        )
        np.testing.assert_array_equal(
            self.widget.get_channel_delay_skew_array(25),
            np.arange(49, dtype=float)[TWENTY_FIVE_TO_FORTY_NINE],
        )

    def test_table_numpy_and_reference_configuration(self):
        table = self.widget.get_delay_skew_table()
        table[:49, 2] = np.arange(49, dtype=float)
        table[:49, 3] = np.linspace(0.1, 4.9, 49)
        table[49, 2] = 1.5
        table[49, 3] = 0.15
        table[50, 2] = -2.5
        table[50, 3] = 0.25
        self.widget.table_skew.set_data(table)
        table = self.widget.get_delay_skew_table()

        self.assertEqual(table.shape, (51, 4))
        self.assertTrue(np.isnan(table[0, 1]))
        self.assertEqual(table[8, 1], 0.0)
        self.assertEqual(table[49, 2], 1.5)
        self.assertEqual(table[49, 3], 0.15)
        self.assertEqual(table[50, 2], -2.5)
        self.assertEqual(table[50, 3], 0.25)

        self.assertEqual(
            self.widget.get_reference_channel_used_for_time_skew(25),
            {"source": "data", "index": 12},
        )
        self.assertEqual(
            self.widget.get_reference_channel_used_for_time_skew(49),
            {"source": "data", "index": 24},
        )

        self.widget.comboBox_reference_source.setCurrentText("data_channel_extra")
        self.widget.spinBox_reference_channel.setValue(1)

        self.assertEqual(
            self.widget.get_reference_channel_used_for_time_skew(25),
            {"source": "data_channel_extra", "index": 1},
        )
        self.assertEqual(
            self.main_window.plugin_configuration["channel_delay_skew"][
                "reference_data_channel_extra_index"
            ],
            1,
        )

    def test_extractor_uses_central_reference_by_default(self):
        data = np.ones((32, 5), dtype=float)
        _shift, _err, meta = channel_delay_skew_extractor.estimate_channel_skew(data)
        self.assertEqual(meta["reference_channel_resolved"], 2)

    def test_estimate_updates_extra_rows_from_h5_file(self):
        time_bins = 64
        x = np.arange(time_bins, dtype=float)
        base = np.exp(-0.5 * ((x - 15.0) / 3.0) ** 2)
        extra = np.stack([base, np.roll(base, 3)], axis=1)

        with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
            filename = tmp.name

        try:
            with h5py.File(filename, "w") as hf:
                hf["data"] = np.zeros((1, 1, 1, 1, time_bins, 25), dtype=float)
                hf["data_channels_extra"] = extra.reshape(1, 1, 1, 1, time_bins, 2)

            self.widget.comboBox_reference_source.setCurrentText("data_channel_extra")
            self.widget.spinBox_reference_channel.setValue(0)
            self.widget.lineEdit_data_file.setText(filename)
            self.widget.pushButton_estimate_clicked()
            self._wait_for_analysis()

            table = self.widget.get_delay_skew_table_numpy()
            self.assertAlmostEqual(table[49, 2], 0.0, places=1)
            self.assertGreater(abs(table[50, 2]), 1.0)
            self.assertFalse(np.isnan(table[49, 3]))
            self.assertFalse(np.isnan(table[50, 3]))
        finally:
            if os.path.exists(filename):
                os.remove(filename)


if __name__ == "__main__":
    unittest.main()
