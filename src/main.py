"""Plugin entrypoint: argv dispatch only (run | start | stop | status | sidebar-patch)."""

import sys

if sys.version_info < (3, 10):  # before any import that needs PEP 604 syntax
    print("token-usage: Python 3.10 or newer is required", file=sys.stderr)
    raise SystemExit(2)

import os  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from token_usage.lifecycle import daemon  # noqa: E402

COMMANDS = ("run", "start", "stop", "status")


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


def _build_poller(state_dir: Path, bin_path: str, socket_path: str | None):
    from token_usage.adapters import log as tlog
    from token_usage.adapters.claude_locator import ClaudeLocator
    from token_usage.adapters.herdr_cli import HerdrCli
    from token_usage.adapters.herdr_fallback import FallbackHerdr
    from token_usage.adapters.herdr_socket import HerdrSocket
    from token_usage.adapters.jsonl_tail import JsonlTail
    from token_usage.adapters.state_store import StateStore
    from token_usage.app.tick import TickService

    class Clock:
        def now(self) -> float:
            return time.time()

    logger = tlog.make_logger(state_dir)
    herdr = FallbackHerdr(HerdrSocket(socket_path) if socket_path else None, HerdrCli(bin_path), logger)
    store, clock = StateStore(state_dir), Clock()
    locator = ClaudeLocator(Path.home() / ".claude" / "projects", logger)
    tick = TickService(herdr, locator, JsonlTail(), store, clock, logger).tick
    return daemon.Poller(state_dir, socket_path or "", tick, herdr, store, clock, logger)


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "sidebar-patch":  # explicit, user-run; never from startup
        from token_usage.lifecycle import sidebar_patch
        return sidebar_patch.main(argv[2:])
    if len(argv) != 2 or argv[1] not in COMMANDS:
        print("usage: main.py run|start|stop|status", file=sys.stderr)
        return 2
    cmd = argv[1]
    state = _env("HERDR_PLUGIN_STATE_DIR")
    bin_path = _env("HERDR_BIN_PATH")
    if not state or (cmd in ("run", "start") and not bin_path):
        print("token-usage: HERDR_PLUGIN_STATE_DIR and HERDR_BIN_PATH must be set", file=sys.stderr)
        return 2
    if cmd == "start" and not (os.path.isabs(bin_path) and os.path.isfile(bin_path) and os.access(bin_path, os.X_OK)):
        print("token-usage: HERDR_BIN_PATH must be an absolute path to an executable", file=sys.stderr)
        return 2
    state_dir, socket_path = Path(state), _env("HERDR_SOCKET_PATH")
    try:
        return _dispatch(cmd, state_dir, bin_path, socket_path)
    except OSError:
        print("token-usage: state directory is not usable", file=sys.stderr)
        return 1


def _dispatch(cmd: str, state_dir: Path, bin_path: str | None, socket_path: str | None) -> int:
    if cmd == "run":
        try:
            poller = _build_poller(state_dir, bin_path, socket_path)
        except Exception as exc:
            print(f"token-usage: cannot start ({type(exc).__name__})", file=sys.stderr)
            return 1
        poller.install_signals()
        return poller.run()
    if cmd == "start":
        result = daemon.start(state_dir, socket_path or "", Path(__file__).resolve())
    elif cmd == "stop":
        result = daemon.stop(state_dir)
    else:
        from token_usage.adapters.state_store import StateStore
        result = daemon.status(state_dir, StateStore(state_dir))
    print(result)
    if result == "failed":
        _log_failed_handoff(state_dir)
        return 1
    return 0


def _log_failed_handoff(state_dir: Path) -> None:
    from token_usage.adapters import log as tlog

    logger = tlog.make_logger(state_dir)
    tlog.log_event(logger, "handoff_failed", cmd="start/stop")
    tlog.close_logger(logger)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
