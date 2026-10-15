"""Windows host: msvcrt byte lock with the holder pid beyond the locked range, stop file, hidden detached spawn.

Byte 0 of poller.lock is locked for the poller's life (the OS drops it when the process dies).
Locked bytes cannot be read by other handles, so the holder pid is written at PID_OFFSET,
outside the locked range, where probes and `stop` can still read it. Stop is cooperative:
`request_stop` creates poller.stop in the state dir and the poller polls for it. If the poller
does not exit, `force_terminate` runs a guarded TerminateProcess (never os.kill).
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

LOCK = "poller.lock"
STOP = "poller.stop"
PID_OFFSET = 16
PID_WIDTH = 16
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
CREATION_WINDOW_S = 60.0  # the pidfile started_at is stamped moments after the process is created
_EPOCH_DELTA_100NS = 116_444_736_000_000_000  # 1601-01-01 to 1970-01-01


class Win32:
    """The few kernel32 calls force_terminate needs, behind a seam so the guard is unit-testable."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._ct, self._wt = ctypes, wintypes
        k = self._k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.argtypes, k.OpenProcess.restype = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
        k.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        k.GetProcessTimes.restype = wintypes.BOOL
        k.TerminateProcess.argtypes, k.TerminateProcess.restype = (wintypes.HANDLE, wintypes.UINT), wintypes.BOOL
        k.CloseHandle.argtypes, k.CloseHandle.restype = (wintypes.HANDLE,), wintypes.BOOL

    def open_process(self, access: int, pid: int):
        return self._k.OpenProcess(access, False, pid) or None

    def creation_time(self, handle):
        ft = [self._wt.FILETIME() for _ in range(4)]
        if not self._k.GetProcessTimes(handle, *(self._ct.byref(f) for f in ft)):
            return None
        ticks = (ft[0].dwHighDateTime << 32) | ft[0].dwLowDateTime
        return (ticks - _EPOCH_DELTA_100NS) / 1e7

    def terminate(self, handle) -> bool:
        return bool(self._k.TerminateProcess(handle, 1))

    def close(self, handle) -> None:
        self._k.CloseHandle(handle)


class WindowsHost:
    supports_socket = False
    stop_poll_s = 0.5

    def __init__(self, popen=subprocess.Popen, win32=None):
        self._popen, self._win32 = popen, win32

    def acquire_lock(self, d: Path):
        import msvcrt  # Windows only: imported here so the module loads on POSIX
        d.mkdir(parents=True, exist_ok=True)
        fd = os.open(d / LOCK, os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0), 0o600)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(fd)
            return None
        return fd

    def _write_identity(self, handle, text: str) -> None:
        os.lseek(handle, PID_OFFSET, os.SEEK_SET)
        os.write(handle, text.encode().ljust(PID_WIDTH))

    def record_identity(self, handle, pid: int) -> None:
        self._write_identity(handle, str(pid))

    def release(self, handle) -> None:
        import msvcrt
        self._write_identity(handle, "")  # blank the pid while the lock still protects it
        try:
            os.lseek(handle, 0, os.SEEK_SET)
            msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(handle)

    def held(self, d: Path) -> bool:
        handle = self.acquire_lock(Path(d))
        if handle is None:
            return True
        self.release(handle)  # we own the lock, so no poller lives: drop any stale pid
        return False

    def holder_pid(self, d: Path):
        try:
            with open(Path(d) / LOCK, "rb") as fh:  # never read byte 0: it is locked
                fh.seek(PID_OFFSET)
                return int(fh.read(PID_WIDTH).strip())
        except (OSError, ValueError):
            return None

    def spawn(self, argv_tail: list[str]) -> None:
        self._popen([sys.executable, "-X", "utf8", "-B", *argv_tail], close_fds=True,
                    creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def request_stop(self, d: Path, verified_pid) -> None:
        (Path(d) / STOP).touch()  # the pid is irrelevant: only the lock holder reads this file

    def stop_requested(self, d: Path) -> bool:
        return (Path(d) / STOP).exists()

    def clear_stop(self, d: Path, older_than: float | None = None) -> None:
        path = Path(d) / STOP
        if older_than is not None:  # keep a request made after the caller's stamp
            try:
                if path.stat().st_mtime > older_than:
                    return
            except OSError:
                return
        path.unlink(missing_ok=True)

    def force_terminate(self, d: Path, pid, started_at) -> bool:
        """TerminateProcess only the verified poller; any doubt returns False without touching a process."""
        if (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1 or pid == os.getpid()
                or isinstance(started_at, bool) or not isinstance(started_at, (int, float))):
            return False
        if not self.held(d) or self.holder_pid(d) != pid:  # held() first: a winning probe wipes the stale pid
            return False
        win32 = self._win32 = self._win32 or Win32()
        handle = win32.open_process(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE, pid)
        if not handle:
            return False
        try:  # the handle pins this process object, so a recycled pid cannot be hit between check and kill
            created = win32.creation_time(handle)
            if created is None or created > started_at or started_at - created > CREATION_WINDOW_S:
                return False
            return bool(win32.terminate(handle))
        finally:
            win32.close(handle)

    def install_signal_handlers(self, on_stop) -> None:
        for name in ("SIGINT", "SIGBREAK"):  # no SIGTERM/SIGHUP semantics on Windows
            sig = getattr(signal, name, None)
            if sig is not None:
                signal.signal(sig, lambda *_: on_stop())
