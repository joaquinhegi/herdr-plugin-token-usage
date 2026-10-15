"""Print-first, minimal sidebar patch: adds `$tokens` to existing agent rows only.

Rule: extend the last row of `ui.sidebar.agents.rows` and of `rows_by_agent.claude` (each when
present, a row set already containing `$tokens` anywhere is left alone). It never creates a rows section (that would replace Herdr's
default layout): with no config or no `[ui.sidebar.agents]` rows it REFUSES with manual steps.
Every edit is verified by re-parsing with tomllib. Never called by startup.
"""

import difflib
import os
import re
import shutil
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from token_usage.adapters.atomic import replace_with_retry

TOKEN = '"$tokens"'
HEADER = re.compile(r"^\s*\[([\w. -]+)\]\s*(#.*)?$")


def _manual(path: Path, why: str) -> str:
    return (
        f"{why}\nNothing was changed. Manual steps for {path}: run `herdr --default-config`, copy its\n"
        "[ui.sidebar.agents] section and rows into that file and uncomment those lines (they ship commented\n"
        'out); add "$tokens" to the agent row, e.g. ["agent", "$tokens"]; run `herdr config check`; reload\n'
        "the config (`herdr server reload-config`); then re-run `sidebar-patch --print`.\n"
    )


@dataclass
class Plan:
    status: str  # patch | noop | refuse
    diff: str = ""
    new_text: str = ""
    message: str = ""


def _refuse(why: str, path: Path) -> Plan:
    return Plan("refuse", message=_manual(path, why))


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
    real = Path(os.path.realpath(path))
    try:
        text = real.read_text(encoding="utf-8")
        data = tomllib.loads(text)
    except FileNotFoundError:
        return _refuse("No config file found.", path)
    except (OSError, UnicodeDecodeError):
        return _refuse("Config cannot be read as a UTF-8 file.", path)
    except tomllib.TOMLDecodeError:
        return _refuse("Config is not valid TOML.", path)
    try:
        agents = data["ui"]["sidebar"]["agents"]
    except (KeyError, TypeError):
        return _refuse("No [ui.sidebar.agents] section found.", path)
    if not isinstance(agents, dict):
        return _refuse("[ui.sidebar] agents is not a table.", path)
    by_agent = agents.get("rows_by_agent")
    found = [("ui.sidebar.agents", "rows", agents.get("rows")) if "rows" in agents else None,
             ("ui.sidebar.agents.rows_by_agent", "claude", by_agent["claude"])
             if isinstance(by_agent, dict) and "claude" in by_agent else None]
    targets = [t for t in found if t]
    if not targets or any(not isinstance(r, list) or not r or not all(isinstance(x, list) for x in r)
                          for _, _, r in targets):  # shape unknown
        return _refuse("No usable row layout found in [ui.sidebar.agents].", path)
    todo = [(t, k) for t, k, r in targets if not any("$tokens" in row for row in r)]
    if not todo:
        return Plan("noop", message="$tokens is already present.\n")
    spots = [_locate(text, t, k) for t, k in todo]
    if None in spots:
        return _refuse("Row layout uses a form this patch does not edit.", path)
    new = text
    for at in sorted(spots, reverse=True):
        new = new[:at] + _glue(new, at) + TOKEN + new[at:]
    expect = tomllib.loads(text)
    a = expect["ui"]["sidebar"]["agents"]
    for _, k in todo:
        (a["rows"] if k == "rows" else a["rows_by_agent"]["claude"])[-1].append("$tokens")
    return _finish(path, text, new, expect)


def _finish(path: Path, old: str, new: str, expect: dict) -> Plan:
    try:
        parsed = tomllib.loads(new)
    except tomllib.TOMLDecodeError:
        return _refuse("Patched config failed validation.", path)
    if parsed != expect:
        return _refuse("Patched config failed validation.", path)
    diff = difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{path.name}", f"b/{path.name}")
    return Plan("patch", "".join(diff), new)


def _emit(res: Plan) -> int:
    print(res.diff or res.message, end="", file=sys.stderr if res.status == "refuse" else sys.stdout)
    return 1 if res.status == "refuse" else 0


def apply(path: Path) -> int:
    res = plan(path)
    if res.status != "patch":
        return _emit(res)
    real = Path(os.path.realpath(path))  # patch the symlink target; the link stays intact
    mode = real.stat().st_mode & 0o777
    backup = real.with_name(f"{real.name}.bak-{time.strftime('%Y%m%dT%H%M%S')}-{time.time_ns() % 10**6:06d}")
    with open(real, "rb") as src, open(backup, "xb") as fh:
        shutil.copyfileobj(src, fh)
    os.chmod(backup, mode)
    fd, tmp = tempfile.mkstemp(dir=real.parent, prefix=f".{real.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(res.new_text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        replace_with_retry(tmp, real)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    print("patched (backup written next to the config)")
    return 0


def default_config_path(environ=None, os_name=None, home=None) -> Path:
    """HERDR_CONFIG_PATH > $XDG_CONFIG_HOME > %APPDATA% (Windows only) > ~/.config. Raises RuntimeError without a home."""
    env = os.environ if environ is None else environ
    if env.get("HERDR_CONFIG_PATH"):
        return Path(env["HERDR_CONFIG_PATH"])
    if env.get("XDG_CONFIG_HOME"):
        return Path(env["XDG_CONFIG_HOME"]) / "herdr" / "config.toml"
    if (os_name or os.name) == "nt" and env.get("APPDATA"):
        return Path(env["APPDATA"]) / "herdr" / "config.toml"
    return (home or Path.home)() / ".config" / "herdr" / "config.toml"


def main(args: list[str]) -> int:
    flags = [a for a in args if a in ("--print", "--apply")]
    rest = [a for a in args if a not in ("--print", "--apply")]
    if len(flags) != 1 or (rest and not (len(rest) == 2 and rest[0] == "--config")):
        print("usage: main.py sidebar-patch --print|--apply [--config PATH]", file=sys.stderr)
        return 2
    try:
        path = Path(rest[1]) if rest else default_config_path()
    except (RuntimeError, KeyError, OSError):
        print("sidebar-patch: cannot locate the home directory; pass --config PATH", file=sys.stderr)
        return 1
    if flags[0] == "--apply":
        return apply(path)
    return _emit(plan(path))
