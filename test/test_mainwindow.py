import os
import sys
# insert root directory into python module search path
sys.path.insert(1, os.getcwd())

import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from PySide6.QtCore import Qt

from brighteyes_mcs.ui.qt.main_window import MainWindow
from brighteyes_mcs.ui.qt.flim_image_view import (
    control_modifier_selects_navigation,
)

class TestMyClass(unittest.TestCase):

    def test_preview_ctrl_modifier_selects_navigation_by_default(self):
        self.assertTrue(
            control_modifier_selects_navigation(
                Qt.KeyboardModifier.ControlModifier
            )
        )
        self.assertFalse(
            control_modifier_selects_navigation(
                Qt.KeyboardModifier.NoModifier
            )
        )

    def test_preview_ctrl_modifier_can_be_inverted(self):
        self.assertFalse(
            control_modifier_selects_navigation(
                Qt.KeyboardModifier.ControlModifier,
                inverted=True,
            )
        )
        self.assertTrue(
            control_modifier_selects_navigation(
                Qt.KeyboardModifier.NoModifier,
                inverted=True,
            )
        )

    @staticmethod
    def _preview_click_fixture(modifiers, inverted=False):
        point = SimpleNamespace(x=lambda: 1.25, y=lambda: 2.5)
        event = SimpleNamespace(
            double=lambda: True,
            pos=lambda: object(),
            modifiers=lambda: modifiers,
        )
        spin_x = MagicMock()
        spin_y = MagicMock()
        spin_z = MagicMock()
        spin_z.value.return_value = 3.75
        instance = SimpleNamespace(
            im_widget=SimpleNamespace(
                view=SimpleNamespace(
                    vb=SimpleNamespace(mapToView=lambda _point: point)
                )
            ),
            preview_view_box=SimpleNamespace(
                navigation_allowed=lambda value:
                    control_modifier_selects_navigation(value, inverted)
            ),
            ui=SimpleNamespace(
                comboBox_view_projection=SimpleNamespace(
                    currentText=lambda: "xy"
                ),
                spinBox_off_x_um=spin_x,
                spinBox_off_y_um=spin_y,
                spinBox_off_z_um=spin_z,
            ),
            getGUI_data=MagicMock(return_value={}),
            markers_list=[],
            drawMarkers=MagicMock(),
            markersViewTable=MagicMock(),
            offset_um_Changed=MagicMock(),
        )
        return instance, event

    def test_unmodified_double_click_adds_preview_marker_by_default(self):
        instance, event = self._preview_click_fixture(
            Qt.KeyboardModifier.NoModifier
        )

        MainWindow.imageClicked(instance, event)

        self.assertEqual(
            instance.markers_list,
            [{
                "offset_x_um": 1.25,
                "offset_y_um": 2.5,
                "offset_z_um": 3.75,
            }],
        )
        instance.offset_um_Changed.assert_not_called()

    def test_ctrl_double_click_moves_preview_by_default(self):
        instance, event = self._preview_click_fixture(
            Qt.KeyboardModifier.ControlModifier
        )

        MainWindow.imageClicked(instance, event)

        self.assertEqual(instance.markers_list, [])
        instance.ui.spinBox_off_x_um.setValue.assert_called_once_with(1.25)
        instance.ui.spinBox_off_y_um.setValue.assert_called_once_with(2.5)
        instance.ui.spinBox_off_z_um.setValue.assert_called_once_with(3.75)
        instance.offset_um_Changed.assert_called_once_with()

    def test_laser_force_pulsing_applies_and_restores_registers(self):
        instance = SimpleNamespace(
            configurationFPGA_dict={
                "laser_time_bin_mode_enable": False,
                "max_laser_time_bin": 9,
            },
            mcs_manager=SimpleNamespace(
                registers_configuration={},
                default_configuration={},
            ),
            ui=SimpleNamespace(
                checkBox_DFD=SimpleNamespace(isChecked=lambda: False),
            ),
            _laser_force_pulsing_previous=None,
            setRegistersDict=MagicMock(),
        )
        instance._currentLaserRegisterValue = (
            lambda name: MainWindow._currentLaserRegisterValue(instance, name)
        )

        MainWindow.laserForcePulsingChanged(instance, True)
        instance.setRegistersDict.assert_called_once_with(
            {
                "laser_time_bin_mode_enable": True,
                "max_laser_time_bin": 1,
                "laser_force_pulsing_enable": True,
            }
        )

        instance.setRegistersDict.reset_mock()
        MainWindow.laserForcePulsingChanged(instance, False)
        instance.setRegistersDict.assert_called_once_with(
            {
                "laser_time_bin_mode_enable": False,
                "max_laser_time_bin": 9,
                "laser_force_pulsing_enable": False,
            }
        )
        self.assertIsNone(instance._laser_force_pulsing_previous)

    def test_dfd_disables_and_unchecks_force_pulsing(self):
        force_pulsing = MagicMock()
        force_pulsing.isChecked.return_value = True
        instance = SimpleNamespace(
            ui=SimpleNamespace(
                checkBox_DFD=SimpleNamespace(isChecked=lambda: True),
                checkBox_pulsing_forced=force_pulsing,
            )
        )

        MainWindow.updateLaserForcePulsingAvailability(instance)

        force_pulsing.setChecked.assert_called_once_with(False)
        force_pulsing.setEnabled.assert_called_once_with(False)

    def temporalSettingsChanged_updates_registers(self):
        instance = MyClass()
        instance.ui.checkBox_circular.isChecked = MagicMock(return_value=True)
        instance.ui.checkBox_DummyData.isChecked = MagicMock(return_value=False)
        instance.setRegistersDict = MagicMock()

        instance.temporalSettingsChanged()

        instance.setRegistersDict.assert_called_with({
            "time_bin_dwell_cycles": int(Cx),
            "max_time_bins_per_pixel": int(time_bin),
            "tag_clock_duration_cycles": int(clock_duration),
            "wait_laser_startup_cycles": int(waitForLaserInCycle),
            "wait_post_frame_cycles": int(waitAfterFrame),
            "wait_laser_first_time_only_enable": waitOnlyFirstTime,
            "circular_scan_enable": True,
            "dummy_data_enable": False,
        })

    def trace_parameters_changed_updates_labels(self):
        instance = MyClass()
        instance.ui.doubleSpinBox_binsize.value = MagicMock(return_value=1.0)
        instance.ui.spinBox_timeresolution.value = MagicMock(return_value=1)
        instance.ui.doubleSpinBox_maxlength.value = MagicMock(return_value=1.0)
        instance.ui.label_trace_total_bins.setText = MagicMock()
        instance.ui.label_trace_total_bins.setStyleSheet = MagicMock()

        instance.trace_parameters_changed()

        instance.ui.label_trace_total_bins.setText.assert_called_with("1000")
        instance.ui.label_trace_total_bins.setStyleSheet.assert_called_with("")

    def configure_analog_sets_registers(self):
        instance = MyClass()
        instance.ui.checkBox_analog_in_integrate_AI0.isChecked = MagicMock(return_value=True)
        instance.ui.checkBox_analog_in_invert_AI0.isChecked = MagicMock(return_value=False)
        instance.ui.comboBox_analogSelect_A.currentIndex = MagicMock(return_value=1)
        instance.ui.comboBox_analogSelect_B.currentIndex = MagicMock(return_value=2)
        instance.setRegistersDict = MagicMock()

        instance.configure_analog()

        instance.setRegistersDict.assert_called_with({
            "analog_a_channel_0_integrate_enable": True,
            "analog_a_channel_0_invert_enable": False,
            "analog_a_input_selector": 1,
            "analog_b_input_selector": 2,
        })

    def activateShowPreview_calls_activateShowPreview(self):
        instance = MyClass()
        instance.mcs_manager.activateShowPreview = MagicMock()

        instance.activateShowPreview(True)

        instance.mcs_manager.activateShowPreview.assert_called_with(True)

    def configure_stream_enables_sets_stream_flags(self):
        instance = MyClass()
        instance.ui.checkBox_fifo_digital.isChecked = MagicMock(return_value=True)
        instance.ui.checkBox_fifo_analog.isChecked = MagicMock(return_value=False)
        instance.mcs_manager.setActivatedFifo = MagicMock()
        instance.setRegistersDict = MagicMock()

        instance.configure_stream_enables()

        instance.mcs_manager.setActivatedFifo.assert_called_with(["stream_out_main"])
        instance.setRegistersDict.assert_called_with({
            "dfd_enable": False,
            "stream_out_aux_enable": False,
            "stream_out_main_enable": True,
        })

    def grabPanorama_sets_image(self):
        instance = MyClass()
        instance.im_widget.getImageItem = MagicMock(return_value=MagicMock(
            x=MagicMock(return_value=0),
            y=MagicMock(return_value=0),
            width=MagicMock(return_value=100),
            height=MagicMock(return_value=100),
            image=MagicMock(return_value=[[0]])
        ))
        instance.im_panorama_widget.setImage = MagicMock()

        instance.grabPanorama()

        instance.im_panorama_widget.setImage.assert_called()

    def updatePreviewConfiguration_updates_shared_dict(self):
        instance = MyClass()
        instance.ui.comboBox_plot_channel.currentText = MagicMock(return_value="1")
        instance.ui.comboBox_view_projection.currentText = MagicMock(return_value="xy")
        instance.ui.checkBox_fcs_preview.isChecked = MagicMock(return_value=True)
        instance.ui.checkBox_trace_on.isChecked = MagicMock(return_value=False)
        instance.mcs_manager.update_shared_dict = MagicMock()

        instance.updatePreviewConfiguration()

        instance.mcs_manager.update_shared_dict.assert_called_with({
            "proj": "xy",
            "channel": 1,
            "activate_autocorrelation": True,
            "activate_trace": False,
        })

    def defineFilename_returns_correct_filename(self):
        instance = MyClass()
        instance.ui.lineEdit_destinationfolder.text = MagicMock(return_value="folder")
        instance.ui.lineEdit_filename.text = MagicMock(return_value="file")
        instance.defineFilename = MagicMock(return_value="folder/file.h5")

        result = instance.defineFilename()

        self.assertEqual(result, "folder/file.h5")

    def start_calls_startAcquisition(self):
        instance = MyClass()
        instance.ui.checkBox_ttmActivate.isChecked = MagicMock(return_value=True)
        instance.ttm_activate_change_state = MagicMock()
        instance.ui.pushButton_acquisitionStart.setEnabled = MagicMock()
        instance.ui.pushButton_stop.setEnabled = MagicMock()
        instance.mcs_manager.is_connected = False
        instance.connectFPGA = MagicMock()
        instance.updatePreviewConfiguration = MagicMock()
        instance.startAcquisition = MagicMock()

        instance.start()

        instance.startAcquisition.assert_called()

    def ttm_activate_change_state_initializes_manager(self):
        instance = MyClass()
        instance.ui.checkBox_ttmActivate.isChecked = MagicMock(return_value=True)
        instance.ui.radioButton_ttm_remote.isChecked = MagicMock(return_value=True)
        instance.ui.lineEdit_ttmPort.text = MagicMock(return_value="1234")
        instance.ui.label_ttm_IP.text = MagicMock(return_value="127.0.0.1")
        instance.ui.lineEdit_ttm_executable_path.text = MagicMock(return_value="")
        instance.ttm_remote_manager = None

        instance.ttm_activate_change_state()

        self.assertIsNotNone(instance.ttm_remote_manager)

    def ttm_remote_is_up_returns_true_if_ready(self):
        instance = MyClass()
        instance.ttm_remote_manager = MagicMock()
        instance.ttm_remote_manager.is_ready = MagicMock(return_value=True)

        result = instance.ttm_remote_is_up()

        self.assertTrue(result)

    def checkAlerts_highlights_invalid_parameters(self):
        instance = MyClass()
        instance.ui.spinBox_range_x.value = MagicMock(return_value=0.0)
        instance.ui.spinBox_nx.value = MagicMock(return_value=2)
        instance.ui.spinBox_range_x.setStyleSheet = MagicMock()
        instance.ui.spinBox_nx.setStyleSheet = MagicMock()

        instance.checkAlerts()

        instance.ui.spinBox_range_x.setStyleSheet.assert_called_with("border: 1px solid red;")
        instance.ui.spinBox_nx.setStyleSheet.assert_called_with("border: 1px solid red;")

    def previewLoop_starts_acquisition(self):
        instance = MyClass()
        instance.ui.spinBox_nrepetition.value = MagicMock(return_value=30000)
        instance.ui.spinBox_nx.setEnabled = MagicMock()
        instance.ui.spinBox_ny.setEnabled = MagicMock()
        instance.ui.spinBox_nframe.setEnabled = MagicMock()
        instance.ui.spinBox_nrepetition.setEnabled = MagicMock()
        instance.mcs_manager.is_connected = False
        instance.connectFPGA = MagicMock()
        instance.positionSettingsChanged_apply = MagicMock()
        instance.temporalSettingsChanged = MagicMock()
        instance.plotSettingsChanged = MagicMock()
        instance.startAcquisition = MagicMock()

        instance.previewLoop()

        instance.startAcquisition.assert_called_with(do_not_save=True)

    def projChanged_updates_labels(self):
        instance = MyClass()
        instance.ui.comboBox_view_projection.currentText = MagicMock(return_value="xy")
        instance.ui.comboBox_view_projection.setStyleSheet = MagicMock()
        instance.ui.spinBox_nx.setStyleSheet = MagicMock()
        instance.ui.spinBox_ny.setStyleSheet = MagicMock()
        instance.ui.spinBox_nframe.setStyleSheet = MagicMock()
        instance.ui.comboBox_plot_channel.setStyleSheet = MagicMock()
        instance.ui.checkBox_fifo_analog.setStyleSheet = MagicMock()
        instance.ui.checkBox_fifo_digital.setStyleSheet = MagicMock()
        instance.ui.label_plot_channel.setText = MagicMock()
        instance.mcs_manager.read_shared_dict = MagicMock()

        instance.projChanged()

        instance.ui.label_plot_channel.setText.assert_called_with("Ch. selected: XY")
        instance.mcs_manager.read_shared_dict.assert_called()

    def finalizeAcquisition_saves_metadata(self):
        instance = MyClass()
        instance.mcs_manager.shared_dict = {"filenameh5": "file.h5"}
        instance.ui.lineEdit_comment.toPlainText = MagicMock(return_value="comment")
        instance.ui.listWidget.addItem = MagicMock()
        instance.getGUI_data = MagicMock(return_value={})
        instance.stop = MagicMock()
        instance.finalizeImage = MagicMock()
        instance.ttm_remote_is_up = MagicMock(return_value=False)
        instance.plugin_signals.signal.emit = MagicMock()

        with patch("H5Manager") as MockH5Manager:
            mock_h5mgr = MockH5Manager.return_value
            instance.finalizeAcquisition()

            mock_h5mgr.metadata_add_initial.assert_called_with("comment")
            mock_h5mgr.metadata_add_dict.assert_any_call("configurationSpadFCSmanager", instance.mcs_manager.registers_configuration)
            mock_h5mgr.metadata_add_dict.assert_any_call("configurationFPGA", instance.configurationFPGA_dict)
            mock_h5mgr.metadata_add_dict.assert_any_call("configurationGUI", instance._gui_config_for_h5(instance.getGUI_data()))
            mock_h5mgr.metadata_add_dict.assert_any_call("configurationGUI_beforeStart", instance._gui_config_for_h5(instance.configurationGUI_dict_beforeStart))
            mock_h5mgr.metadata_add_thumbnail.assert_called()
            mock_h5mgr.close.assert_called()

    def cmd_filename_ttm_opens_dialog(self):
        instance = MyClass()
        instance.ui.lineEdit_destinationfolder.setText = MagicMock()
        instance.ui.lineEdit_ttm_filename.setText = MagicMock()

        with patch("QFileDialog.getExistingDirectory", return_value="folder"):
            instance.cmd_filename_ttm()

            instance.ui.lineEdit_destinationfolder.setText.assert_called_with("folder")
            instance.ui.lineEdit_ttm_filename.setText.assert_called_with("folder")

    def analog_before_stop_sets_analog_out_to_zero(self):
        instance = MyClass()
        instance.ui.checkBox_AnalogOut = [MagicMock(isChecked=MagicMock(return_value=True)) for _ in range(8)]
        instance.setRegistersDict = MagicMock()

        instance.analog_before_stop()

        instance.setRegistersDict.assert_called_with({"analog_output_0_dc_volts": 0, "analog_output_1_dc_volts": 0, "analog_output_2_dc_volts": 0, "analog_output_3_dc_volts": 0, "analog_output_4_dc_volts": 0, "analog_output_5_dc_volts": 0, "analog_output_6_dc_volts": 0, "analog_output_7_dc_volts": 0})

    def stopAcquisition_stops_fpga(self):
        instance = MyClass()
        instance.sendCmdStop = MagicMock()
        instance.mcs_manager.stopPreview = MagicMock()
        instance.timerPreviewImg.stop = MagicMock()
        instance.mcs_manager.stopFPGA = MagicMock()
        instance.mcs_manager.stopAcquisition = MagicMock()

        instance.stopAcquisition()

        instance.sendCmdStop.assert_called()
        instance.mcs_manager.stopPreview.assert_called()
        instance.timerPreviewImg.stop.assert_called()
        instance.mcs_manager.stopFPGA.assert_called()
        instance.mcs_manager.stopAcquisition.assert_called()

    def stop_resets_ui_elements(self):
        instance = MyClass()
        instance.analog_before_stop = MagicMock()
        instance.ttm_remote_is_up = MagicMock(return_value=False)
        instance.stopAcquisition = MagicMock()
        instance.update = MagicMock()
        instance.repaint = MagicMock()

        instance.stop()

        instance.analog_before_stop.assert_called()
        instance.stopAcquisition.assert_called()
        instance.update.assert_called()
        instance.repaint.assert_called()

    def sendCmdRun_sets_run_register(self):
        instance = MyClass()
        instance.setRegistersDict = MagicMock()

        instance.sendCmdRun()

        instance.setRegistersDict.assert_any_call({"stop_command": False, "start_command": False})
        instance.setRegistersDict.assert_any_call({"start_command": True})

    def sendCmdStop_sets_stop_register(self):
        instance = MyClass()
        instance.setRegistersDict = MagicMock()

        instance.sendCmdStop()

        instance.setRegistersDict.assert_any_call({"stop_command": False})
        instance.setRegistersDict.assert_any_call({"stop_command": True})

    def getPreviewImage_returns_preview_image(self):
        instance = MyClass()
        instance.mcs_manager.shared_arrays_ready = True
        instance.mcs_manager.getPreviewImage = MagicMock(return_value="image")

        result = instance.getPreviewImage()

        self.assertEqual(result, "image")

    def getPreviewFlatData_returns_flat_data(self):
        instance = MyClass()
        instance.activeFile = False
        instance.mcs_manager.getPreviewFlatData = MagicMock(return_value="flat_data")

        result = instance.getPreviewFlatData()

        self.assertEqual(result, "flat_data")

    def getCurrentPreviewImage_returns_correct_image(self):
        instance = MyClass()
        instance.ui.comboBox_view_projection.currentText = MagicMock(return_value="xy")
        instance.ui.comboBox_plot_channel.currentText = MagicMock(return_value="RGB")
        instance.getPreviewImage = MagicMock(return_value=[[0]])
        instance.currentImage_pos = [0, 0, 0]
        instance.currentImage_size = [100, 100, 100]
        instance.currentImage_pixels = [100, 100, 100]

        result = instance.getCurrentPreviewImage()

        self.assertIsNotNone(result)

    def plotPreviewImage_sets_image(self):
        instance = MyClass()
        instance.getCurrentPreviewImage = MagicMock(return_value=([[0]], "RGB", True, False, (0, 0), (1, 1)))
        instance.im_widget.setImage = MagicMock()

        instance.plotPreviewImage()

        instance.im_widget.setImage.assert_called()

    def plotCurrentImage_sets_image(self):
        instance = MyClass()
        instance.currentImage = np.zeros((10, 10, 10, 10, 10))
        instance.selected_channel = 1
        instance.ui.spinBox_off_x_um.value = MagicMock(return_value=0)
        instance.ui.spinBox_off_y_um.value = MagicMock(return_value=0)
        instance.ui.spinBox_range_x.value = MagicMock(return_value=100)
        instance.ui.spinBox_range_y.value = MagicMock(return_value=100)
        instance.ui.spinBox_nx.value = MagicMock(return_value=10)
        instance.ui.spinBox_ny.value = MagicMock(return_value=10)
        instance.im_widget.setImage = MagicMock()

        instance.plotCurrentImage()

        instance.im_widget.setImage.assert_called()

    def selectChannelSum_sets_selected_channel(self):
        instance = MyClass()
        instance.setSelectedChannel = MagicMock()

        instance.selectChannelSum()

        instance.setSelectedChannel.assert_called_with(-1)

    def SaveConfigurationCmd_calls_SaveConfiguration(self):
        instance = MyClass()
        instance.SaveConfiguration = MagicMock()

        instance.SaveConfigurationCmd()

        instance.SaveConfiguration.assert_called()

    def SaveConfiguration_saves_configuration(self):
        instance = MyClass()
        instance.getGUI_data = MagicMock(return_value={})
        instance.ui.lineEdit_configurationfile.text = MagicMock(return_value="config.cfg")
        instance.ui.statusBar.showMessage = MagicMock()
        instance.ask_to_save_cfg_as_permanent = MagicMock()

        with patch("QFileDialog.getSaveFileName", return_value=("config.cfg",)):
            with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
                instance.SaveConfiguration()

                mock_file.assert_called_with("config.cfg", "w")
                instance.ui.statusBar.showMessage.assert_called_with("config.cfg saved.", 5000)
                instance.ask_to_save_cfg_as_permanent.assert_called()

    def LoadConfigurationCmd_calls_LoadConfiguration(self):
        instance = MyClass()
        instance.LoadConfiguration = MagicMock()

        instance.LoadConfigurationCmd()

        instance.LoadConfiguration.assert_called()

    def LoadConfiguration_loads_configuration(self):
        instance = MyClass()
        instance.ui.lineEdit_configurationfile.text = MagicMock(return_value="config.cfg")
        instance.ui.statusBar.showMessage = MagicMock()
        instance.ui.label_loadedcfg.setText = MagicMock()
        instance.updatePixelValueChanged = MagicMock()
        instance.ask_to_save_cfg_as_permanent = MagicMock()

        with patch("QFileDialog.getOpenFileName", return_value=("config.cfg",)):
            with patch("builtins.open", unittest.mock.mock_open(read_data='{"key": "value"}')):
                instance.LoadConfiguration()

                instance.ui.statusBar.showMessage.assert_called_with("config.cfg opened and GUI configuration updated.", 5000)
                instance.ui.label_loadedcfg.setText.assert_called_with("config.cfg")
                instance.updatePixelValueChanged.assert_called()

if __name__ == '__main__':
    unittest.main()
