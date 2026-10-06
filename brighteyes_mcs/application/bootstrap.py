"""Application entry point kept separate from the Qt window implementation."""

from __future__ import annotations

import atexit
import argparse
import os
import platform
import sys


def _add_logging_argument(parser):
    parser.add_argument(
        "--log-level", "--verbosity", dest="log_level", type=int, choices=range(4), default=2,
        help="log verbosity: 0=off, 1=normal, 2=user actions (default), 3=data-flow debug",
    )


def _logging_options(argv):
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    _add_logging_argument(parser)
    options, remaining = parser.parse_known_args(argv[1:])
    return [argv[0], *remaining], options.log_level


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
    _add_logging_argument(parser)
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

    from ..logging_setup import configure_logging, install_exception_logging, logger

    argv, log_level = _logging_options(argv)
    configure_logging(verbosity=log_level)
    restore_exception_logging = install_exception_logging()
    try:
        return _run_application(argv)
    except BaseException:
        logger.exception("Application startup or event loop failed")
        raise
    finally:
        restore_exception_logging()


def _run_application(argv):
    from ..logging_setup import logger

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .paths import resource_path
    from ..ui.qt import MainWindow
    from ..ui.qt.first_run import maybe_run_first_run_setup
    from ..ui.qt.qt_locale import install_scientific_locale
    from ..ui.qt.action_logging import UserActionFilter

    argv, force_setup, skip_setup = _startup_options(argv)
    if any(platform.win32_ver()):
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("iit.mms.brighteyesmcs.1")

    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    install_scientific_locale()
    if platform.system() == "Windows" and "-platform" not in argv:
        argv += ["-platform", "windows:darkmode=2"]

    app = QApplication(argv)
    action_filter = UserActionFilter(app)
    app.installEventFilter(action_filter)
    app.setWindowIcon(QIcon(str(resource_path("images/icon.ico"))))
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    if not skip_setup:
        maybe_run_first_run_setup(force=force_setup)
    window = MainWindow(argv)
    original_excepthook = sys.excepthook

    def shutdown_after_unhandled_exception(exception_type, exception, traceback):
        logger.critical(
            "Unhandled application exception",
            exc_info=(exception_type, exception, traceback),
        )
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
