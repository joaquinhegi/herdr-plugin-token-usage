"""POSIX host: flock guard with the holder pid in the lock file, SIGTERM stop, detached spawn."""

import os
import signal
import subprocess
import sys
from pathlib import Path

LOCK = "poller.lock"


class PosixHost:
    supports_socket = True
    stop_poll_s = None

    def __init__(self, popen=subprocess.Popen, kill=os.kill):
        self._popen, self._kill = popen, kill

    def acquire_lock(self, d: Path):
        import fcntl  # POSIX only: imported here so the module loads on Windows
        d.mkdir(parents=True, exist_ok=True)
        fd = os.open(d / LOCK, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return None
        return fd

    def record_identity(self, handle, pid: int) -> None:
        os.ftruncate(handle, 0)
        os.write(handle, str(pid).encode())

    def release(self, handle) -> None:
        os.ftruncate(handle, 0)
        os.close(handle)

    def held(self, d: Path) -> bool:
        fd = self.acquire_lock(Path(d))
        if fd is None:
            return True
        self.release(fd)  # we own the lock, so no poller lives: drop any stale pid
        return False

    def holder_pid(self, d: Path):
        try:
            return int((Path(d) / LOCK).read_text().strip())
        except (OSError, ValueError):
            return None

    def spawn(self, argv_tail: list[str]) -> None:
        self._popen([sys.executable, "-B", *argv_tail], start_new_session=True, close_fds=True,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def request_stop(self, d: Path, verified_pid) -> None:
        if verified_pid is None:
            return
        try:
            self._kill(verified_pid, signal.SIGTERM)
        except OSError:
            pass

    def stop_requested(self, d: Path) -> bool:
        return False

    def clear_stop(self, d: Path, older_than: float | None = None) -> None:
        pass

    def force_terminate(self, d: Path, pid, started_at) -> bool:
        return False  # SIGTERM already sent by request_stop; no escalation on POSIX

    def install_signal_handlers(self, on_stop) -> None:
        signal.signal(signal.SIGTERM, lambda *_: on_stop())
        signal.signal(signal.SIGINT, lambda *_: on_stop())
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
