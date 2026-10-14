import json
import sys
import logging
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters.herdr_cli import HerdrCli  # noqa: E402
from token_usage.adapters.herdr_fallback import FallbackHerdr  # noqa: E402
from token_usage.adapters.herdr_socket import HerdrSocket  # noqa: E402
from tests.adapters.herdr_fakes import FakeServer, fixture_panes, make_fake_bin, ok_handler  # noqa: E402
from tests.support import posix_only  # noqa: E402


@posix_only  # executes the shebang fake bin; Windows CLI gets real tests with the .exe work
class FallbackTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cli = HerdrCli(str(make_fake_bin(self.dir)))
        self.logger = logging.getLogger("fallback_test")
        self.logger.handlers[:] = []

    def test_attribute_error_from_missing_transport_falls_back_to_cli(self):
        class NoSocket:
            def list_panes(self):
                raise AttributeError("module 'socket' has no attribute 'AF_UNIX'")

        fb = FallbackHerdr(NoSocket(), self.cli, self.logger)
        with self.assertLogs(self.logger, "INFO") as cm:
            self.assertEqual(fb.list_panes(), fixture_panes())
        self.assertEqual(cm.records[0].getMessage().count("AttributeError"), 1)

    def test_socket_failure_falls_back_per_call_and_retries_socket(self):
        calls = []

        def h(req, conn):
            calls.append(1)
            if len(calls) == 1:
                conn.sendall(b"garbage")
            else:
                ok_handler(req, conn)

        srv = FakeServer(h)
        self.addCleanup(srv.close)
        fb = FallbackHerdr(HerdrSocket(srv.path), self.cli, self.logger)
        with self.assertLogs(self.logger, "INFO") as cm:
            self.assertEqual(fb.list_panes(), fixture_panes())
        self.assertEqual(len(cm.records), 1)
        self.assertIn("herdr_fallback", cm.records[0].getMessage())
        self.assertEqual(json.loads((self.dir / "argv.json").read_text()), ["pane", "list"])
        (self.dir / "argv.json").unlink()
        self.assertEqual(fb.list_panes(), fixture_panes())
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.dir / "argv.json").exists())

    def test_no_socket_uses_cli_and_report_always_cli(self):
        fb = FallbackHerdr(None, self.cli, self.logger)
        self.assertEqual(fb.list_panes(), fixture_panes())
        fb.report("w1:p1", "src", "usage", "v", 1, 1000)
        self.assertEqual(json.loads((self.dir / "argv.json").read_text())[:2], ["pane", "report-metadata"])
        fb.clear("w1:p1", "src", "usage", 2)
        self.assertIn("--clear-token", json.loads((self.dir / "argv.json").read_text()))


if __name__ == "__main__":
    unittest.main()
