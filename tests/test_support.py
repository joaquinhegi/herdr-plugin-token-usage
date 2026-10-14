import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tests.support import child_env  # noqa: E402


class ChildEnvTest(unittest.TestCase):
    def test_windows_profile_and_temp_vars_are_forwarded_when_present(self):
        names = ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP")
        with mock.patch.dict(os.environ, {n: f"C:\\x\\{n}" for n in names}):
            env = child_env()
        for n in names:
            self.assertEqual(env[n], f"C:\\x\\{n}")

    def test_absent_vars_are_not_invented(self):
        with mock.patch.dict(os.environ, clear=True):
            self.assertEqual(child_env(), {"PATH": ""})

    def test_explicit_extra_wins(self):
        with mock.patch.dict(os.environ, {"TEMP": "a"}):
            self.assertEqual(child_env(TEMP="b")["TEMP"], "b")


if __name__ == "__main__":
    unittest.main()
