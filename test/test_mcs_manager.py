import os
import sys
# insert root directory into python module search path
sys.path.insert(1, os.getcwd())

import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from brighteyes_mcs.libs.mcs_manager import McsManager

class TestMcsManager(unittest.TestCase):

    def test_parse_dfd_metadata_from_bitfile_name_extracts_values(self):
        cycle_mhz, dfd_nbins = McsManager.parse_dfd_metadata_from_bitfile_name(
            "bitfiles/SingleBoard-Digital-PCIe7820R-49CH-40M91.lvbitx"
        )

        self.assertEqual(cycle_mhz, 40)
        self.assertEqual(dfd_nbins, 91)

    def test_parse_dfd_metadata_from_bitfile_name_extracts_nondefault_cycle(self):
        cycle_mhz, dfd_nbins = McsManager.parse_dfd_metadata_from_bitfile_name(
            "bfdades/SgfgsBogsfgsd-Dgsfgital-Pfeqrqe7qre0R-25CH-37M71.lvbitx"
        )

        self.assertEqual(cycle_mhz, 37)
        self.assertEqual(dfd_nbins, 71)

    def test_acquisition_run_sets_acquisition_run_event(self):
        instance = McsManager()
        instance.acquisition_run_event.set = MagicMock()
        instance.acquisition_stop_event.clear = MagicMock()

        instance.acquisition_run()

        instance.acquisition_run_event.set.assert_called()
        instance.acquisition_stop_event.clear.assert_called()

    def test_acquisition_stop_sets_acquisition_stop_event(self):
        instance = McsManager()
        instance.acquisition_stop_event.set = MagicMock()
        instance.acquisition_run_event.clear = MagicMock()

        instance.acquisition_stop()

        instance.acquisition_stop_event.set.assert_called()
        instance.acquisition_run_event.clear.assert_called()

    def test_acquisition_is_done_returns_true_if_done(self):
        instance = McsManager()
        instance.acquisition_done_event.is_set = MagicMock(return_value=True)

        result = instance.acquisition_is_done()

        self.assertTrue(result)

    def test_acquisition_is_almost_done_returns_true_if_almost_done(self):
        instance = McsManager()
        instance.acquisition_almost_done_event.is_set = MagicMock(return_value=True)

        result = instance.acquisition_is_almost_done()

        self.assertTrue(result)

    def test_set_do_not_save_sets_event(self):
        instance = McsManager()
        instance.do_not_save_event.set = MagicMock()
        instance.do_not_save_event.clear = MagicMock()

        instance.set_do_not_save(True)
        instance.do_not_save_event.set.assert_called()

        instance.set_do_not_save(False)
        instance.do_not_save_event.clear.assert_called()

    def test_set_activate_DFD_sets_DFD_Activate(self):
        instance = McsManager()

        instance.set_activate_DFD(True)
        self.assertTrue(instance.DFD_Activate)

        instance.set_activate_DFD(False)
        self.assertFalse(instance.DFD_Activate)

    def test_set_activate_snake_walk_xy_sets_snake_walk_xy(self):
        instance = McsManager()

        instance.set_activate_snake_walk_xy(True)
        self.assertTrue(instance.snake_walk_xy)

        instance.set_activate_snake_walk_xy(False)
        self.assertFalse(instance.snake_walk_xy)

    def test_set_activate_snake_walk_z_sets_snake_walk_z(self):
        instance = McsManager()

        instance.set_activate_snake_walk_z(True)
        self.assertTrue(instance.snake_walk_z)

        instance.set_activate_snake_walk_z(False)
        self.assertFalse(instance.snake_walk_z)

    def test_connect_sets_is_connected(self):
        instance = McsManager()
        instance.fpga_handle = MagicMock()
        instance.fpga_handle.run = MagicMock()
        instance.update_chuck = MagicMock()

        with patch("brighteyes_mcs.libs.mcs_manager.FpgaHandle") as MockFpgaHandle:
            MockFpgaHandle.return_value = MagicMock()
            instance.connect()

            self.assertTrue(instance.is_connected)
            instance.fpga_handle.run.assert_called()
            instance.update_chuck.assert_called()

    def test_connect_raises_exception_on_error(self):
        instance = McsManager()
        with patch("brighteyes_mcs.libs.mcs_manager.FpgaHandle") as MockFpgaHandle:
            MockFpgaHandle.return_value = MagicMock()
            MockFpgaHandle.return_value.run = MagicMock(side_effect=Exception("Error"))

            with self.assertRaises(Exception):
                instance.connect()

    def test_run_starts_dataProcess_and_previewProcess(self):
        instance = McsManager()
        instance.fpga_handle = MagicMock()
        instance.readRegistersDict = MagicMock()
        instance.dataProcess = MagicMock()
        instance.previewProcess = MagicMock()
        instance.do_not_save_event.is_set = MagicMock(return_value=True)

        with patch("brighteyes_mcs.libs.mcs_manager.DataPreProcess") as MockDataPreProcess, patch(
            "brighteyes_mcs.libs.mcs_manager.AcquisitionLoopProcess"
        ) as MockAcquisitionLoopProcess:
            MockDataPreProcess.return_value = instance.dataProcess
            MockAcquisitionLoopProcess.return_value = instance.previewProcess

            instance.run()

        instance.dataProcess.start.assert_called()
        instance.previewProcess.start.assert_called()

    def test_stopAcquisition_stops_dataProcess(self):
        instance = McsManager()
        instance.dataProcess = MagicMock()

        instance.stopAcquisition()

        instance.dataProcess.stop.assert_called()

    def test_stopPreview_stops_previewProcess(self):
        instance = McsManager()
        instance.previewProcess = MagicMock()

        instance.stopPreview()

        instance.previewProcess.stop.assert_called()
        instance.previewProcess.join.assert_called()

    def test_getPreviewImage_returns_correct_array(self):
        instance = McsManager()
        instance.shared_image_xy = MagicMock()
        instance.shared_image_xy.get_numpy_handle = MagicMock(return_value=np.array([[1, 2], [3, 4]]))
        instance.shared_image_xy.get_lock = MagicMock()

        result = instance.getPreviewImage()

        self.assertTrue((result == np.array([[1, 2], [3, 4]])).all())

    def test_getTrace_in_dfd_mode_returns_counts_per_second(self):
        with patch("brighteyes_mcs.libs.mcs_manager.mp.Manager", return_value=MagicMock()):
            instance = McsManager()
        instance.DFD_Activate = True
        instance.time_resolution = 2.0
        instance.clk_multiplier = 2
        instance.timebins_per_pixel = 8
        instance.trace_sample_per_bins = 5
        instance.expected_words_data_per_frame_digital = 80
        instance.trace_pos = MagicMock(value=0)
        instance.loc_previewed = {"FIFO": MagicMock(value=10)}
        instance.shared_trace = MagicMock()
        instance.shared_trace.get_numpy_handle = MagicMock(
            return_value=np.array(
                [
                    [0.0, 1.0, 2.0, 3.0],
                    [10.0, 20.0, 30.0, 40.0],
                ]
            )
        )
        instance.shared_trace_dfd = MagicMock()
        instance.shared_trace_dfd.get_numpy_handle = MagicMock(
            return_value=np.array(
                [
                    [0.0, 1.0, 2.0, 3.0],
                    [4.0, 8.0, 12.0, 16.0],
                    [20.0, 40.0, 60.0, 80.0],
                ]
            )
        )

        trace, trace_pos = instance.getTrace()
        dfd_trace = instance.getDfdTrace()

        self.assertEqual(trace_pos, 0)
        np.testing.assert_allclose(trace[0], np.array([0.0, 10e-6, 20e-6, 30e-6]))
        np.testing.assert_allclose(
            trace[1],
            np.array([1.0e6, 2.0e6, 3.0e6, 4.0e6]),
        )

        np.testing.assert_allclose(dfd_trace[0], np.array([0.0, 1.0, 2.0, 3.0]))
        np.testing.assert_allclose(
            dfd_trace[1],
            np.array([1.0e6, 2.0e6, 3.0e6, 4.0e6]),
        )
        np.testing.assert_allclose(
            dfd_trace[2],
            np.array([20.0 / (12e-6), 40.0 / (12e-6), 60.0 / (8e-6), 80.0 / (8e-6)]),
        )


if __name__ == '__main__':
    unittest.main()
