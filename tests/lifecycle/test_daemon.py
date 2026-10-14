import fcntl
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
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.logger = tlog.make_logger(self.dir / "logs", "t_daemon_%d" % id(self))
        self.addCleanup(tlog.close_logger, self.logger)
        self.store, self.clock, self.herdr = StateStore(self.dir), FakeClock(), FakeHerdr()

    def poller(self, tick, sleeps=1, **kw):
        box = {}

        def sleep(_s):
            self.clock.t += kw.get("step", 4)
            box["n"] = box.get("n", 0) + 1
            if box["n"] >= sleeps:
                box["p"].request_stop()

        p = daemon.Poller(self.dir, "/sock/a", tick, self.herdr, self.store, self.clock, self.logger,
                          sleep=sleep, orphan_after=kw.get("orphan_after", 300))
        box["p"] = p
        return p

    def hold_lock(self):
        fd = os.open(self.dir / daemon.LOCK, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(lambda: Path(f"/dev/fd/{fd}").exists() and self._close(fd))
        return fd

    @staticmethod
    def _close(fd):
        try:
            os.close(fd)
        except OSError:
            pass

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


class FakePopen:
    calls = []

    def __init__(self, *a, **kw):
        FakePopen.calls.append((a, kw))


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
        self.assertEqual(args[0], [sys.executable, str(MAIN), "run"])
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
        self.hold_lock()
        self.write_pid(os.getpid())
        self.assertEqual(self.start(), "running")
        self.assertEqual(FakePopen.calls, [])

    def test_changed_socket_terminates_then_respawns(self):
        fd = self.hold_lock()
        self.write_pid(4242)
        sent = []

        def kill(pid, sig):
            sent.append((pid, sig))
            os.close(fd)  # the old daemon exits and drops its lock

        self.assertEqual(self.start("/sock/b", kill), "restarted")
        self.assertEqual(sent, [(4242, signal.SIGTERM)])
        self.assertEqual(len(FakePopen.calls), 1)

    def test_changed_socket_wait_is_bounded(self):
        self.hold_lock()
        self.write_pid(4242)
        sleeps = []

        def sleep(s):
            sleeps.append(s)
            self.clock.t += 1

        result = daemon.start(self.dir, "/sock/b", MAIN, popen=FakePopen, kill=lambda *a: None,
                              sleep=sleep, clock=self.clock.now)
        self.assertEqual(result, "failed")
        self.assertLessEqual(len(sleeps), 6)
        self.assertEqual(FakePopen.calls, [])


class TestStatus(Base):
    def test_status_shows_only_pid_tick_and_count(self):
        self.hold_lock()
        self.write_pid(4242, sock="/very/secret/sock")
        self.store.save_published({"seq": 1, "panes": {"p1": {}, "p2": {}}})
        out = daemon.status(self.dir, self.store)
        self.assertIn("pid=4242", out)
        self.assertIn("panes=2", out)
        self.assertNotIn("/", out.replace("1970-01-01", ""))
        self.assertNotIn("secret", out)

    def test_status_stopped(self):
        self.assertEqual(daemon.status(self.dir, self.store), "stopped")


class TestRealSpawn(unittest.TestCase):
    def test_start_status_stop_and_missing_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake = tmp / "herdr"
            fake.write_text("#!/bin/sh\necho '[]'\n")
            fake.chmod(0o755)
            state = tmp / "state"
            env = {"PATH": os.environ["PATH"], "HOME": str(tmp), "HERDR_SOCKET_PATH": str(tmp / "no.sock"),
                   "HERDR_PLUGIN_STATE_DIR": str(state), "HERDR_BIN_PATH": str(fake)}

            def killpid():
                try:
                    os.kill(json.loads((state / daemon.PID).read_text())["pid"], signal.SIGKILL)
                except (OSError, ValueError, KeyError):
                    pass

            self.addCleanup(killpid)

            def run(cmd, e=env):
                return subprocess.run([sys.executable, str(MAIN), cmd], env=e, capture_output=True, text=True, timeout=20)

            bad = run("start", {"PATH": os.environ["PATH"]})
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
