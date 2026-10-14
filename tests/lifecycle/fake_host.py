"""In-memory HostPlatform for daemon tests: no fcntl, no signals, no processes."""

from pathlib import Path


class FakeHost:
    supports_socket = True
    stop_poll_s = None

    def __init__(self, holder: int | None = None):
        self.holder = holder  # pid recorded by a live poller; None = lock free
        self.calls: list[tuple] = []

    def acquire_lock(self, d: Path):
        self.calls.append(("acquire_lock",))
        if self.holder is not None:
            return None
        self.holder = 0
        return object()

    def record_identity(self, handle, pid: int) -> None:
        self.calls.append(("record_identity", pid))
        self.holder = pid

    def release(self, handle) -> None:
        self.calls.append(("release",))
        self.holder = None

    def held(self, d: Path) -> bool:
        self.calls.append(("held",))
        return self.holder is not None

    def holder_pid(self, d: Path):
        return self.holder or None

    def spawn(self, argv_tail: list[str]) -> None:
        self.calls.append(("spawn", list(argv_tail)))

    def request_stop(self, d: Path, verified_pid) -> None:
        self.calls.append(("request_stop", verified_pid))
        if verified_pid is not None:
            self.holder = None  # a real stop only reaches a verified poller, which then drops its lock

    def stop_requested(self, d: Path) -> bool:
        return False

    def clear_stop(self, d: Path) -> None:
        self.calls.append(("clear_stop",))

    def force_terminate(self, d: Path) -> bool:
        return False

    def install_signal_handlers(self, on_stop) -> None:
        self.calls.append(("install_signal_handlers",))
