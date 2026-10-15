"""WindowsHost: file-based parts run everywhere; the msvcrt lock tests run on Windows only."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from token_usage.lifecycle import host_windows  # noqa: E402
from token_usage.lifecycle.host_windows import WindowsHost  # noqa: E402
from tests.support import child_env, time_limit  # noqa: E402

nt_only = unittest.skipUnless(os.name == "nt", "msvcrt byte-range locking is Windows-only")

HOLDER = """
import os, sys, time
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from token_usage.lifecycle.host_windows import WindowsHost
host = WindowsHost()
handle = host.acquire_lock(Path(sys.argv[2]))
assert handle is not None
host.record_identity(handle, os.getpid())
print("ready", flush=True)
time.sleep(120)
"""


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        time_limit(self)
        self.dir = Path(tmp.name)
        self.host = WindowsHost()


class StopFileTest(Base):
    def test_request_stop_creates_the_stop_file_ignoring_pid(self):
        self.assertFalse(self.host.stop_requested(self.dir))
        self.host.request_stop(self.dir, None)
        self.assertTrue((self.dir / "poller.stop").exists())
        self.assertTrue(self.host.stop_requested(self.dir))

    def test_clear_stop_is_idempotent(self):
        self.host.request_stop(self.dir, 123)
        self.host.clear_stop(self.dir)
        self.host.clear_stop(self.dir)
        self.assertFalse(self.host.stop_requested(self.dir))

    def test_capabilities(self):
        self.assertFalse(self.host.supports_socket)
        self.assertEqual(self.host.stop_poll_s, 0.5)

    def test_request_stop_names_the_poller(self):  # W1
        self.host.request_stop(self.dir, 4242, 1000.5)
        self.assertEqual(json.loads((self.dir / "poller.stop").read_text()), {"pid": 4242, "started_at": 1000.5})
        self.host.request_stop(self.dir, None)  # unverified pid: the file still exists but names nobody
        self.assertTrue(self.host.stop_requested(self.dir))

    def test_clear_stop_keeps_only_a_request_naming_the_caller(self):
        self.host.request_stop(self.dir, 4242, 1000.5)
        self.host.clear_stop(self.dir, (4242, 1000.5))
        self.assertTrue(self.host.stop_requested(self.dir))
        for other in ((4243, 1000.5), (4242, 999.0)):  # another pid, or a recycled pid of an older run
            self.host.clear_stop(self.dir, other)
            self.assertFalse(self.host.stop_requested(self.dir))
            self.host.request_stop(self.dir, 4242, 1000.5)
        for junk in ("", "not json", "[]", '{"pid": "4242"}'):
            (self.dir / "poller.stop").write_text(junk)
            self.host.clear_stop(self.dir, (4242, 1000.5))
            self.assertFalse(self.host.stop_requested(self.dir))
        self.host.clear_stop(self.dir, (4242, 1000.5))  # missing file: no error


class SpawnTest(Base):
    def test_spawn_flags_and_argv(self):
        calls = []
        WindowsHost(popen=lambda *a, **kw: calls.append((a, kw))).spawn(["/x/main.py", "run"])
        (args, kw), = calls
        self.assertEqual(args[0], [sys.executable, "-X", "utf8", "-B", "/x/main.py", "run"])
        self.assertEqual(kw["creationflags"], 0x00000200 | 0x08000000)  # NEW_PROCESS_GROUP | NO_WINDOW
        self.assertIs(kw["close_fds"], True)
        for k in ("stdin", "stdout", "stderr"):
            self.assertEqual(kw[k], subprocess.DEVNULL)
        self.assertFalse(kw.get("shell"))
        self.assertNotIn("start_new_session", kw)


class SignalTest(Base):
    def test_int_and_break_stop_and_hup_is_not_touched(self):
        stops, registered = [], {}
        fake = mock.Mock(SIGINT=2, SIGBREAK=21, SIGTERM=15, SIGHUP=1, spec=["SIGINT", "SIGBREAK", "SIGTERM", "SIGHUP", "signal"])
        fake.signal = lambda sig, fn: registered.__setitem__(sig, fn)
        with mock.patch.object(host_windows, "signal", fake):
            self.host.install_signal_handlers(lambda: stops.append(1))
        self.assertEqual(sorted(registered), [2, 21])  # S2: neither SIGTERM (15) nor SIGHUP (1)
        for fn in registered.values():
            fn(0, None)
        self.assertEqual(len(stops), 2)

    def test_missing_sigbreak_is_skipped(self):
        registered = {}
        fake = mock.Mock(SIGINT=2, SIGTERM=15, SIGHUP=1, spec=["SIGINT", "SIGTERM", "SIGHUP", "signal"])
        fake.signal = lambda sig, fn: registered.__setitem__(sig, fn)
        with mock.patch.object(host_windows, "signal", fake):
            self.host.install_signal_handlers(lambda: None)
        self.assertEqual(sorted(registered), [2])  # SIGTERM/SIGHUP present on the module but untouched


@nt_only
class LockTest(Base):
    def test_second_lock_fails_until_release_and_release_wipes_identity(self):
        handle = self.host.acquire_lock(self.dir)
        self.assertIsNotNone(handle)
        self.assertIsNone(WindowsHost().acquire_lock(self.dir))
        self.assertTrue(self.host.held(self.dir))
        self.host.record_identity(handle, 4242)
        self.assertEqual(self.host.holder_pid(self.dir), 4242)
        self.host.release(handle)
        self.assertIsNone(self.host.holder_pid(self.dir))
        self.assertFalse(self.host.held(self.dir))

    def test_identity_lives_at_offset_16_outside_the_locked_byte(self):
        handle = self.host.acquire_lock(self.dir)
        self.addCleanup(self.host.release, handle)
        self.host.record_identity(handle, 4242)
        with open(self.dir / "poller.lock", "rb") as fh:  # a second handle, byte 0 is locked
            fh.seek(host_windows.PID_OFFSET)
            self.assertEqual(int(fh.read().strip()), 4242)

    def test_probe_wipes_a_stale_identity_when_it_wins(self):
        (self.dir / "poller.lock").write_bytes(b"\0" * 16 + b"4242")
        self.assertEqual(self.host.holder_pid(self.dir), 4242)
        self.assertFalse(self.host.held(self.dir))
        self.assertIsNone(self.host.holder_pid(self.dir))


@nt_only
class CrossProcessTest(Base):
    def test_live_holder_blocks_and_a_killed_holder_frees_the_lock(self):
        proc = subprocess.Popen([sys.executable, "-B", "-c", HOLDER, str(SRC), str(self.dir)],
                                stdout=subprocess.PIPE, env=child_env(), text=True)
        self.addCleanup(proc.stdout.close)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        self.assertEqual(proc.stdout.readline().strip(), "ready")
        self.assertIsNone(self.host.acquire_lock(self.dir))
        self.assertTrue(self.host.held(self.dir))
        self.assertEqual(self.host.holder_pid(self.dir), proc.pid)  # readable from another process
        proc.kill()  # crash: no release, no cleanup
        proc.wait(timeout=10)
        self.assertFalse(self.host.held(self.dir))
        self.assertIsNone(self.host.holder_pid(self.dir))  # the winning probe wiped the stale pid
        handle = self.host.acquire_lock(self.dir)
        self.assertIsNotNone(handle)
        self.host.release(handle)


@nt_only
class RealTerminateTest(Base):
    """Real OpenProcess/GetProcessTimes/TerminateProcess against a child that holds the lock."""

    def start_holder(self):
        proc = subprocess.Popen([sys.executable, "-B", "-c", HOLDER, str(SRC), str(self.dir)],
                                stdout=subprocess.PIPE, env=child_env(), text=True)
        self.addCleanup(proc.stdout.close)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        self.assertEqual(proc.stdout.readline().strip(), "ready")
        return proc, self.host.holder_pid(self.dir)

    def test_matching_child_is_terminated_and_frees_the_lock(self):
        proc, pid = self.start_holder()
        self.assertTrue(self.host.force_terminate(self.dir, pid, time.time()))
        proc.wait(timeout=10)
        self.assertFalse(self.host.held(self.dir))

    def test_started_at_mismatch_leaves_the_child_alive(self):
        proc, pid = self.start_holder()
        for started in (time.time() - 3600, time.time() + 3600):  # process "created after", and far outside 60 s
            self.assertFalse(self.host.force_terminate(self.dir, pid, started))
        self.assertIsNone(proc.poll())
        self.assertTrue(self.host.held(self.dir))

    def test_pid_that_is_not_the_lock_holder_is_refused(self):
        proc, pid = self.start_holder()
        self.assertFalse(self.host.force_terminate(self.dir, pid + 4, time.time()))
        self.assertIsNone(proc.poll())

    def test_liveness_and_stop_never_use_os_kill(self):
        from token_usage.lifecycle import daemon
        proc, _ = self.start_holder()
        with mock.patch.object(os, "kill", side_effect=AssertionError("os.kill")):
            self.assertTrue(daemon.is_running(self.dir))
            self.assertEqual(daemon.stop(self.dir, sleep=lambda s: None, wait=0), "failed")  # no pidfile: no pid, no force
        self.assertIsNone(proc.poll())


if __name__ == "__main__":
    unittest.main()
