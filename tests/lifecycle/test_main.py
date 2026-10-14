import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[2] / "src" / "main.py"


class TestMainErrors(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.bin = self.tmp / "herdr"
        self.bin.write_text("#!/bin/sh\n")
        self.bin.chmod(0o755)
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.tmp), "HERDR_BIN_PATH": str(self.bin),
                    "HERDR_SOCKET_PATH": str(self.tmp / "no.sock")}

    def run_main(self, cmd, **env):
        e = {**self.env, **env}
        return subprocess.run([sys.executable, "-B", str(MAIN), cmd], env=e, capture_output=True, text=True, timeout=20)

    def assertClean(self, r):
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn(str(self.tmp), r.stderr + r.stdout)
        self.assertTrue(r.stderr.strip())

    def test_old_python_exits_2_with_short_message(self):
        code = ("import sys, runpy; sys.version_info = (3, 10, 9); sys.argv = [%r, 'status']; "
                "runpy.run_path(%r, run_name='__main__')" % (str(MAIN), str(MAIN)))
        r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("3.11", r.stderr)

    def test_unwritable_state_dir(self):
        blocker = self.tmp / "file"
        blocker.write_text("x")
        for cmd in ("status", "stop", "start"):
            self.assertClean(self.run_main(cmd, HERDR_PLUGIN_STATE_DIR=str(blocker / "sub")))

    def test_start_rejects_bad_bin_path(self):
        state = str(self.tmp / "state")
        plain = self.tmp / "plain"
        plain.write_text("x")
        for bad in ("herdr", str(plain), str(self.tmp / "missing")):
            self.assertClean(self.run_main("start", HERDR_PLUGIN_STATE_DIR=state, HERDR_BIN_PATH=bad))
        self.assertFalse((self.tmp / "state" / "poller.pid").exists())


if __name__ == "__main__":
    unittest.main()
