"""WindowsHost: file-based parts run everywhere; the msvcrt lock tests run on Windows only."""

import os
import subprocess
import sys
import tempfile
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

    def test_force_terminate_is_deferred_to_the_guarded_implementation(self):
        self.assertFalse(self.host.force_terminate(self.dir))


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
        fake = mock.Mock(SIGINT=2, SIGBREAK=21, spec=["SIGINT", "SIGBREAK", "signal"])
        fake.signal = lambda sig, fn: registered.__setitem__(sig, fn)
        with mock.patch.object(host_windows, "signal", fake):
            self.host.install_signal_handlers(lambda: stops.append(1))
        self.assertEqual(sorted(registered), [2, 21])
        for fn in registered.values():
            fn(0, None)
        self.assertEqual(len(stops), 2)

    def test_missing_sigbreak_is_skipped(self):
        registered = {}
        fake = mock.Mock(SIGINT=2, spec=["SIGINT", "signal"])
        fake.signal = lambda sig, fn: registered.__setitem__(sig, fn)
        with mock.patch.object(host_windows, "signal", fake):
            self.host.install_signal_handlers(lambda: None)
        self.assertEqual(sorted(registered), [2])


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


if __name__ == "__main__":
    unittest.main()
