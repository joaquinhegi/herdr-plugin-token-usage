import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from token_usage.lifecycle import sidebar_patch as sp

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "src" / "main.py"

CUSTOM = '''[ui.sidebar.agents]
rows = [
  ["state_icon", "workspace"],
  ["agent"],
]

[ui.sidebar.agents.rows_by_agent]
claude = [
  ["agent", "tab"],  # keep me
  ["cwd"],
]
codex = [["agent"]]
'''
ROWS_ONLY = '[ui.sidebar.agents]\nrows = [["agent", "tab"], ["cwd"]]\n'


def added(diff):
    return [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.cfg = self.dir / "config.toml"

    def write(self, text):
        self.cfg.write_text(text)
        return text


class TestPlan(Base):
    def test_custom_claude_row_only_adds_tokens(self):
        text = self.write(CUSTOM)
        res = sp.plan(self.cfg)
        self.assertEqual(res.status, "patch")
        self.assertEqual(added(res.diff), ['  ["cwd", "$tokens"],'])
        new = tomllib.loads(res.new_text)
        old = tomllib.loads(text)
        old["ui"]["sidebar"]["agents"]["rows_by_agent"]["claude"][-1].append("$tokens")
        self.assertEqual(new, old)
        self.assertIn("# keep me", res.new_text)

    def test_rows_fallback_when_no_claude_override(self):
        res = sp.plan(self.write(ROWS_ONLY) and self.cfg)
        self.assertEqual(res.status, "patch")
        self.assertEqual(tomllib.loads(res.new_text)["ui"]["sidebar"]["agents"]["rows"][-1], ["cwd", "$tokens"])

    def test_trailing_comma_row(self):
        self.write('[ui.sidebar.agents]\nrows = [["a",]]\n')
        self.assertEqual(tomllib.loads(sp.plan(self.cfg).new_text)["ui"]["sidebar"]["agents"]["rows"], [["a", "$tokens"]])

    def test_already_patched_is_noop(self):
        self.write(ROWS_ONLY.replace('"cwd"', '"cwd", "$tokens"'))
        res = sp.plan(self.cfg)
        self.assertEqual((res.status, res.diff), ("noop", ""))

    def test_refuses_when_unsafe(self):
        for text in (
            "[ui.sidebar.agents]\nspacing = 1\n",  # section exists, no rows
            "[ui.sidebar.agents]\nrows_by_agent = { claude = [[\"a\"]] }\n",  # inline table
            "[ui.sidebar.agents]\nrows = [[\"a\"]]\nrows = []\n",  # invalid TOML
            "[ui.sidebar.agents]\nrows = []\n",  # no inner row to extend
            "[ui.sidebar.agents]\nrows = [[\"\"\"a\"\"\"]]\n",  # multiline string
        ):
            with self.subTest(text=text):
                self.write(text)
                res = sp.plan(self.cfg)
                self.assertEqual(res.status, "refuse")
                self.assertIn("manual", res.message.lower())

    def test_missing_file_and_missing_section_add_minimal_section(self):
        res = sp.plan(self.cfg)
        self.assertEqual(res.status, "patch")
        self.assertIn("/dev/null", res.diff)
        self.assertEqual(tomllib.loads(res.new_text)["ui"]["sidebar"]["agents"]["rows"], [["agent", "$tokens"]])
        text = self.write('[ui]\ntheme = "x"')  # no trailing newline
        res = sp.plan(self.cfg)
        self.assertTrue(res.new_text.startswith(text + "\n"))
        self.assertEqual(tomllib.loads(res.new_text)["ui"]["theme"], "x")

    def test_plan_writes_nothing(self):
        names = sorted(os.listdir(self.dir))
        sp.plan(self.cfg)  # missing file
        self.write(CUSTOM)
        before = (self.cfg.read_bytes(), self.cfg.stat().st_mtime_ns)
        sp.plan(self.cfg)
        self.assertEqual(sorted(os.listdir(self.dir)), ["config.toml"])
        self.assertEqual((self.cfg.read_bytes(), self.cfg.stat().st_mtime_ns), before)
        self.assertEqual(names, [])


class TestApply(Base):
    def test_backup_then_atomic_replace(self):
        self.write(CUSTOM)
        self.cfg.chmod(0o640)
        self.assertEqual(sp.apply(self.cfg), 0)
        backups = [p for p in self.dir.iterdir() if p.name.startswith("config.toml.bak-")]
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), CUSTOM)
        self.assertEqual(len(list(self.dir.iterdir())), 2)  # no temp files left
        self.assertIn('["cwd", "$tokens"]', self.cfg.read_text())
        self.assertEqual(self.cfg.stat().st_mode & 0o777, 0o640)

    def test_apply_refusal_changes_nothing(self):
        self.write("[ui.sidebar.agents]\nspacing = 1\n")
        self.assertNotEqual(sp.apply(self.cfg), 0)
        self.assertEqual(sorted(os.listdir(self.dir)), ["config.toml"])
        self.assertEqual(self.cfg.read_text(), "[ui.sidebar.agents]\nspacing = 1\n")

    def test_apply_noop_and_missing_file(self):
        self.assertEqual(sp.apply(self.cfg), 0)  # creates, nothing to back up
        self.assertEqual(os.listdir(self.dir), ["config.toml"])
        self.assertEqual(sp.apply(self.cfg), 0)  # second run: already patched, no new backup
        self.assertEqual(os.listdir(self.dir), ["config.toml"])


class TestCli(Base):
    def run_cli(self, *args):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.dir)}
        return subprocess.run([sys.executable, "-B", str(MAIN), "sidebar-patch", *args], env=env,
                              capture_output=True, text=True, timeout=20)

    def test_print_and_apply_via_main(self):
        self.write(ROWS_ONLY)
        r = self.run_cli("--print", "--config", str(self.cfg))
        self.assertEqual(r.returncode, 0)
        self.assertIn('+rows = [["agent", "tab"], ["cwd", "$tokens"]]', r.stdout)
        self.assertEqual(self.cfg.read_text(), ROWS_ONLY)
        self.assertEqual(self.run_cli("--apply", "--config", str(self.cfg)).returncode, 0)
        self.assertIn("$tokens", self.cfg.read_text())

    def test_refusal_and_usage_exit_nonzero(self):
        self.write("[ui.sidebar.agents]\n")
        r = self.run_cli("--print", "--config", str(self.cfg))
        self.assertEqual(r.returncode, 1)
        self.assertIn("manual", r.stderr.lower())
        for args in ((), ("--print", "--apply"), ("--config", str(self.cfg))):
            self.assertEqual(self.run_cli(*args).returncode, 2)

    def test_default_config_is_under_home_and_never_used_by_startup(self):
        r = self.run_cli("--print")  # HOME is a tempdir: no real config touched
        self.assertEqual(r.returncode, 0)
        self.assertIn("/dev/null", r.stdout)
        self.assertEqual(os.listdir(self.dir), [])
        manifest = tomllib.loads((ROOT / "herdr-plugin.toml").read_text())
        commands = [manifest["startup"][0]["command"]] + [a["command"] for a in manifest["actions"]]
        self.assertTrue(all("sidebar-patch" not in c for cmd in commands for c in cmd))
        for f in (ROOT / "src/token_usage/lifecycle/daemon.py", ROOT / "src/token_usage/app/tick.py"):
            self.assertNotIn("sidebar_patch", f.read_text())
        main_src = MAIN.read_text()
        self.assertEqual(main_src.count("import sidebar_patch"), 1)  # lazy import inside the sidebar-patch branch


if __name__ == "__main__":
    unittest.main()
