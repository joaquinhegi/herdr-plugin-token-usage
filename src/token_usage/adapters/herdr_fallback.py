"""Per-call fallback: pane.list tries the socket first, then the CLI; writes use the CLI."""

import logging
from typing import Any

from token_usage.adapters.log import log_event
from token_usage.ports import HerdrError, HerdrPort


class FallbackHerdr:
    def __init__(self, socket_client: HerdrPort | None, cli: HerdrPort, logger: logging.Logger):
        self._socket = socket_client
        self._cli = cli
        self._logger = logger

    def list_panes(self) -> list[dict[str, Any]]:
        if self._socket is not None:
            try:
                return self._socket.list_panes()
            except (HerdrError, OSError, AttributeError) as exc:  # AttributeError: no AF_UNIX transport
                log_event(self._logger, "herdr_fallback", error=type(exc).__name__)
        return self._cli.list_panes()

    def report(self, pane_id: str, source: str, token: str, value: str, seq: int, ttl_ms: int) -> None:
        self._cli.report(pane_id, source, token, value, seq, ttl_ms)

    def clear(self, pane_id: str, source: str, token: str, seq: int) -> None:
        self._cli.clear(pane_id, source, token, seq)
