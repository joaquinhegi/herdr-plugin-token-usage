"""JSON state store: atomic, dirty-only writes; ids/offsets/counters only."""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

VERSION = 1
MAX_AGE = 30 * 86400
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _check_state(state: dict[str, Any]) -> None:
    for key in state.get("files", {}):
        if key.startswith("/") or ".." in Path(key).parts or "\\" in key or ":" in key:
            raise ValueError("file keys must be relative")


class StateStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._written: dict[str, str] = {}

    def _write(self, path: Path, state: dict[str, Any]) -> bool:
        payload = json.dumps({"v": VERSION, **state}, sort_keys=True, separators=(",", ":"))
        if self._written.get(str(path)) == payload:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        self._written[str(path)] = payload
        return True

    def _read(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("v") != VERSION:
            return None
        return data

    def _session_path(self, session_id: str) -> Path:
        if not _ID.fullmatch(session_id):
            raise ValueError("invalid session id")
        return self.root / "sessions" / f"{session_id}.json"

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        return self._read(self._session_path(session_id))

    def save_session(self, session_id: str, state: dict[str, Any]) -> bool:
        _check_state(state)
        return self._write(self._session_path(session_id), state)

    def load_published(self) -> dict[str, Any] | None:
        return self._read(self.root / "published.json")

    def save_published(self, state: dict[str, Any]) -> bool:
        return self._write(self.root / "published.json", state)

    def prune(self, now: float) -> int:
        removed = 0
        for path in (self.root / "sessions").glob("*.json"):
            data = self._read(path)
            if data is not None and now - data.get("last_seen", now) <= MAX_AGE:
                continue
            path.unlink(missing_ok=True)
            self._written.pop(str(path), None)
            removed += 1
        return removed
