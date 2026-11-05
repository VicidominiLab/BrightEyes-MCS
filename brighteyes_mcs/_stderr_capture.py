"""Direct, append-only stderr capture that survives abrupt process termination."""

from __future__ import annotations

import os
import sys

from ._log_file import open_append

STD_ERROR_HANDLE = -12


class _BinaryStderr:
    def __init__(self, capture):
        self.capture = capture

    def write(self, data):
        return self.capture._write(data)

    def flush(self):
        self.capture.flush()


class StderrCapture:
    """Mirror Python stderr to the console; send native fd 2 directly to disk.

    No pipe, reader thread or logging lock lies on the native crash path.
    """

    def __init__(self, path):
        self.original = sys.stderr
        self.console = self.original
        self.saved_fd = None
        self._console_owned = False
        self._windows_original = None
        self._windows_fd_handle = None
        self._windows_saved = False
        self._redirected = False
        self.stream = open_append(path)
        self.buffer = _BinaryStderr(self)
        try:
            try:
                self.saved_fd = os.dup(2)
            except OSError:
                pass  # pythonw may have no usable console descriptor.
            try:
                original_fd = self.original.fileno()
            except (AttributeError, OSError, ValueError):
                original_fd = None
            if self.saved_fd is not None and original_fd == 2:
                self.console = os.fdopen(os.dup(self.saved_fd), "w", buffering=1,
                                         encoding=self.encoding, errors="backslashreplace")
                self._console_owned = True
            if os.name == "nt":
                import msvcrt
                import win32api

                self._windows_original = win32api.GetStdHandle(STD_ERROR_HANDLE)
                self._windows_saved = True
                if self.saved_fd is not None:
                    self._windows_fd_handle = msvcrt.get_osfhandle(2)
            os.dup2(self.stream.fileno(), 2)
            self._redirected = True
            if os.name == "nt":
                win32api.SetStdHandle(STD_ERROR_HANDLE, msvcrt.get_osfhandle(2))
            sys.stderr = self
        except BaseException:
            self.close()
            raise

    @property
    def encoding(self):
        return getattr(self.original, "encoding", None) or "utf-8"

    @property
    def errors(self):
        return "backslashreplace"

    def fileno(self):
        return 2

    def isatty(self):
        try:
            return self.console.isatty()
        except Exception:
            return False

    def write(self, text):
        self._write(text.encode("utf-8", errors="backslashreplace"), text)
        return len(text)

    def _write(self, data, text=None):
        # Flush each write: crashes skip Python's finally and atexit handlers.
        try:
            os.write(self.stream.fileno(), data)
        except Exception:
            pass
        try:
            self.console.write(text if text is not None else data.decode(self.encoding, errors="replace"))
            self.console.flush()
        except Exception:
            pass
        return len(data)

    def flush(self):
        for stream in (self.stream, self.console):
            try:
                stream.flush()
            except Exception:
                pass

    def close(self):
        self.flush()
        if sys.stderr is self:
            sys.stderr = self.original
        if self.saved_fd is not None:
            os.dup2(self.saved_fd, 2)
        elif self._redirected:
            os.close(2)
        self._redirected = False
        if os.name == "nt" and self._windows_saved:
            import msvcrt
            import win32api

            handle = self._windows_original
            if handle == self._windows_fd_handle:
                handle = msvcrt.get_osfhandle(2)
            win32api.SetStdHandle(STD_ERROR_HANDLE, handle)
            self._windows_saved = False
        if self.saved_fd is not None:
            os.close(self.saved_fd)
            self.saved_fd = None
        if self._console_owned:
            self.console.close()
            self._console_owned = False
        self.stream.close()
