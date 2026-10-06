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
    else:
        assert "logging failure (configuration)" in result.stderr, details
    assert "ACTION_FAILED" not in content, content
    assert "Unhandled application exception" not in content, content
    assert "Traceback" not in result.stderr, result.stderr
