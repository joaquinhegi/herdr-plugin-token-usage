"""Print-first, minimal sidebar patch: adds `$tokens` to the Claude agent row only.

Rule: if `ui.sidebar.agents.rows_by_agent.claude` exists, extend its last row; else if
`ui.sidebar.agents.rows` exists, extend its last row; else if no `ui.sidebar.agents` table
exists (or no file), append a minimal section; otherwise REFUSE and print manual steps.
Every edit is verified by re-parsing with tomllib. Never called by startup.
"""

import difflib
import os
import re
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

TOKEN = '"$tokens"'
MINIMAL = '[ui.sidebar.agents]\nrows = [["agent", "$tokens"]]\n'
HEADER = re.compile(r"^\s*\[([\w. -]+)\]\s*(#.*)?$")
MANUAL = (
    "Cannot patch safely. Manual steps: in ~/.config/herdr/config.toml add \"$tokens\" to the\n"
    "last row of [ui.sidebar.agents.rows_by_agent].claude (or of [ui.sidebar.agents].rows when\n"
    "there is no claude override), e.g. [\"agent\", \"$tokens\"]. Nothing was changed."
)


@dataclass
class Plan:
    status: str  # patch | noop | refuse
    diff: str = ""
    new_text: str = ""
    message: str = ""


def _refuse(why: str) -> Plan:
    return Plan("refuse", message=f"{why}\n{MANUAL}\n")


def _insert_pos(text: str, start: int) -> int | None:
    """Offset of the closing `]` of the last inner row of the array opening at `start`."""
    depth, i, last_inner = 0, start, None
    while i < len(text):
        c = text[i]
        if c in "\"'":
            if text.startswith(c * 3, i):
                return None
            j = i + 1
            while j < len(text) and text[j] not in (c, "\n"):
                j += 2 if (c == '"' and text[j] == "\\") else 1
            if j >= len(text) or text[j] != c:
                return None
            i = j
        elif c == "#":
            i = text.find("\n", i)
            if i < 0:
                return None
        elif c == "[":
            depth += 1
        elif c == "]":
            if depth == 2:
                last_inner = i
            depth -= 1
            if depth == 0:
                return last_inner
        i += 1
    return None


def _locate(text: str, table: str, key: str) -> int | None:
    current, pos = None, 0
    for line in text.splitlines(keepends=True):
        m = HEADER.match(line)
        if m:
            current = m.group(1).replace(" ", "")
        elif current == table:
            k = re.match(rf"^{key}\s*=\s*(?=\[)", line)
            if k:
                return _insert_pos(text, pos + k.end())
        pos += len(line)
    return None


def _glue(text: str, at: int) -> str:
    prev = text[:at].rstrip()[-1:]
    return "" if prev == "[" else " " if prev == "," else ", "


def plan(path: Path) -> Plan:
    exists = path.exists()
    text = path.read_text(encoding="utf-8") if exists else ""
    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return _refuse("Config is not valid TOML.")
    try:
        agents = data["ui"]["sidebar"]["agents"]
    except (KeyError, TypeError):
        agents = None
    if agents is None:
        new = text + ("" if not text or text.endswith("\n") else "\n") + ("\n" if text else "") + MINIMAL
        return _finish(path, text, new, exists, None)
    by_agent = agents.get("rows_by_agent")
    override = by_agent.get("claude") if isinstance(by_agent, dict) else None
    which, rows = ("claude", override) if override is not None else ("rows", agents.get("rows"))
    if not isinstance(rows, list) or not rows or not all(isinstance(r, list) for r in rows):  # shape unknown
        return _refuse("No Claude row layout found in [ui.sidebar.agents].")
    if any("$tokens" in r for r in rows):
        return Plan("noop", message="$tokens is already present.\n")
    at = _locate(text, "ui.sidebar.agents.rows_by_agent", "claude") if which == "claude" else _locate(text, "ui.sidebar.agents", "rows")
    if at is None:
        return _refuse("Row layout uses a form this patch does not edit.")
    new = text[:at] + _glue(text, at) + TOKEN + text[at:]
    expect = tomllib.loads(text)
    a = expect["ui"]["sidebar"]["agents"]
    (a["rows_by_agent"]["claude"] if which == "claude" else a["rows"])[-1].append("$tokens")
    return _finish(path, text, new, exists, expect)


def _finish(path: Path, old: str, new: str, existed: bool, expect: dict | None) -> Plan:
    try:
        parsed = tomllib.loads(new)
    except tomllib.TOMLDecodeError:
        return _refuse("Patched config failed validation.")
    if expect is not None and parsed != expect:
        return _refuse("Patched config failed validation.")
    diff = difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                f"a/{path.name}" if existed else "/dev/null", f"b/{path.name}")
    return Plan("patch", "".join(diff), new)


def _emit(res: Plan) -> int:
    print(res.diff or res.message, end="", file=sys.stderr if res.status == "refuse" else sys.stdout)
    return 1 if res.status == "refuse" else 0


def apply(path: Path) -> int:
    res = plan(path)
    if res.status != "patch":
        return _emit(res)
    path.parent.mkdir(parents=True, exist_ok=True)
    backed_up = path.exists()
    if backed_up:
        backup = path.with_name(f"{path.name}.bak-{time.strftime('%Y%m%dT%H%M%S')}-{time.time_ns() % 10**6:06d}")
        with open(backup, "xb") as fh:
            fh.write(path.read_bytes())
        mode = path.stat().st_mode & 0o777
    else:
        mode = 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(res.new_text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    print("patched (backup written next to the config)" if backed_up else "created")
    return 0


def main(args: list[str]) -> int:
    flags = [a for a in args if a in ("--print", "--apply")]
    rest = [a for a in args if a not in ("--print", "--apply")]
    if len(flags) != 1 or (rest and not (len(rest) == 2 and rest[0] == "--config")):
        print("usage: main.py sidebar-patch --print|--apply [--config PATH]", file=sys.stderr)
        return 2
    path = Path(rest[1]) if rest else Path.home() / ".config" / "herdr" / "config.toml"
    if flags[0] == "--apply":
        return apply(path)
    return _emit(plan(path))
