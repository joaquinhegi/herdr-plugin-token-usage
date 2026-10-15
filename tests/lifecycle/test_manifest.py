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

    def items(self):
        return self.m["startup"] + self.m["actions"]

    def test_declares_all_three_platforms(self):
        self.assertEqual(self.m["platforms"], ["linux", "macos", "windows"])

    def test_every_item_is_platform_scoped_and_posix_items_keep_python3(self):
        for item in self.items():
            self.assertIn(item["platforms"], (["linux", "macos"], ["windows"]))
            self.assertEqual(item["command"][0], "python3" if "windows" not in item["platforms"] else "py")

    def test_posix_items_are_unchanged(self):
        posix = lambda items: [i for i in items if i["platforms"] == ["linux", "macos"]]
        self.assertEqual([s["command"] for s in posix(self.m["startup"])], [["python3", "-B", "src/main.py", "start"]])
        actions = {a["id"]: a["command"] for a in posix(self.m["actions"])}
        self.assertEqual(actions, {c: ["python3", "-B", "src/main.py", c] for c in ("start", "stop", "status")})

    def test_windows_items_use_py_launcher_with_utf8(self):
        win = lambda items: [i for i in items if i["platforms"] == ["windows"]]
        self.assertEqual([s["command"] for s in win(self.m["startup"])],
                         [["py", "-3", "-X", "utf8", "-B", "src/main.py", "start"]])
        actions = {a["id"]: a["command"] for a in win(self.m["actions"])}
        self.assertEqual(actions, {f"{c}-windows": ["py", "-3", "-X", "utf8", "-B", "src/main.py", c]
                                   for c in ("start", "stop", "status")})

    def test_action_ids_are_unique_and_titled(self):
        ids = [a["id"] for a in self.m["actions"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(isinstance(a["title"], str) and a["title"] for a in self.m["actions"]))

    def test_build_items_configure_sidebar_per_platform(self):
        self.assertEqual(self.m["build"], [
            {"platforms": ["linux", "macos"],
             "command": ["python3", "-B", "src/main.py", "sidebar-patch", "--install"]},
            {"platforms": ["windows"],
             "command": ["py", "-3", "-X", "utf8", "-B", "src/main.py", "sidebar-patch", "--install"]},
        ])

    def test_no_shell_strings(self):
        commands = [s["command"] for s in self.m["startup"]] + [a["command"] for a in self.m["actions"]] \
            + [b["command"] for b in self.m["build"]]
        for cmd in commands:
            self.assertIsInstance(cmd, list)
            self.assertNotIn(cmd[0], ("sh", "bash", "zsh"))
            self.assertTrue(all(isinstance(p, str) and not any(c in p for c in ";|&$`") for p in cmd))


if __name__ == "__main__":
    unittest.main()
