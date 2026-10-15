import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MAIN = Path(__file__).resolve().parents[2] / "src" / "main.py"
sys.path.insert(0, str(MAIN.parent))

from token_usage.adapters import log as tlog  # noqa: E402
from tests.lifecycle.fake_host import FakeHost  # noqa: E402
from tests.support import child_env  # noqa: E402


class TestMainErrors(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.bin = self.tmp / ("herdr.exe" if os.name == "nt" else "herdr")  # Windows requires .exe
        self.bin.write_text("#!/bin/sh\n")
        self.bin.chmod(0o755)
        self.env = child_env(HOME=str(self.tmp), HERDR_BIN_PATH=str(self.bin), HERDR_SOCKET_PATH=str(self.tmp / "no.sock"))

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

    def test_run_without_a_home_directory_is_a_short_error(self):
        mod = load_main()
        err = io.StringIO()
        env = {"HERDR_PLUGIN_STATE_DIR": str(self.tmp / "state"), "HERDR_BIN_PATH": str(self.bin)}
        with mock.patch.object(Path, "home", side_effect=RuntimeError("no home")), \
                mock.patch.dict(os.environ, env), mock.patch("sys.stderr", err):
            self.assertEqual(mod.main(["main.py", "run"]), 1)
        self.assertIn("cannot start", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


def load_main():
    spec = importlib.util.spec_from_file_location("token_usage_main_under_test", MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestHostSelection(unittest.TestCase):
    """Selection is injected (os_name / default_host), so it is asserted on every OS."""

    def test_default_host_follows_the_os_name(self):
        from token_usage.lifecycle import daemon
        from token_usage.lifecycle.host_posix import PosixHost
        from token_usage.lifecycle.host_windows import WindowsHost
        win = daemon.default_host(kill=lambda *a: self.fail("os.kill on Windows"), os_name="nt")
        self.assertIsInstance(win, WindowsHost)
        self.assertFalse(win.supports_socket)
        self.assertFalse(hasattr(win, "_kill"))  # nothing to signal with
        self.assertIsInstance(daemon.default_host(os_name="posix"), PosixHost)

    def test_start_stop_status_and_poller_defaults_use_the_selection(self):  # W3
        from token_usage.lifecycle import daemon
        host = FakeHost()
        with mock.patch.object(daemon, "default_host", return_value=host) as chosen:
            d = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, d, True)
            self.assertFalse(daemon.is_running(d))
            self.assertEqual(daemon.stop(d), "stopped")
            self.assertEqual(daemon.start(d, "", MAIN), "started")
            self.assertEqual(daemon.status(d, mock.Mock()), "stopped")
            self.assertIs(daemon.Poller(d, "", None, None, None, None, None).host, host)
        self.assertEqual(chosen.call_count, 5)
        self.assertEqual([c for c in host.calls if c[0] == "spawn"], [("spawn", [str(MAIN), "run"])])

    def build(self, supports_socket):
        main, socket_cls = load_main(), mock.Mock()
        host = FakeHost()
        host.supports_socket = supports_socket
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)  # registered first, runs after the logger is closed
        with mock.patch.object(main.daemon, "default_host", return_value=host), \
                mock.patch("token_usage.adapters.herdr_socket.HerdrSocket", socket_cls), \
                mock.patch("token_usage.adapters.herdr_cli.HerdrCli"):
            poller = main._build_poller(Path(state), "/bin/herdr", "/some/herdr.sock")
            self.addCleanup(tlog.close_logger, poller.logger)
        self.assertIs(poller.host, host)
        return socket_cls, poller

    def test_socket_client_is_built_only_when_the_host_supports_it(self):
        socket_cls, poller = self.build(supports_socket=False)
        socket_cls.assert_not_called()
        self.assertIsNone(poller.herdr._socket)
        socket_cls, poller = self.build(supports_socket=True)
        socket_cls.assert_called_once_with("/some/herdr.sock")


if __name__ == "__main__":
    unittest.main()
