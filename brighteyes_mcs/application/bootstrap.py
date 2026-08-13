"""Application entry point kept separate from the Qt window implementation."""

from __future__ import annotations

import atexit
import argparse
import os
import platform
import sys


def _argument_parser() -> argparse.ArgumentParser:
    """Build launcher help without importing Qt."""

    parser = argparse.ArgumentParser(
        prog="python -m brighteyes_mcs",
        description="Launch BrightEyes-MCS microscope control software.",
        epilog=(
            "BrightEyes-MCS is installed as a Python module and deliberately does not "
            "create a brighteyes-mcs.exe. Run this command from its activated Python "
            "environment."
        ),
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="reopen system-profile and Windows Desktop shortcut setup",
    )
    parser.add_argument(
        "--no-first-run",
        action="store_true",
        help="start without displaying first-run setup",
    )
    parser.add_argument(
        "debug",
        nargs="?",
        help="use the legacy unstable/debug window mode",
    )
    return parser


def _startup_options(argv):
    """Remove BrightEyes-MCS startup flags before passing arguments to Qt."""

    force_setup = "--setup" in argv
    skip_setup = "--no-first-run" in argv
    filtered = [argument for argument in argv if argument not in {"--setup", "--no-first-run"}]
    return filtered, force_setup, skip_setup


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if any(argument in {"-h", "--help"} for argument in argv[1:]):
        _argument_parser().print_help()
        return 0

    from ..logging_setup import configure_logging

    configure_logging()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .paths import resource_path
    from ..ui.qt import MainWindow
    from ..ui.qt.first_run import maybe_run_first_run_setup
    from ..ui.qt.qt_locale import install_scientific_locale

    argv, force_setup, skip_setup = _startup_options(argv)
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
        maybe_run_first_run_setup(force=force_setup)
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
