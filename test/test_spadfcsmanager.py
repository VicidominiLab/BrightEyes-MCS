import os
import sys
# insert root directory into python module search path
sys.path.insert(1, os.getcwd())

import unittest
from unittest.mock import MagicMock, patch
from brighteyes_mcs.libs.spad_fcs_manager import SpadFcsManager

class TestSpadFcsManager(unittest.TestCase):

    def acquisition_run_sets_acquisition_run_event(self):
        instance = SpadFcsManager()
        instance.acquisition_run_event.set = MagicMock()
        instance.acquisition_stop_event.clear = MagicMock()

        instance.acquisition_run()

        instance.acquisition_run_event.set.assert_called()
        instance.acquisition_stop_event.clear.assert_called()

    def acquisition_stop_sets_acquisition_stop_event(self):
        instance = SpadFcsManager()
        instance.acquisition_stop_event.set = MagicMock()
        instance.acquisition_run_event.clear = MagicMock()

        instance.acquisition_stop()

        instance.acquisition_stop_event.set.assert_called()
        instance.acquisition_run_event.clear.assert_called()

    def acquisition_is_done_returns_true_if_done(self):
        instance = SpadFcsManager()
        instance.acquisition_done_event.is_set = MagicMock(return_value=True)

        result = instance.acquisition_is_done()

        self.assertTrue(result)

    def acquisition_is_almost_done_returns_true_if_almost_done(self):
        instance = SpadFcsManager()
        instance.acquisition_almost_done_event.is_set = MagicMock(return_value=True)

        result = instance.acquisition_is_almost_done()

        self.assertTrue(result)

    def set_activate_preview_sets_event(self):
        instance = SpadFcsManager()
        instance.activate_preview_event.set = MagicMock()
        instance.activate_preview_event.clear = MagicMock()

        instance.set_activate_preview(True)
        instance.activate_preview_event.set.assert_called()

        instance.set_activate_preview(False)
        instance.activate_preview_event.clear.assert_called()

    def set_activate_DFD_sets_DFD_Activate(self):
        instance = SpadFcsManager()

        instance.set_activate_DFD(True)
        self.assertTrue(instance.DFD_Activate)

        instance.set_activate_DFD(False)
        self.assertFalse(instance.DFD_Activate)

    def set_activate_snake_walk_sets_snake_walk(self):
        instance = SpadFcsManager()

        instance.set_activate_snake_walk(True)
        self.assertTrue(instance.snake_walk)

        instance.set_activate_snake_walk(False)
        self.assertFalse(instance.snake_walk)

    def connect_sets_is_connected(self):
        instance = SpadFcsManager()
        instance.fpga_handle = MagicMock()
        instance.fpga_handle.run = MagicMock()
        instance.update_chuck = MagicMock()

        with patch("brighteyes_mcs.libs.spad_fcs_manager.FpgaHandle") as MockFpgaHandle:
            MockFpgaHandle.return_value = MagicMock()
            instance.connect()

            self.assertTrue(instance.is_connected)
            instance.fpga_handle.run.assert_called()
            instance.update_chuck.assert_called()

    def connect_raises_exception_on_error(self):
        instance = SpadFcsManager()
        instance.fpga_handle = MagicMock()
        instance.fpga_handle.run = MagicMock(side_effect=Exception("Error"))

        with self.assertRaises(Exception):
            instance.connect()

    def run_starts_dataProcess_and_previewProcess(self):
        instance = SpadFcsManager()
        instance.fpga_handle = MagicMock()
        instance.readRegistersDict = MagicMock()
        instance.dataProcess = MagicMock()
        instance.previewProcess = MagicMock()
        instance.activate_preview_event.is_set = MagicMock(return_value=True)

        instance.run()

        instance.dataProcess.start.assert_called()
        instance.previewProcess.start.assert_called()

    def stopAcquisition_stops_dataProcess(self):
        instance = SpadFcsManager()
        instance.dataProcess = MagicMock()

        instance.stopAcquisition()

        instance.dataProcess.stop.assert_called()

    def stopPreview_stops_previewProcess(self):
        instance = SpadFcsManager()
        instance.previewProcess = MagicMock()

        instance.stopPreview()

        instance.previewProcess.stop.assert_called()
        instance.previewProcess.join.assert_called()

    def getPreviewImage_returns_correct_array(self):
        instance = SpadFcsManager()
        instance.shared_image_xy = MagicMock()
        instance.shared_image_xy.get_numpy_handle = MagicMock(return_value=np.array([[1, 2], [3, 4]]))
        instance.shared_image_xy.get_lock = MagicMock()

        result = instance.getPreviewImage()

        self.assertTrue((result == np.array([[1, 2], [3, 4]])).all())


if __name__ == '__main__':
    unittest.main()