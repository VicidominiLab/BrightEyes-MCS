"""Application entry point kept separate from the Qt window implementation."""

from __future__ import annotations

import atexit
import os
import platform
import sys


def _startup_options(argv):
    """Remove BrightEyes-MCS startup flags before passing arguments to Qt."""

    force_setup = "--setup" in argv
    skip_setup = "--no-first-run" in argv
    filtered = [argument for argument in argv if argument not in {"--setup", "--no-first-run"}]
    return filtered, force_setup, skip_setup


def main(argv=None):
    from ..logging_setup import configure_logging

    configure_logging()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .paths import resource_path
    from ..ui.qt import MainWindow
    from ..ui.qt.first_run import maybe_run_shortcut_setup
    from ..ui.qt.qt_locale import install_scientific_locale

    argv, force_setup, skip_setup = _startup_options(list(sys.argv if argv is None else argv))
    if any(platform.win32_ver()):
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("iit.mms.brighteyesmcs.1")

    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    install_scientific_locale()
    if platform.system() == "Windows" and "-platform" not in argv:
        argv += ["-platform", "windows:darkmode=2"]

    app = QApplication(argv)
    app.setWindowIcon(QIcon(str(resource_path("images/icon.ico"))))
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    if not skip_setup:
        maybe_run_shortcut_setup(force=force_setup)
    window = MainWindow(argv)
    original_excepthook = sys.excepthook

    def shutdown_after_unhandled_exception(exception_type, exception, traceback):
        try:
            window.shutdown()
        finally:
            app.exit(1)
            original_excepthook(exception_type, exception, traceback)

    sys.excepthook = shutdown_after_unhandled_exception
    app.aboutToQuit.connect(window.shutdown)
    atexit.register(window.shutdown)
    try:
        window.show()
        return app.exec()
    finally:
        window.shutdown()
        atexit.unregister(window.shutdown)
        sys.excepthook = original_excepthook


__all__ = ["main"]
