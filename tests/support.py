"""Platform guards and helpers shared by the test suite (stdlib only)."""

import os
import signal
import tempfile
import unittest

POSIX = os.name == "posix"
posix_only = unittest.skipUnless(POSIX, "POSIX-only behavior (flock, modes, AF_UNIX, shebang scripts)")
CAN_CHMOD0 = POSIX and os.geteuid() != 0  # root ignores file permissions
unreadable_files = unittest.skipUnless(CAN_CHMOD0, "needs POSIX permissions and a non-root user")


def _can_symlink() -> bool:
    with tempfile.TemporaryDirectory() as d:
        try:
            os.symlink(os.path.join(d, "t"), os.path.join(d, "l"))
        except (OSError, NotImplementedError):
            return False
    return True


needs_symlink = unittest.skipUnless(_can_symlink(), "symlinks unavailable")


def child_env(**extra) -> dict:
    """Minimal environment for a child Python; Windows needs SYSTEMROOT to start."""
    env = {"PATH": os.environ.get("PATH", "")}
    for name in ("SYSTEMROOT", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):  # Windows profile and temp dirs
        if os.environ.get(name):
            env[name] = os.environ[name]
    env.update(extra)
    if "HOME" in extra:
        env.setdefault("USERPROFILE", extra["HOME"])  # Path.home() on Windows
    return env


def time_limit(case: unittest.TestCase, seconds: int = 30) -> None:
    """Fail (not hang) a test that exceeds `seconds`; SIGALRM only, a no-op elsewhere."""
    if not hasattr(signal, "SIGALRM"):
        return

    def expired(*_):
        raise AssertionError(f"test exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)

    def restore():
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

    case.addCleanup(restore)
