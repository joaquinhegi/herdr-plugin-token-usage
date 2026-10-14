"""Plugin entrypoint: argv dispatch only (run | start | stop | status)."""

import os
import sys
import time
from pathlib import Path

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
    if len(argv) != 2 or argv[1] not in COMMANDS:
        print("usage: main.py run|start|stop|status", file=sys.stderr)
        return 2
    cmd = argv[1]
    state = _env("HERDR_PLUGIN_STATE_DIR")
    bin_path = _env("HERDR_BIN_PATH")
    if not state or (cmd in ("run", "start") and not bin_path):
        print("token-usage: HERDR_PLUGIN_STATE_DIR and HERDR_BIN_PATH must be set", file=sys.stderr)
        return 2
    state_dir, socket_path = Path(state), _env("HERDR_SOCKET_PATH")
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
    return 1 if result == "failed" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
