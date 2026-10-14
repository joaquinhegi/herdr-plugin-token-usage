import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.lifecycle import daemon  # noqa: E402
from tests.lifecycle.fake_host import FakeHost  # noqa: E402

MAIN = Path("/x/main.py")


class HostInjectionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write_pid(self, pid, sock="/sock/a"):
        (self.dir / daemon.PID).write_text(json.dumps({"pid": pid, "socket_path": sock, "started_at": 1.0}))

    def test_start_spawns_through_host(self):
        host = FakeHost()
        self.assertEqual(daemon.start(self.dir, "/sock/a", MAIN, host=host), "started")
        self.assertIn(("spawn", [str(MAIN), "run"]), host.calls)

    def test_start_same_socket_is_running_noop(self):
        host = FakeHost(holder=4242)
        self.write_pid(4242)
        self.assertEqual(daemon.start(self.dir, "/sock/a", MAIN, host=host), "running")
        self.assertFalse([c for c in host.calls if c[0] == "spawn"])

    def test_stop_requests_stop_with_verified_pid(self):
        host = FakeHost(holder=4242)
        self.write_pid(4242)
        self.assertEqual(daemon.stop(self.dir, host=host, sleep=lambda s: None), "stopped")
        self.assertIn(("request_stop", 4242), host.calls)

    def test_stop_passes_no_pid_when_identity_unverified(self):
        host = FakeHost(holder=111)
        self.write_pid(222)
        daemon.stop(self.dir, host=host, sleep=lambda s: None, wait=0)
        self.assertIn(("request_stop", None), host.calls)

    def test_status_uses_host_probe(self):
        host = FakeHost(holder=4242)
        self.write_pid(4242)

        class Store:
            def load_published(self):
                return {"panes": {}}

        self.assertIn("running pid=4242", daemon.status(self.dir, Store(), host=host))
        self.assertEqual(daemon.status(self.dir, Store(), host=FakeHost()), "stopped")

    def test_poller_run_uses_host_lock_and_identity(self):
        host = FakeHost()

        class Clock:
            def now(self):
                return 1.0

        class Store:
            def prune(self, now): return 0
            def load_published(self): return {}
            def save_published(self, s): return True

        p = daemon.Poller(self.dir, "", lambda: True, None, Store(), Clock(), None, sleep=lambda s: p.request_stop(),
                          host=host)
        self.assertEqual(p.run(), 0)
        names = [c[0] for c in host.calls]
        self.assertEqual(names[0], "acquire_lock")
        self.assertIn("record_identity", names)
        self.assertEqual(names[-1], "release")


if __name__ == "__main__":
    unittest.main()
