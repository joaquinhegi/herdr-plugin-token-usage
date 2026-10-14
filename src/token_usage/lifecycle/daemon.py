"""Detached poller lifecycle (OS primitives live behind a host port): flock guard, pidfile, spawn, signals, cleanup.

Kill-target identity: the poller holds an exclusive flock on poller.lock for life and,
right after acquiring it, writes its own pid INTO the lock file. Probes that win the lock
truncate the file before releasing it, so the lock file holds a pid only while a live
poller owns the lock (a SIGKILLed poller's leftover is wiped by the next probe). SIGTERM is
sent only when the pidfile pid equals the lock-file pid, is > 1 and is not this process;
a probe or a not-yet-registered poller holding the lock is therefore never mistaken for the
daemon. A poller that collides with a probe retries the lock for ~1 s instead of exiting.
"""

import json
import os
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from token_usage.adapters.atomic import replace_with_retry
from token_usage.adapters.log import log_event, log_exception
from token_usage.app.tick import SOURCE, TOKEN
from token_usage.domain.reconcile import Clear, reconcile
from token_usage.lifecycle.host_posix import LOCK as HOST_LOCK, PosixHost

LOCK = HOST_LOCK
PID = "poller.pid"
INTERVAL_S = 4.0
ORPHAN_S = 300.0
PRUNE_S = 3600.0
CLEANUP_S = 3.0   # total shutdown-cleanup budget
LOCK_TRIES = 10   # run() lock attempts, 0.1 s apart (closes the probe-collision window)
WAIT_S = 8.0      # handoff wait: CLEANUP_S + one worst-case herdr call (4 s) + margin


def is_running(state_dir: Path, host=None) -> bool:
    return (host or PosixHost()).held(Path(state_dir))


def read_pidfile(state_dir: Path) -> dict:
    try:
        data = json.loads((Path(state_dir) / PID).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_pidfile(state_dir: Path, info: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(info, fh)
        replace_with_retry(tmp, state_dir / PID)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Poller:
    def __init__(self, state_dir, socket_path, tick, herdr, store, clock, logger,
                 sleep=None, interval=INTERVAL_S, orphan_after=ORPHAN_S,
                 lock_sleep=time.sleep, mono=time.monotonic, host=None):
        self.dir, self.socket_path = Path(state_dir), socket_path
        self.tick, self.herdr, self.store, self.clock, self.logger = tick, herdr, store, clock, logger
        self._stop = threading.Event()
        self._sleep = sleep or self._stop.wait
        self.interval, self.orphan_after = interval, orphan_after
        self._lock_sleep, self._mono = lock_sleep, mono
        self.host = host or PosixHost()

    def request_stop(self) -> None:
        self._stop.set()

    def is_stopping(self) -> bool:
        return self._stop.is_set()

    def install_signals(self) -> None:
        self.host.install_signal_handlers(self.request_stop)

    def run(self) -> int:
        fd = self.host.acquire_lock(self.dir)
        for _ in range(LOCK_TRIES):
            if fd is not None:
                break
            self._lock_sleep(0.1)  # a probe may hold the lock briefly
            fd = self.host.acquire_lock(self.dir)
        if fd is None:
            return 0  # another poller owns the lock
        self.host.record_identity(fd, os.getpid())
        info = {"pid": os.getpid(), "socket_path": self.socket_path, "started_at": self.clock.now()}
        try:
            _write_pidfile(self.dir, info)
            self._loop(info)
        finally:
            self._cleanup()
            self.host.release(fd)
        return 0

    def _loop(self, info: dict) -> None:
        down_since = None
        pruned = None
        while not self._stop.is_set():
            now = self.clock.now()
            if pruned is None or now - pruned >= PRUNE_S:
                pruned = now
                self._safely("prune_failed", lambda: self.store.prune(now))
            reachable = True
            try:
                reachable = self.tick() is not False
            except Exception as exc:  # one bad tick must not kill the poller
                log_exception(self.logger, "tick_failed", exc)
            if reachable:
                down_since = None
            else:
                down_since = now if down_since is None else down_since
                if now - down_since >= self.orphan_after:
                    log_event(self.logger, "orphan_exit")
                    return
            info["last_tick"] = now
            self._safely("pidfile_failed", lambda: _write_pidfile(self.dir, info))
            self._sleep(self.interval)

    def _safely(self, event: str, fn) -> None:
        try:
            fn()
        except Exception as exc:
            log_exception(self.logger, event, exc)

    def _cleanup(self) -> None:
        def clear_all():
            previous = self.store.load_published() or {}
            now = self.clock.now()
            actions, state = reconcile(previous, {p: None for p in previous.get("panes", {})}, now, int(now * 1000))
            deadline = self._mono() + CLEANUP_S
            for action in actions:
                if self._mono() > deadline:
                    log_event(self.logger, "cleanup_deadline")
                    break
                if isinstance(action, Clear):
                    self._safely("clear_failed", lambda a=action: self.herdr.clear(a.pane_id, SOURCE, TOKEN, a.seq))
            self.store.save_published({"seq": state["seq"], "panes": {}})

        self._safely("cleanup_failed", clear_all)
        (self.dir / PID).unlink(missing_ok=True)


def _wait_free(state_dir, sleep, clock, wait, host) -> bool:
    deadline = clock() + wait
    while clock() < deadline:
        if not host.held(state_dir):
            return True
        sleep(1.0)
    return not host.held(state_dir)


def _verified_pid(state_dir, host):
    pid = read_pidfile(state_dir).get("pid")
    if isinstance(pid, int) and pid > 1 and pid == host.holder_pid(state_dir) and pid != os.getpid():
        return pid
    return None


def _terminate(state_dir, sleep, clock, wait, host) -> bool:
    host.request_stop(state_dir, _verified_pid(state_dir, host))
    return _wait_free(state_dir, sleep, clock, wait, host)


def start(state_dir, socket_path, main_path, popen=subprocess.Popen, kill=os.kill,
          sleep=time.sleep, clock=time.monotonic, wait=WAIT_S, host=None) -> str:
    state_dir, host = Path(state_dir), host or PosixHost(popen=popen, kill=kill)
    result = "started"
    if host.held(state_dir):
        if read_pidfile(state_dir).get("socket_path") == socket_path:
            return "running"
        if not _terminate(state_dir, sleep, clock, wait, host):
            return "failed"
        result = "restarted"
    host.spawn([str(main_path), "run"])
    return result


def stop(state_dir, kill=os.kill, sleep=time.sleep, clock=time.monotonic, wait=WAIT_S, host=None) -> str:
    state_dir, host = Path(state_dir), host or PosixHost(kill=kill)
    if not host.held(state_dir):
        return "stopped"
    return "stopped" if _terminate(state_dir, sleep, clock, wait, host) else "failed"


def status(state_dir, store, host=None) -> str:
    if not (host or PosixHost()).held(Path(state_dir)):
        return "stopped"
    info = read_pidfile(state_dir)
    tick = info.get("last_tick")
    when = datetime.fromtimestamp(tick, timezone.utc).strftime("%H:%M:%SZ") if isinstance(tick, (int, float)) else "none"
    panes = (store.load_published() or {}).get("panes", {})
    return f"running pid={info.get('pid')} last_tick={when} panes={len(panes)}"
