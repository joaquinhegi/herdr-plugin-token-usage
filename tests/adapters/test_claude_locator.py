import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters import log as tlog  # noqa: E402
from token_usage.adapters.claude_locator import ClaudeLocator  # noqa: E402

A = "1a1a1a1a-1111-4111-8bbb-111111111111"
B = "2b2b2b2b-2222-4222-8ccc-222222222222"


class LocatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.root = base / "projects"
        self.outside = base / "outside"
        self.root.mkdir()
        self.outside.mkdir()
        self.logdir = base / "logs"
        self.logger = tlog.make_logger(self.logdir, name="locator-" + base.name)
        self.addCleanup(tlog.close_logger, self.logger)
        self.locator = ClaudeLocator(self.root, self.logger)

    def touch(self, *parts, base=None):
        p = Path(base or self.root, *parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n")
        return p

    def log_lines(self):
        for h in self.logger.handlers:
            h.flush()
        f = self.logdir / "token-usage.log"
        return f.read_text().splitlines() if f.exists() else []

    def test_two_sessions_same_project_map_to_own_files(self):
        a = self.touch("-proj", f"{A}.jsonl")
        b = self.touch("-proj", f"{B}.jsonl")
        self.assertEqual(self.locator.locate(A).main, a)
        self.assertEqual(self.locator.locate(B).main, b)

    def test_subagents_are_read_next_to_the_resolved_main(self):
        """Main symlinked -p -> -q inside root: only -q's subagents belong to the session."""
        real = self.touch("-q", f"{A}.jsonl")
        (self.root / "-p").mkdir()
        (self.root / "-p" / f"{A}.jsonl").symlink_to(real)
        good = self.touch("-q", A, "subagents", "agent-a.jsonl")
        self.touch("-p", A, "subagents", "agent-z.jsonl")
        got = self.locator.locate(A)
        self.assertEqual((got.main, got.subagents), (real, [good]))

    def test_subagents_are_included_and_other_sessions_are_not(self):
        main = self.touch("-proj", f"{A}.jsonl")
        s1 = self.touch("-proj", A, "subagents", "agent-a.jsonl")
        s2 = self.touch("-proj", A, "subagents", "agent-b.jsonl")
        self.touch("-proj", B, "subagents", "agent-x.jsonl")
        self.touch("-proj", A, "subagents", "notes.jsonl")  # not an agent-* transcript
        got = self.locator.locate(A)
        self.assertEqual(got.main, main)
        self.assertEqual(sorted(got.subagents), [s1, s2])

    def test_missing_logs_one_safe_line(self):
        self.assertIsNone(self.locator.locate(A))
        lines = self.log_lines()
        self.assertEqual(len(lines), 1)
        self.assertNotIn(A, lines[0])
        self.assertNotIn(str(self.root), lines[0])

    def test_locate_failed_logs_only_when_outcome_changes(self):
        for _ in range(3):
            self.assertIsNone(self.locator.locate(A))
        self.assertEqual(len(self.log_lines()), 1)
        path = self.touch("-proj", f"{A}.jsonl")
        self.assertIsNotNone(self.locator.locate(A))
        path.unlink()
        self.assertIsNone(self.locator.locate(A))
        self.assertEqual(len(self.log_lines()), 2)

    def test_ambiguous_across_projects_is_none_with_one_line(self):
        self.touch("-p1", f"{A}.jsonl")
        self.touch("-p2", f"{A}.jsonl")
        self.assertIsNone(self.locator.locate(A))
        self.assertEqual(len(self.log_lines()), 1)

    def test_non_uuid_and_traversal_are_none(self):
        self.touch("-proj", f"{A}.jsonl")
        bad_inputs = ("../outside/x", "..", "-proj/secret", "*", A.upper(), A + "x", "")
        for bad in bad_inputs:  # each would resolve to a real file without the UUID guard
            self.touch("-proj", f"{bad}.jsonl")
        self.touch("outside", "x.jsonl")
        self.touch("-proj", "-proj", "secret.jsonl")
        for bad in bad_inputs:
            with self.subTest(bad=bad):
                self.assertIsNone(self.locator.locate(bad))

    def test_non_str_session_id_is_none(self):
        self.assertIsNone(self.locator.locate(None))
        self.assertIsNone(self.locator.locate(123))

    def test_in_root_main_symlink_to_other_session_is_none(self):
        b = self.touch("-proj", f"{B}.jsonl")
        os.symlink(b, self.root / "-proj" / f"{A}.jsonl")
        self.assertIsNone(self.locator.locate(A))
        self.assertEqual(self.locator.locate(B).main, b)

    def test_in_root_subagent_symlink_to_other_session_is_dropped(self):
        main = self.touch("-proj", f"{A}.jsonl")
        ok = self.touch("-proj", A, "subagents", "agent-a.jsonl")
        other = self.touch("-proj", B, "subagents", "agent-y.jsonl")
        os.symlink(other, ok.parent / "agent-x.jsonl")
        got = self.locator.locate(A)
        self.assertEqual(got.main, main)
        self.assertEqual(got.subagents, [ok])

    def test_ambiguous_does_not_leak_subagents(self):
        self.touch("-p1", f"{A}.jsonl")
        self.touch("-p2", f"{A}.jsonl")
        self.touch("-p2", A, "subagents", "agent-a.jsonl")
        self.assertIsNone(self.locator.locate(A))

    def test_main_symlink_escaping_root_is_none(self):
        target = self.touch("real.jsonl", base=self.outside)
        (self.root / "-proj").mkdir()
        os.symlink(target, self.root / "-proj" / f"{A}.jsonl")
        self.assertIsNone(self.locator.locate(A))

    def test_project_dir_symlink_escape_is_none(self):
        self.touch(f"{A}.jsonl", base=self.outside)
        os.symlink(self.outside, self.root / "-evil")
        self.assertIsNone(self.locator.locate(A))

    def test_escaping_subagent_symlink_is_dropped_only(self):
        main = self.touch("-proj", f"{A}.jsonl")
        ok = self.touch("-proj", A, "subagents", "agent-a.jsonl")
        leak = self.touch("leak.jsonl", base=self.outside)
        os.symlink(leak, ok.parent / "agent-leak.jsonl")
        got = self.locator.locate(A)
        self.assertEqual(got.main, main)
        self.assertEqual(got.subagents, [ok])

    def test_duplicate_subagent_symlink_in_same_dir_yields_one(self):
        self.touch("-proj", f"{A}.jsonl")
        a = self.touch("-proj", A, "subagents", "agent-a.jsonl")
        os.symlink(a, a.parent / "agent-dup.jsonl")
        self.assertEqual(self.locator.locate(A).subagents, [a])

    def test_project_dir_alias_to_same_file_is_not_ambiguous(self):
        main = self.touch("-proj", f"{A}.jsonl")
        os.symlink(self.root / "-proj", self.root / "-alias")
        got = self.locator.locate(A)
        self.assertIsNotNone(got)
        self.assertEqual(got.main, main)


if __name__ == "__main__":
    unittest.main()
