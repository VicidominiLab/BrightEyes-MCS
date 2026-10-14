"""Append-only files and crash-recoverable locks for shared session logging."""

from __future__ import annotations

import os
from hashlib import sha256
from time import monotonic, sleep


def open_append(path, *, encoding="utf-8"):
    """Use kernel-level append, also for faulthandler's direct descriptor writes.

    Windows CRT O_APPEND alone seeks before writing. FILE_APPEND_DATA prevents
    a concurrent native crash dump from overwriting another process's record.
    https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-writefile
    """
    if os.name != "nt":
        return open(path, "a", encoding=encoding)

    import msvcrt
    import ntsecuritycon
    import win32con
    import win32file

    handle = win32file.CreateFile(
        str(path), ntsecuritycon.FILE_APPEND_DATA | ntsecuritycon.SYNCHRONIZE,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
        None, win32con.OPEN_ALWAYS, win32con.FILE_ATTRIBUTE_NORMAL, None,
    )
    try:
        descriptor = msvcrt.open_osfhandle(int(handle), os.O_WRONLY | os.O_BINARY)
    except BaseException:
        handle.Close()
        raise
    handle.Detach()  # The CRT descriptor now owns this Windows handle.
    try:
        return os.fdopen(descriptor, "a", encoding=encoding)
    except BaseException:
        os.close(descriptor)
        raise


class LogFileLock:
    """Serialize records without a queue or a lock held forever by a dead worker.

    Windows named mutexes and POSIX flock are released by the operating system
    when their owner dies. No lock file, manager process or worker argument is
    required. Each process opens its own lock for the same canonical log path.
    """

    def __init__(self, path):
        self._handle = None
        self._descriptor = None
        if os.name == "nt":
            import win32event

            name = sha256(os.path.normcase(os.path.realpath(path)).encode("utf-8")).hexdigest()
            self._handle = win32event.CreateMutex(None, False, "Local\\BrightEyesLog-" + name)
        else:
            self._descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)

    def acquire(self, timeout=0.1):
        if os.name == "nt":
            import win32event

            status = win32event.WaitForSingleObject(self._handle, int(timeout * 1000))
            # WAIT_ABANDONED grants ownership after a worker died holding it.
            return status in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED)

        import fcntl

        deadline = monotonic() + timeout
        while True:
            try:
                fcntl.flock(self._descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                if monotonic() >= deadline:
                    return False
                sleep(0.001)

    def release(self):
        if os.name == "nt":
            import win32event

            win32event.ReleaseMutex(self._handle)
        else:
            import fcntl

            fcntl.flock(self._descriptor, fcntl.LOCK_UN)

    def close(self):
        if self._handle is not None:
            self._handle.Close()
            self._handle = None
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None
