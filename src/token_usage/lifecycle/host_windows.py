"""Windows host: msvcrt byte lock with the holder pid beyond the locked range, stop file, hidden detached spawn.

Byte 0 of poller.lock is locked for the poller's life (the OS drops it when the process dies).
Locked bytes cannot be read by other handles, so the holder pid is written at PID_OFFSET,
outside the locked range, where probes and `stop` can still read it. Stop is cooperative:
`request_stop` creates poller.stop in the state dir and the poller polls for it.
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


class WindowsHost:
    supports_socket = False
    stop_poll_s = 0.5

    def __init__(self, popen=subprocess.Popen):
        self._popen = popen

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

    def clear_stop(self, d: Path) -> None:
        (Path(d) / STOP).unlink(missing_ok=True)

    def force_terminate(self, d: Path) -> bool:
        return False  # slice 2b: guarded TerminateProcess; until then a stuck poller reports "failed"

    def install_signal_handlers(self, on_stop) -> None:
        for name in ("SIGINT", "SIGBREAK"):  # no SIGTERM/SIGHUP semantics on Windows
            sig = getattr(signal, name, None)
            if sig is not None:
                signal.signal(sig, lambda *_: on_stop())
