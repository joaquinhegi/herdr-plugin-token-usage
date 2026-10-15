"""WindowsHost.force_terminate guard logic against a fake Win32 layer: runs on every OS."""

import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.lifecycle.host_posix import PosixHost  # noqa: E402
from token_usage.lifecycle.host_windows import WindowsHost  # noqa: E402

ACCESS = 0x1000 | 0x0001  # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE
STARTED = 1_000_000.0


class FakeWin32:
    def __init__(self, handle=7, created=STARTED - 5, ok=True, times_error=None):
        self.handle, self.created, self.ok, self.times_error = handle, created, ok, times_error
        self.calls = []

    def open_process(self, access, pid):
        self.calls.append(("open", access, pid))
        return self.handle

    def creation_time(self, handle):
        self.calls.append(("times", handle))
        if self.times_error:
            raise self.times_error
        return self.created

    def terminate(self, handle):
        self.calls.append(("terminate", handle))
        return self.ok

    def close(self, handle):
        self.calls.append(("close", handle))


class StubHost(WindowsHost):
    """Lock state is stubbed: msvcrt is Windows-only; the real lock is covered in CI."""

    def __init__(self, win32, held=True, holder=4242):
        super().__init__(win32=win32)
        self._held, self._holder = held, holder

    def held(self, d):
        return self._held

    def holder_pid(self, d):
        return self._holder


class GuardTest(unittest.TestCase):
    def test_creation_window_boundaries_are_inclusive(self):  # WC1: created == started_at, and exactly 60 s
        self.assertTrue(self.go(created=STARTED)[0])
        self.assertTrue(self.go(created=STARTED - 60.0)[0])
        self.assertFalse(self.go(created=STARTED + 0.001)[0])
        self.assertFalse(self.go(created=STARTED - 60.001)[0])

    def test_win32_errors_are_a_refusal_logged_by_type_and_the_handle_is_closed(self):  # S7
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            result, calls = self.go(times_error=OSError("boom /secret/path"))
        self.assertFalse(result)
        self.assertEqual(calls[-1], ("close", 7))
        self.assertNotIn(("terminate", 7), calls)
        self.assertIn("OSError", err.getvalue())
        self.assertNotIn("secret", err.getvalue())

    def test_a_failing_win32_layer_is_a_refusal(self):
        class Broken:
            def open_process(self, *a):
                raise OSError("no kernel32")
        host = StubHost(Broken())
        self.assertFalse(host.force_terminate(Path("/state"), 4242, STARTED))

    def go(self, pid=4242, started=STARTED, **kw):
        win32 = FakeWin32(**{k: v for k, v in kw.items() if k in ("handle", "created", "ok", "times_error")})
        host = StubHost(win32, **{k: v for k, v in kw.items() if k in ("held", "holder")})
        with mock.patch.object(os, "kill", side_effect=AssertionError("os.kill must never be used")):
            return host.force_terminate(Path("/state"), pid, started), win32.calls

    def test_matching_identity_terminates_the_same_handle_then_closes_it(self):
        result, calls = self.go()
        self.assertTrue(result)
        self.assertEqual(calls, [("open", ACCESS, 4242), ("times", 7), ("terminate", 7), ("close", 7)])

    def test_refused_before_any_handle_is_opened(self):
        me = os.getpid()
        cases = {"holder differs": dict(holder=4243), "no holder": dict(holder=None), "lock not held": dict(held=False),
                 "pid 1": dict(pid=1, holder=1), "pid 0": dict(pid=0, holder=0), "own pid": dict(pid=me, holder=me),
                 "bool pid": dict(pid=True, holder=True), "no pid": dict(pid=None, holder=None),
                 "no started_at": dict(started=None), "str started_at": dict(started="1.0")}
        for name, kw in cases.items():
            with self.subTest(name):
                result, calls = self.go(**kw)
                self.assertFalse(result)
                self.assertEqual(calls, [])

    def test_creation_time_guard_is_bounded_on_both_sides(self):
        cases = [(STARTED + 0.001, False), (STARTED + 10, False), (STARTED - 60.001, False), (STARTED - 3600, False),
                 (STARTED, True), (STARTED - 60, True), (STARTED - 0.5, True)]
        for created, expected in cases:
            with self.subTest(created=created - STARTED):
                result, calls = self.go(created=created)
                self.assertEqual(result, expected)
                self.assertEqual(("terminate", 7) in calls, expected)
                self.assertEqual(calls[-1], ("close", 7))  # the handle is always closed

    def test_failed_open_neither_terminates_nor_closes(self):
        for handle in (None, 0):
            result, calls = self.go(handle=handle)
            self.assertFalse(result)
            self.assertEqual(calls, [("open", ACCESS, 4242)])

    def test_unknown_creation_time_refuses(self):
        result, calls = self.go(created=None)
        self.assertFalse(result)
        self.assertEqual(calls, [("open", ACCESS, 4242), ("times", 7), ("close", 7)])

    def test_terminate_failure_reports_false_and_closes(self):
        result, calls = self.go(ok=False)
        self.assertFalse(result)
        self.assertEqual(calls[-2:], [("terminate", 7), ("close", 7)])


class PosixForceTest(unittest.TestCase):
    def test_posix_host_never_force_terminates(self):
        killed = []
        host = PosixHost(kill=lambda *a: killed.append(a))
        self.assertFalse(host.force_terminate(Path("/state"), 4242, STARTED))
        self.assertEqual(killed, [])


if __name__ == "__main__":
    unittest.main()
