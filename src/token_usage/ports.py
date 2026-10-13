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
