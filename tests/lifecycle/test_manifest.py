import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

ROOT = Path(__file__).resolve().parents[2]


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.m = tomllib.loads((ROOT / "herdr-plugin.toml").read_text())

    def test_required_fields(self):
        for key in ("id", "name", "version", "min_herdr_version"):
            self.assertIsInstance(self.m[key], str)

    def test_startup_and_actions_are_argv_lists(self):
        self.assertEqual([s["command"] for s in self.m["startup"]], [["python3", "src/main.py", "start"]])
        actions = {a["id"]: a["command"] for a in self.m["actions"]}
        self.assertEqual(actions, {c: ["python3", "src/main.py", c] for c in ("start", "stop", "status")})

    def test_no_shell_strings_or_build(self):
        commands = [s["command"] for s in self.m["startup"]] + [a["command"] for a in self.m["actions"]]
        for cmd in commands:
            self.assertIsInstance(cmd, list)
            self.assertNotIn(cmd[0], ("sh", "bash", "zsh"))
            self.assertTrue(all(isinstance(p, str) and not any(c in p for c in ";|&$`") for p in cmd))
        self.assertNotIn("build", self.m)


if __name__ == "__main__":
    unittest.main()
