"""Launch the complete GUI in its own interpreter, without acquisition hardware."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("log_directory_available", [True, False])
def test_full_window_startup_and_plot_signals(tmp_path, log_directory_available):
    if not log_directory_available:
        # An existing file cannot be used as a log directory, even under admin.
        (tmp_path / "logs").write_text("not a directory", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        APPDATA=str(tmp_path / "appdata"),
        LOCALAPPDATA=str(tmp_path / "localappdata"),
        IPYTHONDIR=str(tmp_path / "ipython"),
        QT_QPA_PLATFORM="offscreen",
        BRIGHTEYES_LOG_DIR=str(tmp_path / "logs"),
        BRIGHTEYES_LOG_SESSION="startup-test",
    )
    source = textwrap.dedent("""\
        if __name__ == '__main__':
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication
            from unittest.mock import Mock
            from brighteyes_mcs.application.bootstrap import main
            from brighteyes_mcs.logging_setup import logger
            from brighteyes_mcs.ui import qt

            class StartupWindow(qt.MainWindow):
                def __init__(self, args):
                    import os
                    if os.name == 'nt':
                        from PySide6.QtGui import QFont, QFontDatabase
                        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
                        QApplication.instance().setFont(QFont('Segoe UI', 9))
                    super().__init__(args)
                    QTimer.singleShot(1500, self.check_startup)

                def connectFPGA(self):
                    raise AssertionError('Startup must not connect to hardware')

                def check_startup(self):
                    assert self.init_ready and self.guiReadyFlag
                    assert not self._shutdown_started and not self._shutdown_complete
                    assert not self.mcs_manager.is_connected
                    combo = self.ui.comboBox_plot_channel
                    combo.setCurrentIndex((combo.currentIndex() + 1) % combo.count())
                    combo.setCurrentText('LIFETIME_HSV')
                    assert 'red' in combo.styleSheet()
                    self.ui.checkBox_DFD.click()
                    assert combo.currentText() == 'Sum'
                    self.ui.doubleSpinBox_binsize.setValue(0.01)
                    assert self.ui.doubleSpinBox_binsize.value() > (
                        self.ui.spinBox_DFD_nbins.value()
                        * self.ui.spinBox_timeresolution.value() / 1000)
                    combo.setCurrentText('LIFETIME_HSV')
                    assert combo.styleSheet() == ''
                    self.ui.checkBox_lifetime_force_quality_full.setChecked(False)
                    assert self.ui.checkBox_lifetime_auto_quality.isEnabled()
                    self.ui.checkBox_lifetime_auto_quality.setChecked(True)
                    self.ui.checkBox_lifetime_hue_wrap.setChecked(True)
                    self.ui.doubleSpinBox_lifetime_percentile_high.setValue(98)
                    options = self.getLifetimeScalingOptions()
                    assert options == dict(auto_counts=True, auto_counts_zero=False, auto_quality=True,
                                           hue_wrap=True, hue_wrap_mode='repeat',
                                           equalize_hue=False, equalize_counts=False,
                                           hue_offset=0, value_gamma=1,
                                           analysis_interval=1, percentiles=(1, 98))
                    self.ui.checkBox_lifetime_auto_counts_zero.click()
                    assert self.getLifetimeScalingOptions()['auto_counts_zero']
                    assert self.getGUI_data()['lifetime_auto_counts_zero']
                    self.ui.checkBox_lifetime_auto_counts.setChecked(False)
                    assert not self.ui.checkBox_lifetime_auto_counts_zero.isEnabled()
                    self.ui.checkBox_lifetime_auto_counts.setChecked(True)
                    assert self.ui.checkBox_lifetime_auto_counts_zero.isEnabled()
                    self.ui.checkBox_lifetime_equalize_hue.setChecked(True)
                    assert self.getLifetimeScalingOptions()['equalize_hue']
                    assert self.ui.toolButton_lifetime_equalize_hue_update.isEnabled()
                    assert not self.ui.toolButton_lifetime_equalize_counts_update.isEnabled()
                    self.refreshLifetimeEqualization = Mock()
                    self.ui.toolButton_lifetime_equalize_hue_update.click()
                    self.refreshLifetimeEqualization.assert_called_once_with('H')
                    assert [self.ui.widget_lifetime_controls.tabs.tabText(i).replace('&&', '&') for i in range(3)] == [
                        'Hue', 'Brightness & saturation', 'Histogram & correction']
                    self.ui.doubleSpinBox_lifetime_hue_shift.setValue(-90)
                    assert self.ui.doubleSpinBox_lifetime_hue_shift.value() == 270
                    assert self.getLifetimeScalingOptions()['hue_offset'] == 0.75
                    self.ui.slider_lifetime_value_gamma.setValue(200)
                    assert self.getLifetimeScalingOptions()['value_gamma'] == 2
                    assert self.getGUI_data()['lifetime_hue_shift'] == 270
                    assert self.getGUI_data()['lifetime_value_gamma'] == 2
                    self.traceReset()  # Idle reset has no preview process.
                    self.ui.widget_lifetime_controls.layout().activate()
                    self.layout().activate()
                    assert self.minimumSizeHint().width() < 1870
                    assert self.getGUI_data()['lifetime_percentile_high'] == 98
                    self.ui.checkBox_DFD.click()
                    assert 'red' in combo.styleSheet()
                    combo.setCurrentText('Sum')
                    assert self.ui.doubleSpinBox_lifetime_value_gamma.isEnabled()
                    assert self.ui.widget_lifetime_controls.isHidden()
                    assert not self.ui.widget_preview_gamma.isHidden()
                    gamma_index = self.ui.gridLayout_4.indexOf(self.ui.widget_preview_gamma)
                    assert self.ui.gridLayout_4.getItemPosition(gamma_index)[:2] == (0, 4)
                    assert self.ui.label_lifetime_gamma.text() == 'Gamma'
                    assert self.im_widget._image_gamma == 2
                    assert self.circular_preview_widget._image_gamma == 2
                    self.im_widget_plot_item.setXRange(0, 2)
                    # Exercise the real clicked(bool) connection and handler,
                    # replacing only the physical hardware operations.
                    self.connectFPGA = Mock(side_effect=lambda:
                        setattr(self.mcs_manager, 'is_connected', True))
                    self.disconnectFPGA = Mock(side_effect=lambda:
                        setattr(self.mcs_manager, 'is_connected', False))
                    self._fpgaWatchdogTick = Mock()
                    button = self.ui.pushButton_fpga_connection_cmd
                    button.click()
                    self.connectFPGA.assert_called_once_with()
                    assert self.mcs_manager.is_connected and button.isChecked()
                    button.click()
                    self.disconnectFPGA.assert_called_once_with()
                    assert not self.mcs_manager.is_connected and not button.isChecked()
                    logger.info('STARTUP_AND_PLOT_SIGNALS_OK')
                    import sys
                    self.flare._start_reference_write = Mock()
                    self.flare.selection_changed('TCP/IP - FPGA Flare')
                    self.ui.checkBox_DFD.click()
                    combo.setCurrentText('LIFETIME_HSV')
                    self.ui.comboBox_lifetime_channel.setCurrentText('Ch 10')
                    assert self.getLifetimeSourceChannel() == 10
                    assert self.flare.display_channels == (10,)
                    assert self.getGUI_data()['lifetime_channel'] == 'Ch 10'
                    self.ui.comboBox_lifetime_channel.setCurrentText('Sum')
                    assert self.getLifetimeSourceChannel() is None
                    assert len(self.flare.display_channels) == 25
                    self.ui.doubleSpinBox_binsize.setValue(10)
                    assert abs(self.ui.doubleSpinBox_binsize.value() - 10.01) < 1e-9
                    assert abs(self.ui.doubleSpinBox_binsize.singleStep() - 0.182) < 1e-9
                    self.ui.doubleSpinBox_binsize.stepDown()
                    assert abs(self.ui.doubleSpinBox_binsize.value() - 9.828) < 1e-9
                    # Reproduce the user's window size with populated lifetime
                    # histograms and both DFD/time trace plots present.
                    import numpy as np
                    from PySide6.QtWidgets import QScrollArea
                    from brighteyes_mcs.ui.qt.workspace_layout import size_default_docks
                    self.showNormal()
                    self.resize(1867, 950)
                    size_default_docks(self, self.ui)
                    image = np.ones((32, 32, 3))
                    image[..., 0] = np.linspace(0.2, 0.8, 1024).reshape(32, 32)
                    image[..., 2] = np.linspace(10, 100, 1024).reshape(32, 32)
                    self.im_widget.setFlimImage(image, render_mode='hsv', auto_counts=True)
                    QApplication.processEvents()
                    assert self.width() == 1867 and self.height() == 950
                    assert self.centralWidget() is self.ui.centralwidget
                    assert self.ui.tab_preview.findChild(QScrollArea) is None
                    assert self.ui.dockWidget_preview.width() <= 400
                    assert self.ui.dockWidget_trace.width() <= 400
                    assert self.im_widget.width() > 900
                    assert self.ui.scrollArea_6.horizontalScrollBar().maximum() == 0
                    assert self.ui.scrollArea_6.verticalScrollBar().maximum() == 0
                    previous_width = self.ui.dockWidget_statistics.width()
                    self.ui.dockWidget_traceConf.raise_()
                    QApplication.processEvents()
                    assert self.ui.dockWidget_traceConf.width() == previous_width
                    assert self.ui.dockWidget_traceConf.minimumSizeHint().width() < 360
                    self.ui.dockWidget_trace.raise_()
                    QApplication.processEvents()
                    assert self.ui.dockWidget_trace.width() == previous_width
                    print('STARTUP_AND_PLOT_SIGNALS_OK', file=sys.__stdout__, flush=True)
                    self.close()
                    QApplication.instance().quit()

            qt.MainWindow = StartupWindow
            raise SystemExit(main(['mcs', '--no-first-run', '-platform', 'offscreen']))
    """)
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=Path(__file__).resolve().parents[1],
        env=environment, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60,
    )
    path = tmp_path / "logs/mcs-log-startup-test.log"
    content = path.read_text(encoding="utf-8") if log_directory_available and path.exists() else ""
    details = result.stdout[-4000:] + result.stderr[-4000:] + content[-6000:]
    assert result.returncode == 0, details
    assert "STARTUP_AND_PLOT_SIGNALS_OK" in result.stdout, details
    if log_directory_available:
        assert "STARTUP_AND_PLOT_SIGNALS_OK" in content, details
        assert list(path.parent.iterdir()) == [path]
    else:
        assert "logging failure (configuration)" in result.stderr, details
    assert "ACTION_FAILED" not in content, content
    assert "Unhandled application exception" not in content, content
    assert "Traceback" not in result.stderr, result.stderr
