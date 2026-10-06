"""Standard logging configuration for the BrightEyes application."""

from __future__ import annotations

import logging
import os
import faulthandler
import multiprocessing
import sys
import threading
from contextvars import ContextVar
from functools import wraps
from inspect import Parameter, signature
from itertools import count
from pathlib import Path
from time import localtime, strftime


LOGGER_NAME = "brighteyes_mcs"
SESSION_ENV_VAR = "BRIGHTEYES_LOG_SESSION"
LOG_DIR_ENV_VAR = "BRIGHTEYES_LOG_DIR"
VERBOSITY_ENV_VAR = "BRIGHTEYES_LOG_VERBOSITY"
DEFAULT_VERBOSITY = 2
ACTION_LEVEL = 15
logging.addLevelName(ACTION_LEVEL, "ACTION")
_reported_failures = set()


def report_logging_failure(context, error):
    """Best-effort, once-per-component notice independent of the logging system."""
    try:
        if context in _reported_failures:
            return
        _reported_failures.add(context)
        print(f"BrightEyes-MCS logging failure ({context}): {error}. "
              "The application will continue without this diagnostic.",
              file=sys.stderr, flush=True)
    except Exception:
        pass  # Even stderr may be missing, closed or out of disk space.


class ResilientLogger(logging.LoggerAdapter):
    """Keep record creation, filters, formatting and handlers out of app control flow."""

    def log(self, level, msg, *args, **kwargs):
        try:
            kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
            super().log(level, msg, *args, **kwargs)
        except Exception as error:
            report_logging_failure("record output", error)

    def __getattr__(self, name):
        return getattr(self.logger, name)

    @property
    def propagate(self):
        return self.logger.propagate

    @propagate.setter
    def propagate(self, value):
        self.logger.propagate = value


class ResilientFileHandler(logging.FileHandler):
    """Stop retrying an unusable file; leave the application and other sinks running."""
    _failed = False

    def handle(self, record):
        if self._failed:
            return False
        try:
            return super().handle(record)
        except Exception as error:
            self._failed = True
            report_logging_failure("file handler", error)
            return False

    def handleError(self, record):
        error = sys.exc_info()[1]
        if isinstance(error, OSError):
            self._failed = True
        report_logging_failure("file output", error)


logger = ResilientLogger(logging.getLogger(LOGGER_NAME), {})
_action = ContextVar("log_action", default="-")
_action_sequence = count(1)
_fault_file = None


def verbosity() -> int:
    try:
        selected = int(os.environ.get(VERBOSITY_ENV_VAR, DEFAULT_VERBOSITY))
        if selected not in (0, 1, 2, 3):
            raise ValueError("Log verbosity must be 0, 1, 2 or 3")
        return selected
    except (TypeError, ValueError) as error:
        report_logging_failure("verbosity setting", error)
        return DEFAULT_VERBOSITY


def safe_log(level, message, *args, **kwargs):
    """Guard diagnostic calls, including replaced/custom logger implementations."""
    try:
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        logger.log(level, message, *args, **kwargs)
    except Exception as error:
        report_logging_failure("diagnostic output", error)


def data_debug_enabled() -> bool:
    return verbosity() == 3


class SessionFilter(logging.Filter):
    def filter(self, record):
        record.action = _action.get()
        return True


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


def configure_logging(*, verbosity: int | None = None, debug_enabled: bool | None = None,
                      log_dir: str | Path | None = None) -> Path | None:
    """Try to configure logging; unavailable diagnostics must not block startup."""
    try:
        return _configure_logging(verbosity=verbosity, debug_enabled=debug_enabled, log_dir=log_dir)
    except Exception as error:
        report_logging_failure("configuration", error)
        return None


def _configure_logging(*, verbosity=None, debug_enabled=None, log_dir=None):
    """Configure this process; children inherit the session, folder and verbosity.

    Each process owns a file, avoiding interleaved writes and tracebacks on Windows.
    Level zero creates neither a directory nor a file.
    """
    global _fault_file
    selected = (int(os.environ.get(VERBOSITY_ENV_VAR, DEFAULT_VERBOSITY))
                if verbosity is None else verbosity)
    if debug_enabled is not None and verbosity is None:
        selected = 3 if debug_enabled else 1
    if selected not in (0, 1, 2, 3):
        raise ValueError("Log verbosity must be 0, 1, 2 or 3")
    os.environ[VERBOSITY_ENV_VAR] = str(selected)
    logger.setLevel({0: logging.CRITICAL + 1, 1: logging.INFO,
                     2: ACTION_LEVEL, 3: logging.DEBUG}[selected])
    logger.propagate = False
    destination = Path(log_dir) if log_dir is not None else default_log_dir()
    destination = destination.resolve()
    os.environ[LOG_DIR_ENV_VAR] = str(destination)
    for handler in list(logger.handlers):
        if getattr(handler, "_brighteyes_handler", False):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception as error:
                report_logging_failure("handler cleanup", error)
    if _fault_file is not None:
        try:
            faulthandler.disable()
            _fault_file.close()
        except Exception as error:
            report_logging_failure("crash diagnostics cleanup", error)
        _fault_file = None
    if selected == 0:
        return None
    destination.mkdir(parents=True, exist_ok=True)
    suffix = ("" if multiprocessing.current_process().name == "MainProcess"
              else f"-pid-{os.getpid()}")
    log_file = destination / f"mcs-log-{_session_timestamp()}{suffix}.log"
    handler = ResilientFileHandler(log_file, encoding="utf-8")
    handler._brighteyes_handler = True
    handler.addFilter(SessionFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s pid=%(process)d "
        "process=%(processName)s thread=%(threadName)s action=%(action)s "
        "%(pathname)s:%(lineno)d %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
    logger.addHandler(handler)
    # Keep the descriptor alive for native faults, including crashes in extensions.
    try:
        _fault_file = log_file.open("a", encoding="utf-8")
        faulthandler.enable(file=_fault_file, all_threads=True)
    except Exception as error:
        report_logging_failure("native crash diagnostics", error)
        if _fault_file is not None:
            try:
                _fault_file.close()
            except Exception:
                pass
            _fault_file = None
    safe_log(logging.INFO, "Logging started verbosity=%s session=%s python=%s", selected,
             _session_timestamp(), sys.version.split()[0])
    return log_file


def set_debug(enabled: bool = False) -> None:
    """Legacy API: worker constructor flags must not override launcher policy."""
    if VERBOSITY_ENV_VAR not in os.environ:
        logger.setLevel(logging.DEBUG if enabled else logging.INFO)


def _signature_wrapper(function, dispatch):
    """Give PySide the actual Python argument layout, not just __signature__.

    Qt examines the callable's code to select signal arguments. A *args wrapper
    changes both its choice of clicked(bool) and its trimming of longer signals.
    Compile only parameter names/kinds from our Python function; default objects
    and annotations are restored directly, never interpolated into source code.
    """
    original = signature(function)
    parameters = list(original.parameters.values())
    declaration = original.replace(
        parameters=[parameter.replace(annotation=Parameter.empty,
                    default=None if parameter.default is not Parameter.empty else Parameter.empty)
                    for parameter in parameters], return_annotation=Parameter.empty)
    forwarding = []
    for parameter in parameters:
        name = parameter.name
        if parameter.kind == Parameter.VAR_POSITIONAL:
            forwarding.append(f"*{name}")
        elif parameter.kind == Parameter.VAR_KEYWORD:
            forwarding.append(f"**{name}")
        elif parameter.kind == Parameter.KEYWORD_ONLY:
            forwarding.append(f"{name}={name}")
        else:
            forwarding.append(name)
    dispatch_name = "_trace_dispatch"
    while dispatch_name in original.parameters:
        dispatch_name += "_"
    namespace = {dispatch_name: dispatch}
    source = (f"def wrapper{declaration}:\n"
              f"    return {dispatch_name}({', '.join(forwarding)})\n")
    exec(compile(source, f"<trace_action {function.__qualname__}>", "exec"), namespace)
    wrapper = namespace["wrapper"]
    wrapper.__defaults__ = function.__defaults__
    wrapper.__kwdefaults__ = function.__kwdefaults__
    return wraps(function)(wrapper)


def trace_action(function):
    """Record the first handler while preserving Qt's original signal delivery."""

    @wraps(function)
    def traced(*args, **kwargs):
        token = None
        try:
            if verbosity() >= 2 and _action.get() == "-":
                token = _action.set(f"{os.getpid()}-{next(_action_sequence)}")
                source = "direct"
                try:
                    if args and callable(getattr(args[0], "sender", None)):
                        sender = args[0].sender()
                        if sender is not None:
                            source = sender.objectName() or type(sender).__name__
                except RuntimeError:
                    pass  # A Qt object may already be tearing down.
                # Do not copy images or arbitrary widget representations into logs.
                values = [value if isinstance(value, (int, float, bool, type(None)))
                          else value[:256] if isinstance(value, str) else type(value).__name__
                          for value in args[1:]]
                options = {key: value if isinstance(value, (int, float, bool, type(None)))
                           else value[:256] if isinstance(value, str) else type(value).__name__
                           for key, value in kwargs.items()}
                safe_log(ACTION_LEVEL, "ACTION_BEGIN first_call=%s source=%s args=%r kwargs=%r",
                         function.__qualname__, source, values, options)
        except Exception as error:
            report_logging_failure("action metadata", error)

        # The real action is executed exactly once, outside diagnostic setup.
        # Never retry it or suppress its own exception if logging fails.
        try:
            result = function(*args, **kwargs)
        except BaseException:
            if token is not None:
                safe_log(logging.ERROR, "ACTION_FAILED first_call=%s", function.__qualname__,
                         exc_info=True)
            raise
        else:
            if token is not None:
                safe_log(ACTION_LEVEL, "ACTION_END first_call=%s", function.__qualname__)
            return result
        finally:
            if token is not None:
                try:
                    _action.reset(token)
                except Exception as error:
                    report_logging_failure("action context cleanup", error)
    try:
        return _signature_wrapper(function, traced)
    except Exception as error:
        report_logging_failure("action wrapper setup", error)
        return function


def logged_worker(function):
    """Initialize logging inside spawned processes and preserve fatal tracebacks."""
    @wraps(function)
    def run(*args, **kwargs):
        restore_exceptions = None
        try:
            if VERBOSITY_ENV_VAR in os.environ:
                configure_logging()
            restore_exceptions = install_exception_logging()
        except Exception as error:
            report_logging_failure("worker diagnostics setup", error)
        safe_log(logging.INFO, "WORKER_START %s", function.__qualname__)
        try:
            return function(*args, **kwargs)
        except BaseException:
            safe_log(logging.ERROR, "WORKER_FAILED %s", function.__qualname__, exc_info=True)
            raise
        finally:
            safe_log(logging.INFO, "WORKER_EXIT %s", function.__qualname__)
            if restore_exceptions is not None:
                try:
                    restore_exceptions()
                except Exception as error:
                    report_logging_failure("worker diagnostics cleanup", error)
    return run


def install_exception_logging():
    """Capture startup and background-thread failures while retaining stderr."""
    original_sys, original_thread = sys.excepthook, threading.excepthook

    def application_error(kind, error, traceback):
        safe_log(logging.CRITICAL, "Unhandled application exception", exc_info=(kind, error, traceback))
        original_sys(kind, error, traceback)

    def thread_error(args):
        safe_log(logging.CRITICAL, "Unhandled thread exception: %s", args.thread.name,
                 exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        original_thread(args)

    sys.excepthook, threading.excepthook = application_error, thread_error

    def restore():
        sys.excepthook, threading.excepthook = original_sys, original_thread
    return restore
