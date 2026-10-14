import sys
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters import log as tlog  # noqa: E402
from token_usage.adapters.jsonl_tail import JsonlTail  # noqa: E402
from token_usage.adapters.state_store import StateStore  # noqa: E402
from token_usage.domain.ledger import Ledger  # noqa: E402
from token_usage.sources import claude  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "claude"
SENTINEL = "SENTINEL_SECRET_PROMPT_TEXT"


class LogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.logger = tlog.make_logger(self.root / "logs", "t_" + self.root.name)
        self.addCleanup(tlog.close_logger, self.logger)

    def text(self):
        for h in self.logger.handlers:
            h.flush()
        return "".join(p.read_text() for p in (self.root / "logs").iterdir())

    def test_make_logger_twice_adds_no_duplicate_handler(self):
        again = tlog.make_logger(self.root / "logs", self.logger.name)
        self.assertIs(again, self.logger)
        self.assertEqual(len(self.logger.handlers), 1)

    def test_rotation_settings(self):
        handler = self.logger.handlers[0]
        self.assertIsInstance(handler, RotatingFileHandler)
        self.assertEqual((handler.maxBytes, handler.backupCount), (256 * 1024, 1))

    def test_token_with_trailing_newline_is_redacted(self):
        tlog.log_event(self.logger, "tick", session="x\n")
        self.assertIn("session=?", self.text())

    def test_event_fields_are_ints_or_safe_tokens_only(self):
        tlog.log_event(self.logger, "tick", lines=3, session="11111111", path="/Users/me/x.jsonl",
                       msg="hello there")
        out = self.text()
        self.assertIn("tick", out)
        self.assertIn("lines=3", out)
        self.assertIn("session=11111111", out)
        for leaked in ("/Users", "hello"):
            self.assertNotIn(leaked, out)

    def test_exception_logs_type_only(self):
        tlog.log_exception(self.logger, "parse_failed", ValueError(f"{SENTINEL} /etc/passwd"))
        out = self.text()
        self.assertIn("ValueError", out)
        self.assertNotIn(SENTINEL, out)
        self.assertNotIn("/etc", out)

    def test_sentinel_never_reaches_state_or_logs(self):
        store = StateStore(self.root / "state")
        for name in ("basic", "duplicate_ids", "subagent", "alias"):
            path = FIXTURES / f"{name}.jsonl"
            result = JsonlTail().read(path, None)
            ledger = Ledger()
            for obj in result.objects:
                parsed = claude.parse_line(obj)
                if parsed:
                    ledger.apply(*parsed, alias=claude.request_alias(obj))
            tlog.log_event(self.logger, "tick", lines=len(result.objects), undecodable=result.undecodable)
            sid = f"{len(name):08d}-2222-3333-4444-555555555555"
            store.save_session(sid, {"provider": "claude", "last_seen": 1, "total": ledger.total,
                                     "files": {"main": result.position},
                                     "ledger": ledger.entries, "aliases": ledger.aliases})
        scanned = [p for d in (self.root / "state", self.root / "logs") for p in d.rglob("*") if p.is_file()]
        self.assertTrue(scanned)
        for p in scanned:
            self.assertNotIn(SENTINEL, p.read_text())
            self.assertNotIn(str(FIXTURES), p.read_text())


if __name__ == "__main__":
    unittest.main()
