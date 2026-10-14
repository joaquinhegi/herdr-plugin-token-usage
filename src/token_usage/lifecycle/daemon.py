"""Detached poller lifecycle: flock guard, pidfile, spawn, signals, cleanup."""

import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from token_usage.adapters.log import log_event, log_exception
from token_usage.app.tick import SOURCE, TOKEN
from token_usage.domain.reconcile import Clear, reconcile

LOCK = "poller.lock"
PID = "poller.pid"
INTERVAL_S = 4.0
ORPHAN_S = 300.0
PRUNE_S = 3600.0
WAIT_S = 5.0


def _try_lock(state_dir: Path) -> int | None:
    """Return a locked fd, or None when another process holds the lock."""
    state_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(state_dir / LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def is_running(state_dir: Path) -> bool:
    fd = _try_lock(Path(state_dir))
    if fd is None:
        return True
    os.close(fd)
    return False


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
        os.replace(tmp, state_dir / PID)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Poller:
    def __init__(self, state_dir, socket_path, tick, herdr, store, clock, logger,
                 sleep=None, interval=INTERVAL_S, orphan_after=ORPHAN_S):
        self.dir, self.socket_path = Path(state_dir), socket_path
        self.tick, self.herdr, self.store, self.clock, self.logger = tick, herdr, store, clock, logger
        self._stop = threading.Event()
        self._sleep = sleep or self._stop.wait
        self.interval, self.orphan_after = interval, orphan_after

    def request_stop(self) -> None:
        self._stop.set()

    def install_signals(self) -> None:
        signal.signal(signal.SIGTERM, lambda *_: self.request_stop())
        signal.signal(signal.SIGINT, lambda *_: self.request_stop())
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def run(self) -> int:
        fd = _try_lock(self.dir)
        if fd is None:
            return 0  # another poller owns the lock
        info = {"pid": os.getpid(), "socket_path": self.socket_path, "started_at": self.clock.now()}
        try:
            _write_pidfile(self.dir, info)
            self._loop(info)
        finally:
            self._cleanup()
            os.close(fd)
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
            for action in actions:
                if isinstance(action, Clear):
                    self._safely("clear_failed", lambda a=action: self.herdr.clear(a.pane_id, SOURCE, TOKEN, a.seq))
            self.store.save_published({"seq": state["seq"], "panes": {}})

        self._safely("cleanup_failed", clear_all)
        (self.dir / PID).unlink(missing_ok=True)


def _wait_free(state_dir, sleep, clock, wait) -> bool:
    deadline = clock() + wait
    while clock() < deadline:
        if not is_running(state_dir):
            return True
        sleep(1.0)
    return not is_running(state_dir)


def _terminate(state_dir, kill, sleep, clock, wait) -> bool:
    pid = read_pidfile(state_dir).get("pid")
    if isinstance(pid, int) and pid > 1:
        try:
            kill(pid, signal.SIGTERM)
        except OSError:
            pass
    return _wait_free(state_dir, sleep, clock, wait)


def start(state_dir, socket_path, main_path, popen=subprocess.Popen, kill=os.kill,
          sleep=time.sleep, clock=time.monotonic, wait=WAIT_S) -> str:
    state_dir = Path(state_dir)
    result = "started"
    if is_running(state_dir):
        if read_pidfile(state_dir).get("socket_path") == socket_path:
            return "running"
        if not _terminate(state_dir, kill, sleep, clock, wait):
            return "failed"
        result = "restarted"
    popen([sys.executable, str(main_path), "run"], start_new_session=True, close_fds=True,
          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result


def stop(state_dir, kill=os.kill, sleep=time.sleep, clock=time.monotonic, wait=WAIT_S) -> str:
    if not is_running(Path(state_dir)):
        return "stopped"
    return "stopped" if _terminate(Path(state_dir), kill, sleep, clock, wait) else "failed"


def status(state_dir, store) -> str:
    if not is_running(Path(state_dir)):
        return "stopped"
    info = read_pidfile(state_dir)
    tick = info.get("last_tick")
    when = datetime.fromtimestamp(tick, timezone.utc).strftime("%H:%M:%SZ") if isinstance(tick, (int, float)) else "none"
    panes = (store.load_published() or {}).get("panes", {})
    return f"running pid={info.get('pid')} last_tick={when} panes={len(panes)}"
