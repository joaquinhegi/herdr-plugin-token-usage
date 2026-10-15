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


class ForceTerminateFlowTest(StopWaitTest):
    def test_force_runs_after_the_cooperative_budget_with_pid_and_started_at(self):
        host = FakeHost(holder=4242, stop_file=True, force_result=True, free_on_force=True)
        result, sleeps = self.run_stop(host, wait=3)
        self.assertEqual(result, "stopped")
        self.assertEqual(len(sleeps), 3)  # 3 cooperative polls; the force wait finds the lock already free
        self.assertEqual([c for c in host.calls if c[0] == "force_terminate"], [("force_terminate", 4242, 1.0)])

    def test_force_that_does_not_free_the_lock_fails_after_two_seconds(self):
        host = FakeHost(holder=4242, stop_file=True, force_result=True)
        result, sleeps = self.run_stop(host, wait=3)
        self.assertEqual(result, "failed")
        self.assertEqual(len(sleeps), 3 + 2)  # FORCE_WAIT_S = 2 s, one-second polls

    def test_refused_force_does_not_wait_again(self):
        host = FakeHost(holder=4242, stop_file=True)
        result, sleeps = self.run_stop(host, wait=3)
        self.assertEqual((result, len(sleeps)), ("failed", 3))
        self.assertEqual(len([c for c in host.calls if c[0] == "force_terminate"]), 1)

    def test_no_force_when_the_poller_exits_cooperatively(self):
        host = FakeHost(holder=4242, stop_file=True, free_after=1, force_result=True)
        self.assertEqual(self.run_stop(host)[0], "stopped")
        self.assertFalse([c for c in host.calls if c[0] == "force_terminate"])

    def test_no_force_without_a_verified_pid(self):
        host = FakeHost(holder=999, stop_file=True, force_result=True)  # pidfile says 4242
        self.assertEqual(self.run_stop(host, wait=2)[0], "failed")
        self.assertFalse([c for c in host.calls if c[0] == "force_terminate"])

    def test_restart_forces_a_stuck_poller_too(self):
        host = FakeHost(holder=4242, stop_file=True, force_result=True, free_on_force=True)
        result, _ = self.run_stop(host, fn=daemon.start, wait=2)
        self.assertEqual(result, "restarted")
        self.assertEqual([c for c in host.calls if c[0] == "spawn"], [("spawn", [str(MAIN), "run"])])


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

    def test_a_stop_request_made_after_the_startup_timestamp_survives(self):  # W1: stop racing a restart
        host = FakeHost(stop_file=True)
        host.stop_flag, host.stop_mtime = True, 200.0
        p = self.poller(lambda: self.fail("must not tick"), host=host, wall=lambda: 100.0)
        p.run()
        self.assertIn(("clear_stop", 100.0), host.calls)  # conditional clear, stamped before acquire_lock
        self.assertLess(host.calls.index(("acquire_lock",)), host.calls.index(("clear_stop", 100.0)))

    def test_a_stop_file_older_than_the_timestamp_is_cleared(self):
        host = FakeHost(stop_file=True)
        host.stop_flag, host.stop_mtime = True, 50.0
        ticks = []
        self.poller(lambda: ticks.append(1), host=host, wall=lambda: 100.0).run()
        self.assertEqual(len(ticks), 1)

    def test_the_wall_stamp_is_taken_before_acquire_lock(self):
        order = []
        host = FakeHost(stop_file=True)
        orig = host.acquire_lock
        host.acquire_lock = lambda d: (order.append("acquire"), orig(d))[1]
        self.poller(lambda: None, host=host, wall=lambda: order.append("stamp") or 1.0).run()
        self.assertEqual(order[:2], ["stamp", "acquire"])

    def test_clear_stop_failure_cannot_skip_the_lock_release(self):  # S1
        host = FakeHost(stop_file=True)
        host.clear_error = PermissionError("denied")
        ticks = []
        self.assertEqual(self.poller(lambda: ticks.append(1), host=host).run(), 0)
        self.assertEqual(len(ticks), 1)
        self.assertEqual(host.calls[-1], ("release",))
        self.assertEqual(len([c for c in host.calls if c[0] == "clear_stop"]), 2)

    def test_default_sleep_is_the_cooperative_wait(self):  # W2: no injected sleep
        host = FakeHost(stop_file=True, stop_poll_s=0.02)
        p = daemon.Poller(self.dir, "/sock/a", lambda: threading.Timer(0.1, lambda: setattr(host, "stop_flag", True)).start(),
                          self.herdr, self.store, self.clock, self.logger, interval=30.0, host=host)
        self.assertEqual(p._sleep.__func__, daemon.Poller._wait)
        began = time.monotonic()
        p.run()
        self.assertLess(time.monotonic() - began, 5.0)

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
