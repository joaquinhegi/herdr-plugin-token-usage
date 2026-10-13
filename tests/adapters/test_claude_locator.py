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

    def test_subagents_are_included_and_other_sessions_are_not(self):
        main = self.touch("-proj", f"{A}.jsonl")
        s1 = self.touch("-proj", A, "subagents", "agent-a.jsonl")
        s2 = self.touch("-proj", A, "subagents", "agent-b.jsonl")
        self.touch("-proj", B, "subagents", "agent-x.jsonl")
        got = self.locator.locate(A)
        self.assertEqual(got.main, main)
        self.assertEqual(sorted(got.subagents), [s1, s2])

    def test_missing_logs_one_safe_line(self):
        self.assertIsNone(self.locator.locate(A))
        lines = self.log_lines()
        self.assertEqual(len(lines), 1)
        self.assertNotIn(A, lines[0])
        self.assertNotIn(str(self.root), lines[0])

    def test_ambiguous_across_projects_is_none_with_one_line(self):
        self.touch("-p1", f"{A}.jsonl")
        self.touch("-p2", f"{A}.jsonl")
        self.assertIsNone(self.locator.locate(A))
        self.assertEqual(len(self.log_lines()), 1)

    def test_non_uuid_and_traversal_are_none(self):
        self.touch("-proj", "secret.jsonl")
        self.touch("-proj", f"{A}.jsonl")
        for bad in ("../outside/x", "..", "-proj/secret", "*", A.upper(), A + "x", ""):
            with self.subTest(bad=bad):
                self.assertIsNone(self.locator.locate(bad))

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


if __name__ == "__main__":
    unittest.main()
