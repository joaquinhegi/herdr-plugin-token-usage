import io
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from token_usage.lifecycle import sidebar_patch as sp
from tests.support import child_env, needs_symlink, posix_only

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
    def test_tokens_in_any_row_is_noop(self):
        self.write('[ui.sidebar.agents]\nrows = [["agent", "$tokens"], ["cwd"]]\n')
        res = sp.plan(self.cfg)
        self.assertEqual((res.status, res.new_text), ("noop", ""))

    def test_tokens_in_any_row_noop_is_independent_per_target(self):
        self.write('[ui.sidebar.agents]\nrows = [["agent", "$tokens"], ["cwd"]]\n\n'
                   '[ui.sidebar.agents.rows_by_agent]\nclaude = [["agent"], ["cwd"]]\n')
        res = sp.plan(self.cfg)
        self.assertEqual(res.status, "patch")
        self.assertEqual(added(res.diff), ['claude = [["agent"], ["cwd", "$tokens"]]'])

    def test_non_table_agents_refuses_without_traceback(self):
        self.write("[ui.sidebar]\nagents = 1\n")
        self.assertEqual(sp.plan(self.cfg).status, "refuse")

    def test_manual_steps_say_uncomment_and_check(self):
        self.write("[ui]\ntheme = 'x'\n")
        msg = sp.plan(self.cfg).message
        for needle in ("uncomment", "herdr config check", "reload"):
            self.assertIn(needle, msg.lower())

    def test_custom_claude_row_only_adds_tokens(self):
        text = self.write(CUSTOM.split("\n\n")[1])  # no top-level rows: only the override
        text = self.write("[ui.sidebar.agents]\nspacing = 1\n\n" + text)
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

    def test_missing_file_or_section_refuses_with_manual_steps_for_given_path(self):
        for text in (None, '[ui]\ntheme = "x"\n', "[ui.sidebar.agents]\nspacing = 1\n"):
            with self.subTest(text=text):
                if text is not None:
                    self.write(text)
                res = sp.plan(self.cfg)
                self.assertEqual(res.status, "refuse")
                self.assertEqual(res.new_text, "")
                for needle in ("--default-config", "$tokens", "--print", str(self.cfg)):
                    self.assertIn(needle, res.message)
                self.assertNotIn("~/.config", res.message)

    def test_rows_and_claude_override_both_get_tokens_idempotent_per_row(self):
        res = sp.plan(self.write(CUSTOM) and self.cfg)
        self.assertEqual(added(res.diff), ['  ["agent", "$tokens"],', '  ["cwd", "$tokens"],'])
        a = tomllib.loads(res.new_text)["ui"]["sidebar"]["agents"]
        self.assertEqual(a["rows"][-1], ["agent", "$tokens"])
        self.assertEqual(a["rows_by_agent"]["claude"][-1], ["cwd", "$tokens"])
        self.assertEqual(a["rows_by_agent"]["codex"], [["agent"]])
        self.write(res.new_text)
        self.assertEqual(sp.plan(self.cfg).status, "noop")
        half = CUSTOM.replace('  ["agent"],\n]', '  ["agent", "$tokens"],\n]')  # only rows already patched
        self.write(half)
        res = sp.plan(self.cfg)
        self.assertEqual(added(res.diff), ['  ["cwd", "$tokens"],'])
        self.assertEqual(tomllib.loads(res.new_text)["ui"]["sidebar"]["agents"]["rows"][-1], ["agent", "$tokens"])

    def test_fake_header_in_multiline_string_is_refused_by_reparse(self):
        self.write('[ui]\nnote = """\n[ui.sidebar.agents]\nrows = [["fake"]]\n"""\n'
                   '[ui.sidebar.agents]\nrows = [["agent"]]\n')
        res = sp.plan(self.cfg)
        self.assertEqual(res.status, "refuse")
        self.assertEqual(res.new_text, "")

    def test_unreadable_inputs_refuse_without_traceback_or_path(self):
        res = sp.plan(self.dir)  # a directory
        self.assertEqual(res.status, "refuse")
        self.cfg.write_bytes(b"\xff\xfe\x00bad")
        res2 = sp.plan(self.cfg)
        self.assertEqual(res2.status, "refuse")
        for r in (res, res2):
            self.assertNotIn("Errno", r.message)
            self.assertNotIn("Traceback", r.message)

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
        if os.name == "posix":
            self.cfg.chmod(0o640)
        self.assertEqual(sp.apply(self.cfg), 0)
        backups = [p for p in self.dir.iterdir() if p.name.startswith("config.toml.bak-")]
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), CUSTOM)
        self.assertEqual(len(list(self.dir.iterdir())), 2)  # no temp files left
        self.assertIn('["cwd", "$tokens"]', self.cfg.read_text())
        if os.name == "posix":
            self.assertEqual(self.cfg.stat().st_mode & 0o777, 0o640)

    def test_apply_refusal_changes_nothing(self):
        self.write("[ui.sidebar.agents]\nspacing = 1\n")
        self.assertNotEqual(sp.apply(self.cfg), 0)
        self.assertEqual(sorted(os.listdir(self.dir)), ["config.toml"])
        self.assertEqual(self.cfg.read_text(), "[ui.sidebar.agents]\nspacing = 1\n")

    def test_apply_missing_file_refuses_and_second_run_is_noop(self):
        self.assertEqual(sp.apply(self.cfg), 1)  # never creates a config
        self.assertEqual(os.listdir(self.dir), [])
        self.write(ROWS_ONLY)
        self.assertEqual(sp.apply(self.cfg), 0)
        self.assertEqual(sp.apply(self.cfg), 0)  # already patched: no new backup
        self.assertEqual(len(os.listdir(self.dir)), 2)

    @needs_symlink
    def test_symlink_target_is_patched_in_place_and_link_kept(self):
        real_dir = self.dir / "real"
        real_dir.mkdir()
        target = real_dir / "config.toml"
        target.write_text(ROWS_ONLY)
        link = self.dir / "link.toml"
        link.symlink_to(target)
        self.assertEqual(sp.apply(link), 0)
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.path.realpath(link), os.path.realpath(target))
        self.assertIn("$tokens", target.read_text())
        backups = [p.name for p in real_dir.iterdir() if ".bak-" in p.name]
        self.assertEqual(len(backups), 1)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["link.toml", "real"])

    @posix_only
    def test_backup_preserves_private_mode(self):
        self.write(ROWS_ONLY)
        self.cfg.chmod(0o600)
        self.assertEqual(sp.apply(self.cfg), 0)
        backup = next(p for p in self.dir.iterdir() if ".bak-" in p.name)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cfg.stat().st_mode & 0o777, 0o600)


class TestDefaultPath(unittest.TestCase):
    HOME = lambda self: Path("/h")  # noqa: E731

    def resolve(self, env, os_name="posix"):
        return sp.default_config_path(env, os_name, self.HOME)

    def test_precedence_env_then_xdg_then_appdata_then_home(self):
        env = {"HERDR_CONFIG_PATH": "/e/c.toml", "XDG_CONFIG_HOME": "/x", "APPDATA": "/a"}
        self.assertEqual(self.resolve(env, "nt"), Path("/e/c.toml"))
        del env["HERDR_CONFIG_PATH"]
        self.assertEqual(self.resolve(env, "nt"), Path("/x/herdr/config.toml"))
        del env["XDG_CONFIG_HOME"]
        self.assertEqual(self.resolve(env, "nt"), Path("/a/herdr/config.toml"))
        self.assertEqual(self.resolve({}, "nt"), Path("/h/.config/herdr/config.toml"))

    def test_appdata_is_ignored_off_windows_and_empty_values_are_unset(self):
        self.assertEqual(self.resolve({"APPDATA": "/a"}), Path("/h/.config/herdr/config.toml"))
        env = {"HERDR_CONFIG_PATH": "", "XDG_CONFIG_HOME": ""}
        self.assertEqual(self.resolve(env), Path("/h/.config/herdr/config.toml"))

    def test_home_is_not_needed_when_a_higher_source_is_set(self):
        def boom():
            raise RuntimeError("no home")
        self.assertEqual(sp.default_config_path({"XDG_CONFIG_HOME": "/x"}, "posix", boom), Path("/x/herdr/config.toml"))

    def test_unresolvable_home_is_a_short_error_without_traceback(self):
        err = io.StringIO()
        with mock.patch.object(Path, "home", side_effect=RuntimeError("no home")), \
                mock.patch.dict(os.environ, {}, clear=True), mock.patch("sys.stderr", err):
            self.assertEqual(sp.main(["--print"]), 1)
        self.assertIn("home directory", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


class TestApplyReplace(Base):
    def test_apply_replaces_through_replace_with_retry(self):  # S5
        self.write(ROWS_ONLY)
        with mock.patch.object(sp, "replace_with_retry", wraps=sp.replace_with_retry) as m:
            self.assertEqual(sp.apply(self.cfg), 0)
        self.assertEqual(m.call_count, 1)
        self.assertIn("$tokens", self.cfg.read_text())


class TestCli(Base):
    def run_cli(self, *args):
        env = child_env(HOME=str(self.dir))
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

    def test_non_table_agents_cli_exit_1_no_traceback(self):
        self.write("[ui.sidebar]\nagents = 1\n")
        r = self.run_cli("--print", "--config", str(self.cfg))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)

    def test_default_config_honors_herdr_config_path(self):
        self.write(ROWS_ONLY)
        env = child_env(HOME=str(self.dir / "nohome"), HERDR_CONFIG_PATH=str(self.cfg))
        r = subprocess.run([sys.executable, "-B", str(MAIN), "sidebar-patch", "--print"], env=env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0)
        self.assertIn("$tokens", r.stdout)

    def test_directory_config_is_short_error_not_traceback(self):
        r = self.run_cli("--apply", "--config", str(self.dir))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)

    def test_default_config_is_under_home_and_never_used_by_startup(self):
        r = self.run_cli("--print")  # HOME is a tempdir: no real config touched
        self.assertEqual(r.returncode, 1)
        self.assertIn("--default-config", r.stderr)
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
