"""Cooperative stop flow (stop file) through FakeHost: runs on every OS."""

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.lifecycle import daemon  # noqa: E402
from tests.lifecycle.fake_host import FakeHost  # noqa: E402
from tests.lifecycle.test_daemon import Base  # noqa: E402

MAIN = Path("/x/main.py")


class StopWaitTest(Base):
    def run_stop(self, host, fn=daemon.stop, **kw):
        sleeps = []

        def sleep(s):
            sleeps.append(s)
            self.clock.t += s

        self.write_pid(4242)
        args = (self.dir,) if fn is daemon.stop else (self.dir, "/sock/b", MAIN)
        return fn(*args, host=host, sleep=sleep, clock=self.clock.now, **kw), sleeps

    def test_stop_polls_until_the_holder_frees(self):
        host = FakeHost(holder=4242, stop_file=True, free_after=3)
        result, sleeps = self.run_stop(host)
        self.assertEqual(result, "stopped")
        self.assertEqual(len(sleeps), 3)

    def test_stop_never_freed_fails_after_the_wait_budget(self):
        host = FakeHost(holder=4242, stop_file=True)
        result, sleeps = self.run_stop(host, wait=3)
        self.assertEqual(result, "failed")
        self.assertEqual(len(sleeps), 3)

    def test_restart_waits_then_spawns_once(self):
        host = FakeHost(holder=4242, stop_file=True, free_after=2)
        result, _ = self.run_stop(host, fn=daemon.start)
        self.assertEqual(result, "restarted")
        self.assertEqual([c for c in host.calls if c[0] == "spawn"], [("spawn", [str(MAIN), "run"])])

    def test_restart_never_freed_does_not_spawn(self):
        host = FakeHost(holder=4242, stop_file=True)
        result, _ = self.run_stop(host, fn=daemon.start, wait=2)
        self.assertEqual(result, "failed")
        self.assertFalse([c for c in host.calls if c[0] == "spawn"])

    def test_stop_without_holder_requests_nothing(self):
        host = FakeHost(stop_file=True)
        self.assertEqual(daemon.stop(self.dir, host=host), "stopped")
        self.assertFalse([c for c in host.calls if c[0] == "request_stop"])


class StatusStoppingTest(Base):
    def test_stopping_when_held_and_stop_requested(self):
        host = FakeHost(holder=4242, stop_file=True)
        self.write_pid(4242)
        host.stop_flag = True
        self.assertTrue(daemon.status(self.dir, self.store, host=host).startswith("stopping pid=4242"))

    def test_running_without_stop_request(self):
        host = FakeHost(holder=4242, stop_file=True)
        self.write_pid(4242)
        self.assertTrue(daemon.status(self.dir, self.store, host=host).startswith("running pid=4242"))

    def test_stale_stop_file_without_holder_is_stopped(self):
        host = FakeHost(stop_file=True)
        host.stop_flag = True
        self.assertEqual(daemon.status(self.dir, self.store, host=host), "stopped")


class PollerStopFileTest(Base):
    def test_stale_stop_file_is_cleared_after_the_lock_and_again_on_exit(self):
        host = FakeHost(stop_file=True)
        host.stop_flag = True  # left over from a crashed run
        ticks = []
        self.poller(lambda: ticks.append(1), host=host).run()
        self.assertEqual(len(ticks), 1)  # the stale request did not stop the new poller
        names = [c[0] for c in host.calls if c[0] in ("acquire_lock", "record_identity", "clear_stop", "release")]
        self.assertEqual(names, ["acquire_lock", "record_identity", "clear_stop", "clear_stop", "release"])

    def test_stop_request_ends_the_loop_between_ticks(self):
        host = FakeHost(stop_file=True)
        ticks = []

        def tick():
            ticks.append(1)
            host.stop_flag = True  # `stop` ran while this tick was in flight

        self.poller(tick, sleeps=1000, host=host).run()
        self.assertEqual(len(ticks), 1)

    def test_is_stopping_follows_the_host_and_latches(self):
        host = FakeHost(stop_file=True)
        p = self.poller(lambda: None, host=host)
        self.assertFalse(p.is_stopping())
        host.stop_flag = True
        self.assertTrue(p.is_stopping())
        host.stop_flag = False
        self.assertTrue(p.is_stopping())

    def test_posix_style_host_never_polls_for_stop(self):
        host = FakeHost()
        self.assertFalse(self.poller(lambda: None, host=host).is_stopping())

    def test_wait_wakes_in_slices_when_the_host_polls(self):
        host = FakeHost(stop_file=True, stop_poll_s=0.02)
        p = self.poller(lambda: None, host=host)
        threading.Timer(0.1, lambda: setattr(host, "stop_flag", True)).start()
        began = time.monotonic()
        p._wait(30.0)
        self.assertLess(time.monotonic() - began, 2.0)

    def test_wait_is_a_single_event_wait_without_stop_poll(self):
        p = self.poller(lambda: None, host=FakeHost())
        threading.Timer(0.1, p.request_stop).start()
        began = time.monotonic()
        p._wait(30.0)
        self.assertLess(time.monotonic() - began, 2.0)


if __name__ == "__main__":
    unittest.main()
