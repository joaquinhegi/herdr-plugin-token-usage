import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters import log as tlog  # noqa: E402
from token_usage.adapters.state_store import StateStore  # noqa: E402
from token_usage.lifecycle import daemon  # noqa: E402
from token_usage.lifecycle.host_posix import PosixHost  # noqa: E402
from token_usage.lifecycle.host_windows import WindowsHost  # noqa: E402
from tests.support import child_env, posix_only, time_limit  # noqa: E402

MAIN = Path(__file__).resolve().parents[2] / "src" / "main.py"


class FakeClock:
    def __init__(self):
        self.t = 1_000.0

    def now(self):
        return self.t


class FakeHerdr:
    def __init__(self):
        self.cleared = []

    def clear(self, pane_id, source, token, seq):
        self.cleared.append((pane_id, source, token, seq))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)  # registered first, so it runs last (LIFO)
        time_limit(self)
        self.dir = Path(self.tmp.name)
        self.logger = tlog.make_logger(self.dir / "logs", "t_daemon_%d" % id(self))
        self.addCleanup(tlog.close_logger, self.logger)
        self.store, self.clock, self.herdr = StateStore(self.dir), FakeClock(), FakeHerdr()
        self.host = WindowsHost() if os.name == "nt" else PosixHost()
        self._held = set()

    def poller(self, tick, sleeps=1, **kw):
        box = {}

        def sleep(_s):
            self.clock.t += kw.get("step", 4)
            box["n"] = box.get("n", 0) + 1
            if box["n"] >= sleeps:
                box["p"].request_stop()

        p = daemon.Poller(self.dir, "/sock/a", tick, self.herdr, self.store, self.clock, self.logger,
                          sleep=sleep, orphan_after=kw.get("orphan_after", 300),
                          lock_sleep=kw.get("lock_sleep", lambda s: None), mono=kw.get("mono", time.monotonic),
                          host=kw.get("host") or self.host)
        box["p"] = p
        return p

    def hold_lock(self, pid=None):
        """Hold the lock like a probe; with pid, like a daemon that recorded itself as the holder."""
        handle = self.host.acquire_lock(self.dir)
        self._held.add(handle)
        if pid is not None:
            self.host.record_identity(handle, pid)
        self.addCleanup(self.release_lock, handle)
        return handle

    def release_lock(self, handle):
        if handle in self._held:
            self._held.remove(handle)
            self.host.release(handle)

    def write_pid(self, pid, sock="/sock/a"):
        (self.dir / daemon.PID).write_text(json.dumps({"pid": pid, "socket_path": sock, "started_at": 1.0, "last_tick": 2.0}))


class TestRun(Base):
    def test_second_run_exits_zero_without_ticking(self):
        self.hold_lock()
        calls = []
        self.assertEqual(self.poller(lambda: calls.append(1)).run(), 0)
        self.assertEqual(calls, [])

    def test_stale_pidfile_replaced(self):
        self.write_pid(2_999_999)
        seen = []
        self.poller(lambda: seen.append(json.loads((self.dir / daemon.PID).read_text())["pid"])).run()
        self.assertEqual(seen, [os.getpid()])

    def test_tick_exception_keeps_loop_running(self):
        calls = []

        def tick():
            calls.append(1)
            raise RuntimeError("boom")

        self.poller(tick, sleeps=3).run()
        self.assertEqual(len(calls), 3)

    def test_stop_request_during_slow_tick_ends_run_within_bound(self):
        import threading
        from token_usage.adapters.claude_locator import ClaudeLocator
        from token_usage.adapters.jsonl_tail import JsonlTail
        from token_usage.app.tick import TickService
        from tests.scenarios.test_tick import A, FakeHerdr as TickHerdr, claude_pane, line

        projects = self.dir / "projects" / "-p"
        projects.mkdir(parents=True)
        (projects / f"{A}.jsonl").write_text(line("m1", 100))
        herdr = TickHerdr()
        herdr.panes = [claude_pane(f"p{i}", A) for i in range(20)]
        orig = herdr.report
        herdr.report = lambda *a: (time.sleep(0.2), orig(*a))[1]  # 20 panes x 0.2 s = 4 s tick
        svc = TickService(herdr, ClaudeLocator(self.dir / "projects", self.logger), JsonlTail(), self.store,
                          self.clock, self.logger)
        p = daemon.Poller(self.dir, "/sock/a", svc.tick, herdr, self.store, self.clock, self.logger, host=self.host)
        svc.should_stop = p.is_stopping
        threading.Timer(0.5, p.request_stop).start()
        began = time.monotonic()
        self.assertEqual(p.run(), 0)
        self.assertLess(time.monotonic() - began, 2.0)

    def test_stop_clears_published_persists_and_removes_pidfile(self):
        self.store.save_published({"seq": 5, "panes": {"p1": {"session": "s", "value": "1k", "at": 1.0}}})
        self.poller(lambda: True).run()
        self.assertEqual(len(self.herdr.cleared), 1)
        pane, source, token, seq = self.herdr.cleared[0]
        self.assertEqual((pane, source, token), ("p1", "token-usage", "tokens"))
        self.assertGreater(seq, 5)
        self.assertEqual(self.store.load_published()["panes"], {})
        self.assertFalse((self.dir / daemon.PID).exists())

    def test_orphan_guard_exits_after_threshold(self):
        calls = []
        self.poller(lambda: calls.append(1) or False, sleeps=1000, orphan_after=300, step=100).run()
        self.assertEqual(len(calls), 4)  # t=0,100,200,300 -> 300s unreachable

    def test_recovery_resets_orphan_timer(self):
        results = iter([False, False, True] + [False] * 2)
        calls = []
        self.poller(lambda: calls.append(1) or next(results), sleeps=5, orphan_after=300, step=100).run()
        self.assertEqual(len(calls), 5)


class TestRunHardening(Base):
    def test_run_retries_lock_so_a_probe_collision_leaves_a_poller(self):
        fd = self.hold_lock()
        sleeps, calls = [], []

        def lock_sleep(s):
            sleeps.append(s)
            if len(sleeps) == 3:
                self.release_lock(fd)  # the probe finishes

        self.poller(lambda: calls.append(1), lock_sleep=lock_sleep).run()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(sleeps), 3)

    def test_run_gives_up_after_bounded_retries(self):
        self.hold_lock()
        sleeps = []
        self.assertEqual(self.poller(lambda: None, lock_sleep=sleeps.append).run(), 0)
        self.assertTrue(0 < len(sleeps) <= 20)
        self.assertLessEqual(sum(sleeps), 2.0)

    def test_prune_at_startup_and_hourly(self):
        pruned = []
        self.store.prune = pruned.append
        self.poller(lambda: True, sleeps=3, step=2000).run()  # t=1000, 3000, 5000
        self.assertEqual(pruned, [1000.0, 5000.0])

    @posix_only  # SIGHUP does not exist on Windows
    def test_signal_handlers(self):
        for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            self.addCleanup(signal.signal, sig, signal.getsignal(sig))
        p = self.poller(lambda: True)
        p.install_signals()
        self.assertEqual(signal.getsignal(signal.SIGHUP), signal.SIG_IGN)
        for sig in (signal.SIGINT, signal.SIGTERM):
            p._stop.clear()
            signal.getsignal(sig)(sig, None)
            self.assertTrue(p._stop.is_set())

    def test_cleanup_is_bounded_by_total_deadline(self):
        now = {"t": 0.0}
        panes = {f"p{i}": {"session": "s", "value": "1k", "at": 1.0} for i in range(10)}
        self.store.save_published({"seq": 1, "panes": panes})
        self.herdr.clear = lambda *a: (self.herdr.cleared.append(a), now.__setitem__("t", now["t"] + 1.0))
        self.poller(lambda: True, mono=lambda: now["t"]).run()
        self.assertLess(len(self.herdr.cleared), 10)
        self.assertEqual(self.store.load_published()["panes"], {})
        self.assertFalse((self.dir / daemon.PID).exists())

    def test_wait_exceeds_worst_case_cleanup(self):
        self.assertGreaterEqual(daemon.WAIT_S, daemon.CLEANUP_S + 4.0 + 1.0)


class FakePopen:
    calls = []

    def __init__(self, *a, **kw):
        FakePopen.calls.append((a, kw))


@posix_only  # real PosixHost flock; WindowsHost parity lands in slice 2a
class TestStart(Base):
    def setUp(self):
        super().setUp()
        FakePopen.calls = []

    def start(self, sock="/sock/a", kill=None):
        return daemon.start(self.dir, sock, MAIN, popen=FakePopen, kill=kill or (lambda *a: None),
                            sleep=lambda s: None, clock=self.clock.now)

    def test_spawn_argv_and_kwargs(self):
        self.assertEqual(self.start(), "started")
        (args, kwargs), = FakePopen.calls
        self.assertEqual(args[0], [sys.executable, "-B", str(MAIN), "run"])
        self.assertIs(kwargs["start_new_session"], True)
        self.assertIs(kwargs["close_fds"], True)
        for k in ("stdin", "stdout", "stderr"):
            self.assertEqual(kwargs[k], subprocess.DEVNULL)
        self.assertFalse(kwargs.get("shell"))

    def test_stale_pidfile_spawns(self):
        self.write_pid(2_999_999)
        self.assertEqual(self.start(), "started")
        self.assertEqual(len(FakePopen.calls), 1)

    def test_live_same_socket_is_noop(self):
        self.hold_lock(os.getpid())
        self.write_pid(os.getpid())
        self.assertEqual(self.start(), "running")
        self.assertEqual(FakePopen.calls, [])

    def test_changed_socket_terminates_then_respawns(self):
        fd = self.hold_lock(4242)
        self.write_pid(4242)
        sent = []

        def kill(pid, sig):
            sent.append((pid, sig))
            self.release_lock(fd)  # the old daemon exits and drops its lock

        self.assertEqual(self.start("/sock/b", kill), "restarted")
        self.assertEqual(sent, [(4242, signal.SIGTERM)])
        self.assertEqual(len(FakePopen.calls), 1)

    def test_unverified_pid_is_never_signaled(self):
        sent = []
        victim = subprocess.Popen(["sleep", "30"])
        self.addCleanup(victim.wait)
        self.addCleanup(victim.kill)
        self.hold_lock()  # a probe (or a daemon not yet recorded) holds the lock
        self.write_pid(victim.pid)
        daemon.stop(self.dir, kill=lambda p, s: sent.append(p), sleep=lambda s: None,
                    clock=self.clock.now, wait=0)
        self.assertEqual(sent, [])
        self.assertIsNone(victim.poll())

    def test_lock_file_pid_mismatch_is_not_signaled(self):
        self.hold_lock(111)
        self.write_pid(222)
        sent = []
        daemon.stop(self.dir, kill=lambda p, s: sent.append(p), sleep=lambda s: None, clock=self.clock.now, wait=0)
        self.assertEqual(sent, [])

    def test_unsafe_pids_are_never_signaled(self):
        for pid in (0, 1, -1, os.getpid()):
            fd = self.hold_lock(pid)
            self.write_pid(pid)
            sent = []
            daemon.stop(self.dir, kill=lambda p, s: sent.append(p), sleep=lambda s: None, clock=self.clock.now, wait=0)
            self.assertEqual(sent, [], pid)
            self.release_lock(fd)

    def test_probe_clears_stale_lock_file_pid(self):
        (self.dir / daemon.LOCK).write_text("4242")  # daemon was SIGKILLed
        self.assertFalse(daemon.is_running(self.dir))
        self.assertEqual((self.dir / daemon.LOCK).read_text(), "")

    def test_changed_socket_wait_is_bounded(self):
        self.hold_lock(4242)
        self.write_pid(4242)
        sleeps = []

        def sleep(s):
            sleeps.append(s)
            self.clock.t += 1

        result = daemon.start(self.dir, "/sock/b", MAIN, popen=FakePopen, kill=lambda *a: None,
                              sleep=sleep, clock=self.clock.now)
        self.assertEqual(result, "failed")
        self.assertLessEqual(len(sleeps), 10)
        self.assertEqual(FakePopen.calls, [])


class TestStatus(Base):
    def test_status_shows_only_pid_tick_and_count(self):
        self.hold_lock()
        self.write_pid(4242, sock="/very/secret/sock")
        self.store.save_published({"seq": 1, "panes": {"p1": {}, "p2": {}}})
        out = daemon.status(self.dir, self.store, host=self.host)
        self.assertIn("pid=4242", out)
        self.assertIn("panes=2", out)
        self.assertNotIn("/", out.replace("1970-01-01", ""))
        self.assertNotIn("secret", out)

    def test_status_stopped(self):
        self.assertEqual(daemon.status(self.dir, self.store, host=self.host), "stopped")


@posix_only  # real flock daemon + shebang fake bin; Windows gets its own in slice 2a/2b
class TestRealSpawn(unittest.TestCase):
    def test_start_status_stop_and_missing_env(self):
        time_limit(self, 60)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)  # first registered, last run: killpid below runs before it
        tmp = Path(tmp.name)
        fake = tmp / "herdr"
        fake.write_text("#!/bin/sh\necho '[]'\n")
        fake.chmod(0o755)
        state = tmp / "state"
        env = child_env(HOME=str(tmp), HERDR_SOCKET_PATH=str(tmp / "no.sock"),
                        HERDR_PLUGIN_STATE_DIR=str(state), HERDR_BIN_PATH=str(fake))

        def killpid():
            try:
                os.kill(json.loads((state / daemon.PID).read_text())["pid"], signal.SIGKILL)
            except (OSError, ValueError, KeyError):
                pass

        self.addCleanup(killpid)

        def run(cmd, e=env):
            return subprocess.run([sys.executable, "-B", str(MAIN), cmd], env=e, capture_output=True, text=True, timeout=20)

        bad = run("start", child_env())
        self.assertNotEqual(bad.returncode, 0)
        self.assertNotIn("Traceback", bad.stderr)
        self.assertEqual(run("start").returncode, 0)
        pidfile = state / daemon.PID
        for _ in range(100):
            if pidfile.exists() and "last_tick" in pidfile.read_text():
                break
            time.sleep(0.1)
        self.assertIn("running", run("status").stdout)
        self.assertEqual(run("stop").returncode, 0)
        self.assertIn("stopped", run("status").stdout)
        self.assertFalse((state / daemon.PID).exists())


if __name__ == "__main__":
    unittest.main()
