"""In-memory HostPlatform for daemon tests: no fcntl, no signals, no processes."""

from pathlib import Path


class FakeHost:
    supports_socket = True
    stop_poll_s = None

    def __init__(self, holder: int | None = None, stop_file: bool = False, free_after: int | None = None,
                 stop_poll_s: float | None = None, force_result: bool = False, free_on_force: bool = False):
        self.holder = holder  # pid recorded by a live poller; None = lock free
        self.stop_file = stop_file  # Windows-style cooperative stop instead of a signal
        self.free_after = free_after  # stop-file mode: holder frees after this many held() polls
        self.stop_poll_s = stop_poll_s
        self.stop_flag = False
        self.stop_mtime: float | None = None  # mtime of the stop file; None = unknown (always clearable)
        self.clear_error: Exception | None = None
        self.force_result, self.free_on_force = force_result, free_on_force
        self._polls = 0
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
        if self.stop_flag and self.free_after is not None and self.holder is not None:
            self._polls += 1
            if self._polls > self.free_after:
                self.holder = None
        return self.holder is not None

    def holder_pid(self, d: Path):
        return self.holder or None

    def spawn(self, argv_tail: list[str]) -> None:
        self.calls.append(("spawn", list(argv_tail)))

    def request_stop(self, d: Path, verified_pid) -> None:
        self.calls.append(("request_stop", verified_pid))
        if self.stop_file:
            self.stop_flag = self.holder is not None
        elif verified_pid is not None:
            self.holder = None  # a real stop only reaches a verified poller, which then drops its lock

    def stop_requested(self, d: Path) -> bool:
        return self.stop_file and self.stop_flag

    def clear_stop(self, d: Path, older_than: float | None = None) -> None:
        self.calls.append(("clear_stop", older_than))
        if self.clear_error is not None:
            raise self.clear_error
        if older_than is not None and self.stop_mtime is not None and self.stop_mtime > older_than:
            return  # a request made after `older_than` is not stale
        self.stop_flag = False

    def force_terminate(self, d: Path, pid, started_at) -> bool:
        self.calls.append(("force_terminate", pid, started_at))
        if self.force_result and self.free_on_force:
            self.holder = None
        return self.force_result

    def install_signal_handlers(self, on_stop) -> None:
        self.calls.append(("install_signal_handlers",))
