"""Ports (Protocols) implemented by the I/O adapters."""

from pathlib import Path
from typing import Any, Protocol


class Clock(Protocol):
    def now(self) -> float: ...


class StateStore(Protocol):
    def load_session(self, session_id: str) -> dict[str, Any] | None: ...
    def save_session(self, session_id: str, state: dict[str, Any]) -> bool: ...
    def load_published(self) -> dict[str, Any] | None: ...
    def save_published(self, state: dict[str, Any]) -> bool: ...
    def prune(self, now: float) -> int: ...


class TailResult(Protocol):
    objects: list[Any]
    undecodable: int
    position: dict[str, int]


class Tailer(Protocol):
    def read(self, path: Path, position: dict[str, int] | None) -> TailResult: ...


class HerdrError(Exception):
    """Any failure talking to Herdr (spawn, timeout, protocol, bad input)."""


class HerdrPort(Protocol):
    def list_panes(self) -> list[dict[str, Any]]: ...
    def report(self, pane_id: str, source: str, token: str, value: str, seq: int, ttl_ms: int) -> None: ...
    def clear(self, pane_id: str, source: str, token: str, seq: int) -> None: ...
