import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters import atomic  # noqa: E402


class ReplaceWithRetryTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src, self.dst = Path(tmp.name) / "a.tmp", Path(tmp.name) / "a"
        self.src.write_text("new")

    def test_transient_permission_error_is_retried(self):
        real, calls, sleeps = os.replace, [], []

        def flaky(a, b):
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError("sharing violation")
            return real(a, b)

        with mock.patch("os.replace", flaky):
            atomic.replace_with_retry(self.src, self.dst, sleep=sleeps.append)
        self.assertEqual(self.dst.read_text(), "new")
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [0.05, 0.1])

    def test_persistent_permission_error_fails_after_five_tries(self):
        calls, sleeps = [], []

        def locked(a, b):
            calls.append(1)
            raise PermissionError("locked")

        with mock.patch("os.replace", locked), self.assertRaises(PermissionError):
            atomic.replace_with_retry(self.src, self.dst, sleep=sleeps.append)
        self.assertEqual(len(calls), 5)
        self.assertLessEqual(sum(sleeps), 1.6)

    def test_other_errors_are_not_retried(self):
        calls = []

        def broken(a, b):
            calls.append(1)
            raise OSError("disk")

        with mock.patch("os.replace", broken), self.assertRaises(OSError):
            atomic.replace_with_retry(self.src, self.dst, sleep=lambda s: None)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
