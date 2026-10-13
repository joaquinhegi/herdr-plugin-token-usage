import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.domain.ledger import Ledger  # noqa: E402
from token_usage.sources import claude, codex  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load(provider, name):
    """Yield decoded JSON objects, skipping undecodable lines like the tailer."""
    for line in (FIXTURES / provider / f"{name}.jsonl").read_text().splitlines():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def claude_total(name, ledger=None):
    ledger = ledger or Ledger()
    for obj in load("claude", name):
        parsed = claude.parse_line(obj)
        if parsed is not None:
            ledger.apply(*parsed, alias=claude.request_alias(obj))
    return ledger


class ClaudeParserTest(unittest.TestCase):
    def test_basic_total_and_thinking_not_added(self):
        self.assertEqual(claude_total("basic").total, 135 + 10 + 1150)

    def test_message_id_key_and_usage(self):
        obj = next(load("claude", "basic"))  # user line
        self.assertIsNone(claude.parse_line(obj))
        key, call = claude.parse_line(next(o for o in load("claude", "basic") if o["type"] == "assistant"))
        self.assertEqual(key, "msg_1")
        self.assertEqual((call.input, call.output, call.cache_creation, call.cache_read), (10, 20, 5, 100))
        self.assertEqual(call.thinking, 8)

    def test_duplicates_and_request_id_fallback(self):
        ledger = claude_total("duplicate_ids")
        self.assertEqual(ledger.entries["msg_d"], (10, 20, 0, 50))
        self.assertEqual(ledger.entries["req_only"], (3, 4, 5, 6))
        self.assertEqual(ledger.total, 80 + 18)

    def test_subagent_sidechain_lines_are_counted(self):
        ledger = claude_total("subagent")
        self.assertEqual(ledger.entries["msg_sub1"], (7, 3, 0, 90))
        self.assertEqual(ledger.total, 100 + 3)

    def test_request_id_only_duplicate_resolves_to_message_key(self):
        ledger = claude_total("alias")
        self.assertEqual(ledger.total, 5)  # not 5 + 5
        self.assertEqual(list(ledger.entries), ["msg_a"])
        self.assertEqual(ledger.aliases, {"req_a": "msg_a"})

    def test_skips_synthetic_error_and_idless(self):
        ledger = claude_total("synthetic_and_errors")
        self.assertEqual(list(ledger.entries), ["msg_ok"])
        self.assertEqual(ledger.total, 10)

    def test_resume_copy_and_replay_do_not_double_count(self):
        ledger = claude_total("basic")
        claude_total("resume_copy", ledger)
        self.assertEqual(ledger.total, 1295 + 28)
        claude_total("basic", ledger)
        self.assertEqual(ledger.total, 1295 + 28)

    def test_malformed_shapes_return_none(self):
        for obj in ({}, {"type": "assistant"}, {"type": "assistant", "message": "x"},
                    {"type": "assistant", "message": {"id": "m", "usage": "bad"}},
                    {"type": "assistant", "message": {"id": "m", "usage": {"input_tokens": "9"}}},
                    {"type": "assistant", "message": {"id": "m", "usage": {"input_tokens": True}}}):
            with self.subTest(obj=obj):
                self.assertIsNone(claude.parse_line(obj))


class CodexParserTest(unittest.TestCase):
    def test_snapshots_use_latest_not_sum(self):
        snaps = [s for s in map(codex.parse_line, load("codex", "snapshots")) if s]
        self.assertEqual([s.total for s in snaps], [100, 250, 250])
        self.assertEqual(codex.latest_total(load("codex", "snapshots")), 250)

    def test_null_info_ignored(self):
        self.assertEqual(codex.latest_total(load("codex", "null_info")), 100)
        self.assertIsNone(codex.parse_line(next(load("codex", "null_info"))))

    def test_no_snapshots_is_none_not_zero(self):
        self.assertIsNone(codex.latest_total([{"type": "session_meta"}]))

    def test_reasoning_and_cached_not_added_again(self):
        snap = codex.parse_line(
            {"type": "event_msg", "payload": {"type": "token_count", "info": {
                "total_token_usage": {"input_tokens": 150, "cached_input_tokens": 30,
                                      "output_tokens": 100, "reasoning_output_tokens": 20}}}})
        self.assertEqual(snap.total, 250)
        self.assertEqual(snap.reasoning_output, 20)


if __name__ == "__main__":
    unittest.main()
