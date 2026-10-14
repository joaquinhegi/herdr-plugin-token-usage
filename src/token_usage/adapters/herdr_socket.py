"""Herdr socket client (newline-delimited JSON over AF_UNIX).

Only pane.list is implemented: socket report_metadata is not verified against
herdr 0.8.2, so metadata writes (report / clear) go through the CLI client.
"""

import json
import socket
from typing import Any

from token_usage.adapters.herdr_cli import panes_from
from token_usage.ports import HerdrError

_REQ_ID = "req_1"


class HerdrSocket:
    def __init__(self, path: str, timeout: float = 2.0, max_bytes: int = 8 * 1024 * 1024):
        self._path = path
        self._timeout = timeout
        self._max = max_bytes

    def _read_line(self, sock: socket.socket) -> bytes:
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                raise HerdrError("closed_without_newline")
            buf += chunk
            if len(buf) > self._max:
                raise HerdrError("response_too_large")
        return buf.split(b"\n", 1)[0]

    def list_panes(self) -> list[dict[str, Any]]:
        request = json.dumps({"id": _REQ_ID, "method": "pane.list", "params": {}}).encode() + b"\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(self._timeout)
                sock.connect(self._path)
                sock.sendall(request)
                reply = json.loads(self._read_line(sock))
        except (OSError, ValueError) as exc:
            raise HerdrError(type(exc).__name__) from None
        if not isinstance(reply, dict) or reply.get("id") != _REQ_ID or "error" in reply:
            raise HerdrError("bad_reply")
        return panes_from(reply.get("result"))

    def report(self, *args: Any) -> None:
        raise NotImplementedError("metadata writes go through the CLI client")

    clear = report
