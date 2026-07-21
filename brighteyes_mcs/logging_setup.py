"""Standard logging configuration for the BrightEyes application."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from time import localtime, strftime


LOGGER_NAME = "brighteyes_mcs"
SESSION_ENV_VAR = "BRIGHTEYES_LOG_SESSION"
LOG_DIR_ENV_VAR = "BRIGHTEYES_LOG_DIR"
logger = logging.getLogger(LOGGER_NAME)


def _session_timestamp() -> str:
    timestamp = os.environ.get(SESSION_ENV_VAR)
    if timestamp is None:
        timestamp = strftime("%y%m%d-%H%M%S", localtime())
        os.environ[SESSION_ENV_VAR] = timestamp
    return timestamp


def default_log_dir() -> Path:
    """Return a user-writable directory for application logs."""

    configured = os.environ.get(LOG_DIR_ENV_VAR)
    if configured:
        return Path(configured)

    user_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if user_data:
        return Path(user_data) / "BrightEyes-MCS" / "log"
    return Path.cwd() / "log"


def configure_logging(*, debug_enabled: bool = False, log_dir: str | Path | None = None) -> Path:
    """Configure the package logger once and return the active log file."""

    logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    logger.propagate = False

    destination = Path(log_dir) if log_dir is not None else default_log_dir()
    destination.mkdir(parents=True, exist_ok=True)
    log_file = (destination / f"mcs-log-{_session_timestamp()}.log").resolve()

    if not any(getattr(handler, "baseFilename", None) == str(log_file) for handler in logger.handlers):
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(pathname)s:%(lineno)d: %(asctime)s.%(msecs)03d\t%(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return log_file


def set_debug(enabled: bool = False) -> None:
    """Enable or disable debug messages for the BrightEyes package logger."""

    logger.setLevel(logging.DEBUG if enabled else logging.INFO)
