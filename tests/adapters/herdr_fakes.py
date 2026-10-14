"""Test doubles for Herdr: a fake bin script and an AF_UNIX server (never the real herdr)."""

import json
import os
import socket
import stat
import sys
import tempfile
import threading
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "herdr" / "pane_list.json"


def fixture_panes() -> list[dict]:
    return json.loads(FIXTURE.read_text())["result"]["panes"]


def make_fake_bin(directory: Path, *, sleep: float = 0, code: int = 0, out: str | None = None) -> Path:
    """Fake herdr: dumps argv as JSON to argv.json, prints the fixture (or `out`)."""
    body = (
        f"#!{sys.executable}\n"
        "import json, sys, time\n"
        f"json.dump(sys.argv[1:], open({str(directory / 'argv.json')!r}, 'w'))\n"
        f"time.sleep({sleep})\n"
        f"print({out!r} if {out!r} is not None else json.dumps({{'type': 'pane_list', 'panes': {fixture_panes()!r}}}))\n"
        f"sys.exit({code})\n"
    )
    path = directory / "herdr"
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class FakeServer:
    """One-shot AF_UNIX server; `handler(request_line_bytes, conn)` produces the reply."""

    def __init__(self, handler):
        self.dir = tempfile.mkdtemp(dir="/tmp")
        self.path = os.path.join(self.dir, "s")
        self._srv = socket.socket(socket.AF_UNIX)
        self._srv.bind(self.path)
        self._srv.listen(4)
        self._handler = handler
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                try:
                    self._handler(buf, conn)
                except OSError:
                    pass

    def close(self):
        self._srv.close()
        os.unlink(self.path)
        os.rmdir(self.dir)


def ok_handler(req: bytes, conn) -> None:
    rid = json.loads(req)["id"]
    conn.sendall(json.dumps({"id": rid, "result": {"type": "pane_list", "panes": fixture_panes()}}).encode() + b"\n")
