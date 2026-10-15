"""Print-first, minimal sidebar patch (plus `--install`, the GitHub-install setup): adds `$tokens` to existing agent rows only.

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
STYLED_TOKEN = '{ token = "$tokens", fg = "#f9e2af", bold = true }'
STYLED_VALUE = {"token": "$tokens", "fg": "#f9e2af", "bold": True}
# Herdr 0.8.2 default rows (`herdr --default-config`) plus the styled token.
DEFAULT_ROWS = f'[["state_icon", "workspace", "tab"], ["agent", {STYLED_TOKEN}]]'
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


def _has_token(row) -> bool:
    return any(x == "$tokens" or (isinstance(x, dict) and x.get("token") == "$tokens") for x in row)


def plan(path: Path, styled: bool = False) -> Plan:
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
    todo = [(t, k) for t, k, r in targets if not any(_has_token(row) for row in r)]
    if not todo:
        return Plan("noop", message="$tokens is already present.\n")
    spots = [_locate(text, t, k) for t, k in todo]
    if None in spots:
        return _refuse("Row layout uses a form this patch does not edit.", path)
    new = text
    for at in sorted(spots, reverse=True):
        new = new[:at] + _glue(new, at) + (STYLED_TOKEN if styled else TOKEN) + new[at:]
    expect = tomllib.loads(text)
    a = expect["ui"]["sidebar"]["agents"]
    for _, k in todo:
        (a["rows"] if k == "rows" else a["rows_by_agent"]["claude"])[-1].append(STYLED_VALUE if styled else "$tokens")
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


def _write(real: Path, text: str, backup: bool) -> None:
    """Atomic replace; with `backup` the existing file is copied to `.bak-<timestamp>` first."""
    mode = (real.stat().st_mode & 0o777) if backup else 0o600
    if backup:
        bak = real.with_name(f"{real.name}.bak-{time.strftime('%Y%m%dT%H%M%S')}-{time.time_ns() % 10**6:06d}")
        with open(real, "rb") as src, open(bak, "xb") as fh:
            shutil.copyfileobj(src, fh)
        os.chmod(bak, mode)
    fd, tmp = tempfile.mkstemp(dir=real.parent, prefix=f".{real.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        replace_with_retry(tmp, real)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def apply(path: Path) -> int:
    res = plan(path)
    if res.status != "patch":
        return _emit(res)
    _write(Path(os.path.realpath(path)), res.new_text, True)  # patch the symlink target; the link stays intact
    print("patched (backup written next to the config)")
    return 0


def _install_plan(path: Path) -> Plan:
    real = Path(os.path.realpath(path))
    try:
        text = real.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Plan("create", new_text=f"[ui.sidebar.agents]\nrows = {DEFAULT_ROWS}\n")
    except (OSError, UnicodeDecodeError):
        return _refuse("Config cannot be read as a UTF-8 file.", path)
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return _refuse("Config is not valid TOML.", path)
    ui = data.get("ui", {})
    sidebar = ui.get("sidebar", {}) if isinstance(ui, dict) else None
    if isinstance(sidebar, dict) and "agents" not in sidebar:
        section = f"[ui.sidebar.agents]\nrows = {DEFAULT_ROWS}\n"
        new = text + ("\n" if text and not text.endswith("\n") else "") + ("\n" if text else "") + section
        expect = tomllib.loads(text)
        expect.setdefault("ui", {}).setdefault("sidebar", {})["agents"] = tomllib.loads(section)["ui"]["sidebar"]["agents"]
        res = _finish(path, text, new, expect)
        return Plan("append", res.diff, new) if res.status == "patch" else res
    return plan(path, styled=True)


def install(path: Path) -> int:
    """Configure the sidebar for a GitHub install. Always returns 0: config problems never fail the install."""
    try:
        res = _install_plan(path)
        if res.status in ("create", "append", "patch"):
            real = Path(os.path.realpath(path))
            if res.status == "create":
                real.parent.mkdir(parents=True, exist_ok=True)
                tomllib.loads(res.new_text)
            _write(real, res.new_text, res.status != "create")
            print(f"sidebar configured in {path}; run `herdr server reload-config` to apply it live"
                  + ("" if res.status == "create" else " (backup written next to the config)"))
        else:
            print(res.message, end="")
    except (OSError, ValueError):
        print(_manual(path, "The config could not be written."), end="")
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
    modes = ("--print", "--apply", "--install")
    flags = [a for a in args if a in modes]
    rest = [a for a in args if a not in modes]
    if len(flags) != 1 or (rest and not (len(rest) == 2 and rest[0] == "--config")):
        print("usage: main.py sidebar-patch --print|--apply|--install [--config PATH]", file=sys.stderr)
        return 2
    try:
        path = Path(rest[1]) if rest else default_config_path()
    except (RuntimeError, KeyError, OSError):
        msg = "sidebar-patch: cannot locate the home directory; pass --config PATH"
        print(msg + (" (install continues without configuring the sidebar)" if flags[0] == "--install" else ""),
              file=sys.stdout if flags[0] == "--install" else sys.stderr)
        return 0 if flags[0] == "--install" else 1
    if flags[0] == "--install":
        return install(path)
    if flags[0] == "--apply":
        return apply(path)
    return _emit(plan(path))
