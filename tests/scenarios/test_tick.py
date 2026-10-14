import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters import log as tlog  # noqa: E402
from token_usage.adapters.claude_locator import ClaudeLocator  # noqa: E402
from token_usage.adapters.jsonl_tail import JsonlTail  # noqa: E402
from token_usage.adapters.state_store import StateStore  # noqa: E402
from token_usage.app.tick import SOURCE, TOKEN, TickService  # noqa: E402
from token_usage.ports import HerdrError  # noqa: E402

A = "1a1a1a1a-1111-4111-8bbb-111111111111"
B = "2b2b2b2b-2222-4222-8ccc-222222222222"
SECRET = "SENTINEL-prompt-text"


def line(mid, total):
    usage = {"input_tokens": 1, "output_tokens": total - 1}
    msg = {"id": mid, "model": "m", "usage": usage, "content": SECRET}
    return json.dumps({"type": "assistant", "message": msg}) + "\n"


def claude_pane(pane_id, sid):
    return {"pane_id": pane_id, "agent_session": {"source": "herdr:claude", "agent": "claude", "kind": "id", "value": sid}}


class FakeClock:
    def __init__(self):
        self.t = 1_000.0

    def now(self):
        return self.t


class FakeHerdr:
    def __init__(self):
        self.panes, self.calls, self.fail_list, self.fail_pane = [], [], False, set()

    def list_panes(self):
        if self.fail_list:
            raise HerdrError("down")
        return self.panes

    def report(self, pane_id, source, token, value, seq, ttl_ms):
        if pane_id in self.fail_pane:
            raise HerdrError("boom")
        self.calls.append(("report", pane_id, source, token, value, ttl_ms))

    def clear(self, pane_id, source, token, seq):
        if pane_id in self.fail_pane:
            raise HerdrError("boom")
        self.calls.append(("clear", pane_id, source, token))


class RaisingTail(JsonlTail):
    def __init__(self, bad):
        super().__init__()
        self.bad = bad

    def read(self, path, position):
        if self.bad in path.name:
            raise OSError("corrupt")
        return super().read(path, position)


class TickTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        (self.base / "projects" / "-proj").mkdir(parents=True)
        self.logger = tlog.make_logger(self.base / "logs", name="tick-" + self.base.name)
        self.addCleanup(tlog.close_logger, self.logger)
        self.herdr, self.clock = FakeHerdr(), FakeClock()
        self.svc = self.service()

    def service(self, tailer=None):
        return TickService(self.herdr, ClaudeLocator(self.base / "projects", self.logger), tailer or JsonlTail(),
                           StateStore(self.base / "state"), self.clock, self.logger)

    def write(self, sid, *lines, mode="a"):
        with open(self.base / "projects" / "-proj" / f"{sid}.jsonl", mode) as fh:
            fh.write("".join(lines))

    def published(self):
        return (StateStore(self.base / "state").load_published() or {}).get("panes", {})

    def take(self):
        calls, self.herdr.calls = self.herdr.calls, []
        return calls

    def test_two_sessions_in_two_panes_have_independent_totals(self):
        """session-mapping: Same repo, two sessions."""
        self.write(A, line("m1", 1200))
        self.write(B, line("m1", 950))
        self.herdr.panes = [claude_pane("p1", A), claude_pane("p2", B)]
        self.svc.tick()
        self.assertEqual(self.take(), [("report", "p1", SOURCE, TOKEN, "1.2k tokens", 60000),
                                       ("report", "p2", SOURCE, TOKEN, "950 tokens", 60000)])

    def test_total_grows_after_new_lines(self):
        """usage-accounting: Growing file."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.take()
        self.write(A, line("m2", 1300))
        self.svc.tick()
        self.assertEqual([c[4] for c in self.take()], ["2.5k tokens"])

    def test_resume_after_restart_does_not_double_count(self):
        """session-mapping: Resume after restart."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.take()
        self.svc = self.service()  # new process, same persisted state
        self.svc.tick()
        self.assertEqual(self.take(), [])  # same total, within refresh window
        self.write(A, line("m2", 300))
        self.svc.tick()
        self.assertEqual([c[4] for c in self.take()], ["1.5k tokens"])

    def test_session_change_in_same_pane_starts_from_new_usage(self):
        """session-mapping: New session in same pane."""
        self.write(A, line("m1", 1200))
        self.write(B, line("m1", 950))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.herdr.panes = [claude_pane("p1", B)]
        self.take()
        self.svc.tick()
        self.assertEqual([c[4] for c in self.take()], ["950 tokens"])

    def test_corrupt_session_is_skipped_and_other_is_published(self):
        """plugin-lifecycle: Corrupt transcript."""
        self.write(A, line("m1", 1200))
        self.write(B, line("m1", 950))
        self.herdr.panes = [claude_pane("p1", A), claude_pane("p2", B)]
        self.service(RaisingTail(A)).tick()
        self.assertEqual([c[1] for c in self.take()], ["p2"])
        self.assertEqual(list(self.published()), ["p2"])

    def test_herdr_unreachable_changes_nothing(self):
        """sidebar-metadata: Herdr unreachable."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        before, self.herdr.fail_list = self.published(), True
        self.take()
        self.svc.tick()
        self.assertEqual((self.take(), self.published()), ([], before))

    def test_failed_publish_is_not_recorded_and_is_retried(self):
        """sidebar-metadata: Herdr unreachable (publish failure, retried)."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.herdr.fail_pane = {"p1"}
        self.svc.tick()
        self.assertEqual(self.published(), {})
        self.herdr.fail_pane = set()
        self.svc.tick()
        self.assertEqual([c[:2] for c in self.take()], [("report", "p1")])
        self.assertIn("p1", self.published())

    def test_failed_clear_keeps_record_for_retry(self):
        """sidebar-metadata: publish/clear (clear failure, retried)."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.herdr.panes, self.herdr.fail_pane = [{"pane_id": "p1", "agent": "codex"}], {"p1"}
        self.svc.tick()
        self.assertIn("p1", self.published())
        self.herdr.fail_pane = set()
        self.take()
        self.svc.tick()
        self.assertEqual([c[:2] for c in self.take()], [("clear", "p1")])

    def test_codex_unmapped_and_malformed_panes_publish_nothing(self):
        """session-mapping: Codex pane / No reliable session."""
        self.write(A, line("m1", 1200))
        bad = {"source": "herdr:claude", "agent": "claude", "kind": "id", "value": "../etc"}
        self.herdr.panes = [
            claude_pane("p1", A),
            {"pane_id": "p2", "agent": "codex", "agent_session": {"source": "herdr:codex", "kind": "id", "value": B}},
            {"pane_id": "p3"},
            {"pane_id": "p4", "agent_session": bad},
        ]
        self.svc.tick()
        self.assertEqual([c[1] for c in self.take()], ["p1"])

    def test_previously_published_pane_that_becomes_unmapped_is_cleared(self):
        """session-mapping: loss of reliable mapping clears."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.herdr.panes = [{"pane_id": "p1", "agent": "codex"}]
        self.take()
        self.svc.tick()
        self.assertEqual([c[:2] for c in self.take()], [("clear", "p1")])
        self.assertEqual(self.published(), {})

    def test_empty_or_missing_session_shows_nothing(self):
        """session-mapping: Missing file; design: Empty session is never 0."""
        self.write(B, "not json\n")
        self.herdr.panes = [claude_pane("p1", A), claude_pane("p2", B)]
        self.svc.tick()
        self.assertEqual((self.take(), self.published()), ([], {}))

    def test_closed_pane_is_forgotten_and_other_is_unaffected(self):
        """sidebar-metadata: Pane closed."""
        self.write(A, line("m1", 1200))
        self.write(B, line("m1", 950))
        self.herdr.panes = [claude_pane("p1", A), claude_pane("p2", B)]
        self.svc.tick()
        self.herdr.panes = [claude_pane("p2", B)]
        self.take()
        self.svc.tick()
        self.assertEqual((self.take(), list(self.published())), ([], ["p2"]))

    def test_unchanged_value_refreshes_only_after_20s_with_ttl(self):
        """sidebar-metadata: Unchanged value."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.take()
        self.clock.t += 19
        self.svc.tick()
        self.assertEqual(self.take(), [])
        self.clock.t += 1
        self.svc.tick()
        self.assertEqual(self.take(), [("report", "p1", SOURCE, TOKEN, "1.2k tokens", 60000)])

    def test_content_and_paths_never_reach_state_or_logs(self):
        """plugin-lifecycle: Content never stored."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        for h in self.logger.handlers:
            h.flush()
        for f in (p for p in self.base.rglob("*") if p.is_file() and "projects" not in p.parts):
            text = f.read_text()
            self.assertNotIn(SECRET, text)
            self.assertNotIn("-proj", text)


if __name__ == "__main__":
    unittest.main()
