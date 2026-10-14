import json
import os
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


class CountingTail(JsonlTail):
    def __init__(self):
        super().__init__()
        self.reads = []  # (file name, stored position passed in, objects returned)

    def read(self, path, position):
        result = super().read(path, position)
        self.reads.append((path.name, position, len(result.objects)))
        return result


class SaveFails(StateStore):
    def __init__(self, root, which):
        super().__init__(root)
        self.which = which

    def save_published(self, state):
        if self.which == "published":
            raise OSError("disk full")
        return super().save_published(state)

    def save_session(self, sid, state):
        if self.which == "session":
            raise OSError("disk full")
        return super().save_session(sid, state)


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

    def write_sub(self, sid, name, *lines):
        d = self.base / "projects" / "-proj" / sid / "subagents"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text("".join(lines))

    def log_text(self):
        for h in self.logger.handlers:
            h.flush()
        return (self.base / "logs" / "token-usage.log").read_text()

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

    def test_stop_during_sessions_aborts_tick_without_publishing(self):
        self.write(A, line("m1", 1200))
        self.write(B, line("m1", 950))
        self.herdr.panes = [claude_pane("p1", A), claude_pane("p2", B)]
        self.svc.should_stop = lambda: True
        self.svc.tick()
        self.assertEqual(self.take(), [])
        self.assertEqual(self.published(), {})

    def test_stop_between_publish_actions_keeps_unapplied_for_retry(self):
        self.write(A, line("m1", 1200))
        self.write(B, line("m1", 950))
        self.herdr.panes = [claude_pane("p1", A), claude_pane("p2", B)]
        stop = []
        orig = self.herdr.report
        self.herdr.report = lambda *a: (orig(*a), stop.append(1))[0]
        self.svc.should_stop = lambda: bool(stop)
        self.svc.tick()
        self.assertEqual(len(self.take()), 1)
        self.assertEqual(list(self.published()), ["p1"])  # p2 unapplied: retried next tick
        self.svc.should_stop = lambda: False
        self.svc.tick()
        self.assertEqual([c[1] for c in self.take()], ["p2"])

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
        log = self.log_text()
        self.assertIn(f"session_failed error=OSError session={A[:8]}", log)
        self.assertNotIn(A, log)  # only the 8-char prefix is ever logged

    @unittest.skipIf(os.geteuid() == 0, "root ignores file permissions")
    def test_unreadable_transcript_shows_nothing_and_clears(self):
        """session-mapping: No reliable session, no figure (unreadable main or subagent)."""
        self.write(A, line("m1", 1200))
        self.write_sub(A, "agent-1.jsonl", line("m2", 300))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.assertEqual(self.published()["p1"]["value"], "1.5k tokens")
        root = self.base / "projects" / "-proj"
        for target in (root / f"{A}.jsonl", root / A / "subagents" / "agent-1.jsonl"):
            self.take()
            target.chmod(0)
            self.addCleanup(target.chmod, 0o600)
            self.svc.tick()  # whole session unavailable: never a partial undercount
            self.assertEqual(([c[:2] for c in self.take()], self.published()), ([("clear", "p1")], {}))
            target.chmod(0o600)
            self.svc.tick()
            self.assertEqual([c[4] for c in self.take()], ["1.5k tokens"])
        log = self.log_text()
        self.assertEqual(log.count("transcript_unreadable"), 2)
        self.assertNotIn(A, log)
        self.assertNotIn("-proj", log)

    @unittest.skipIf(os.geteuid() == 0, "root ignores file permissions")
    def test_unreadable_transcript_logs_only_on_change(self):
        self.write(A, line("m1", 1200))
        target = self.base / "projects" / "-proj" / f"{A}.jsonl"
        self.herdr.panes = [claude_pane("p1", A)]
        target.chmod(0)
        self.addCleanup(target.chmod, 0o600)
        for _ in range(3):
            self.svc.tick()
        self.assertEqual(self.log_text().count("transcript_unreadable"), 1)

    def test_tick_reports_herdr_reachability(self):
        self.assertTrue(self.svc.tick())
        self.herdr.fail_list = True
        self.assertFalse(self.svc.tick())

    def test_disallowed_subagent_name_is_ignored_and_session_still_saves(self):
        self.write(A, line("m1", 1200))
        self.write_sub(A, "agent-a b.jsonl", line("s1", 500))
        self.write_sub(A, "agent-a..b.jsonl", line("s2", 500))
        self.herdr.panes = [claude_pane("p1", A)]
        self.svc.tick()
        self.assertEqual(self.take(), [("report", "p1", SOURCE, TOKEN, "1.2k tokens", 60000)])
        self.assertEqual(list(StateStore(self.base / "state").load_session(A)["files"]), ["main"])

    def test_old_disallowed_file_key_is_dropped_and_session_saves(self):
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        store = StateStore(self.base / "state")
        path = store._session_path(A)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"v": 1, "last_seen": 1.0, "ledger": {}, "aliases": {},
                                    "files": {"subagents/agent-a b.jsonl": {"offset": 1}, "subagents/agent-gone.jsonl": {"offset": 1}}}))
        self.svc.tick()
        self.assertEqual(list(store.load_session(A)["files"]), ["main"])

    def test_real_interrupted_error_from_herdr_is_a_publish_failure_not_stop(self):
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]

        def boom(*a):
            raise InterruptedError("EINTR")

        self.herdr.report = boom
        self.svc.tick()
        self.assertIn("apply_failed error=InterruptedError", self.log_text())

    def test_save_failures_do_not_escape_tick(self):
        """plugin-lifecycle: store failures are contained."""
        self.write(A, line("m1", 1200))
        self.herdr.panes = [claude_pane("p1", A)]
        for which in ("session", "published"):
            self.svc.store = SaveFails(self.base / which, which)
            self.svc.tick()
            self.assertNotEqual(self.take(), [])
            self.assertIn(f"save_{which}_failed error=OSError", self.log_text())

    def test_session_state_wiring_survives_restart(self):
        """usage-accounting: persisted offsets, aliases, subagents, last_seen and seq are really used."""
        self.write(A, line("m1", 1200).replace('"message"', '"requestId": "r1", "message"'))
        self.write_sub(A, "agent-1.jsonl", line("m2", 300))
        self.herdr.panes = [claude_pane("p1", A)]
        tail = CountingTail()
        self.svc = self.service(tail)
        self.svc.tick()
        store = StateStore(self.base / "state")
        saved, root = store.load_session(A), self.base / "projects" / "-proj"
        sizes = {"main": (root / f"{A}.jsonl").stat().st_size, "subagents/agent-1.jsonl": (root / A / "subagents" / "agent-1.jsonl").stat().st_size}
        self.assertEqual({k: v["offset"] for k, v in saved["files"].items()}, sizes)
        self.assertEqual((saved["aliases"], saved["last_seen"], sorted(saved["ledger"])), ({"r1": "m1"}, 1000.0, ["m1", "m2"]))
        seq1 = store.load_published()["seq"]
        self.take()
        tail, self.clock.t = CountingTail(), self.clock.t + 20  # restart, refresh due
        self.svc = self.service(tail)
        self.write(A, json.dumps({"type": "assistant", "requestId": "r1", "message": {"model": "m", "usage": {"input_tokens": 1, "output_tokens": 1199}}}) + "\n")
        self.svc.tick()
        # only the appended line is read; the requestId-only line maps to m1 via the persisted alias
        self.assertEqual(sorted((n, p is not None, c) for n, p, c in tail.reads), [(f"{A}.jsonl", True, 1), ("agent-1.jsonl", True, 0)])
        self.assertEqual([c[4] for c in self.take()], ["1.5k tokens"])
        tail, self.clock.t = CountingTail(), 500.0  # restart with the clock moved back
        self.service(tail).tick()
        self.assertGreater(StateStore(self.base / "state").load_published()["seq"], seq1)

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
