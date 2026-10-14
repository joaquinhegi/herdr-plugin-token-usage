"""Herdr CLI client: argv-only subprocess calls with strict input validation."""

import json
import os
import re
import subprocess
from typing import Any

from token_usage.ports import HerdrError

_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


def _check(*values: str) -> None:
    for v in values:
        if not isinstance(v, str) or not _ID.fullmatch(v) or v.startswith("-"):
            raise HerdrError("invalid_identifier")


def _int(v: int) -> None:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise HerdrError("invalid_number")


def panes_from(data: Any) -> list[dict[str, Any]]:
    """Accept a bare list, {"panes": [...]} or {"result": {"panes": [...]}}."""
    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        data = data["result"]
    if isinstance(data, dict):
        data = data.get("panes")
    if not isinstance(data, list):
        raise HerdrError("unexpected_shape")
    return [p for p in data if isinstance(p, dict)]


class HerdrCli:
    def __init__(self, bin_path: str, timeout: float = 2.0):
        if not os.path.isabs(bin_path) or not os.path.isfile(bin_path) or not os.access(bin_path, os.X_OK):
            raise HerdrError("invalid_bin")
        self._bin = bin_path
        self._timeout = timeout

    def _run(self, *args: str) -> str:
        try:
            proc = subprocess.run(
                [self._bin, *args], shell=False, capture_output=True, timeout=self._timeout,
                check=False, stdin=subprocess.DEVNULL, text=True,
            )
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            raise HerdrError(type(exc).__name__) from None
        if proc.returncode != 0:
            raise HerdrError("nonzero_exit")
        return proc.stdout

    def list_panes(self) -> list[dict[str, Any]]:
        try:
            return panes_from(json.loads(self._run("pane", "list")))
        except ValueError:
            raise HerdrError("invalid_json") from None

    def report(self, pane_id: str, source: str, token: str, value: str, seq: int, ttl_ms: int) -> None:
        _check(pane_id, source, token)
        if not isinstance(value, str) or not 1 <= len(value) <= 80 or not value.isprintable():
            raise HerdrError("invalid_value")
        _int(seq)
        _int(ttl_ms)
        self._run("pane", "report-metadata", pane_id, "--source", source,
                  "--token", f"{token}={value}", "--seq", str(seq), "--ttl-ms", str(ttl_ms))

    def clear(self, pane_id: str, source: str, token: str, seq: int) -> None:
        _check(pane_id, source, token)
        _int(seq)
        self._run("pane", "report-metadata", pane_id, "--source", source,
                  "--clear-token", token, "--seq", str(seq))
