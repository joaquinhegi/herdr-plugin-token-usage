# Exploration: windows-support

Full text also in Engram `sdd/windows-support/explore`.

## Current State

- Manifest commands are `["python3","-B","src/main.py",...]` and no `platforms` is declared (`herdr-plugin.toml:11,16,21,26`).
- `start` spawns a detached poller guarded by `fcntl.flock` on `poller.lock`; the poller writes its pid into that file. `stop` sends SIGTERM after a pidfile/lock-file pid match (`src/token_usage/lifecycle/daemon.py`).
- Pane listing tries an `AF_UNIX` socket, then the CLI; metadata writes always use the CLI (`HERDR_BIN_PATH`).

## Observed on Windows

`herdr plugin install` + `enable` succeed; `start`/`status` fail with exit 9009 because `python3` resolves to the Microsoft Store app alias.

## Herdr facts (herdr.dev/docs/plugins, github.com/herdrdev/herdr `master`)

1. `platforms = ["linux","macos","windows"]` at top level; startup, actions, events, panes, build and link handlers may declare their own `platforms` (item-level overrides top-level). There is no per-platform `command`. Ids must be unique inside a plugin, even across platforms. The install warning appears when top-level `platforms` is missing.
2. `command[0]` on Windows: names containing a separator resolve against the plugin root; bare names are searched on `PATH` with `PATHEXT`; `.bat`/`.cmd` run through `cmd.exe /d /c`.
3. Process model: stdio piped, `child.wait()` without timeout, no job object; detached grandchildren survive; background commands spawn with `CREATE_NO_WINDOW`.
4. Documented rule (verified on herdr.dev/docs/plugins): "Plugins must stop detached background processes before their parent command or pane exits." Startup hooks are "one-shot initialization commands rather than supervised daemons". The current detached poller does not follow this rule on any OS; the runtime does not enforce it today.
5. Socket on Windows is a named pipe `\\.\pipe\` + `HERDR_SOCKET_PATH`. CPython has no `socket.AF_UNIX` on Windows; the CLI fallback is sufficient.
6. Config: `XDG_CONFIG_HOME\herdr` else `%APPDATA%\herdr\config.toml`; `HERDR_CONFIG_PATH` overrides.
7. Claude integration supports Windows (PowerShell hook; `CLAUDE_CONFIG_DIR` or `%USERPROFILE%\.claude`). `agent_session` is produced server-side (unverified on a real Windows machine). Transcripts expected under `%USERPROFILE%\.claude\projects\<slug>\<uuid>.jsonl`.

## Python on Windows

- `py` is the launcher both installers provide; no `python3.exe` from the traditional installer. Proposed argv: `["py","-3","-X","utf8","-B","src/main.py",...]` (`main.py` already rejects < 3.11).
- `os.kill(pid, sig)` for any signal other than CTRL_C/CTRL_BREAK calls TerminateProcess; `os.kill(pid, 0)` kills. Ctrl events do not cross separate hidden consoles. Use a stop file polled by the loop; liveness via lock probe only.
- `msvcrt.locking` is mandatory byte-range locking released on handle close/process death: the pid cannot be read from the locked range (`daemon._lock_pid`).
- Spawn with `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` (not `DETACHED_PROCESS`, which would flash a console on every `herdr.exe` call).
- `os.replace` can raise `PermissionError` while the target is open (needs retry); directory fsync impossible (already best effort); `chmod` only toggles read-only; `X_OK` is existence-only.

## POSIX assumptions (file:line → Windows equivalent)

| file:line | Assumption | Windows equivalent |
|---|---|---|
| `herdr-plugin.toml` | `python3` | item-level `platforms`; Windows items use `py -3 -X utf8`; distinct ids |
| `daemon.py:12,43` | `fcntl.flock` | `msvcrt.locking(LK_NBLCK)` behind a lock port |
| `daemon.py:54,61,116-117,124` | pid inside locked file, `ftruncate` | pid only in pidfile, or outside the locked range |
| `daemon.py:103-105` | `SIGHUP` (AttributeError → crash) | guard; stop file |
| `daemon.py:187-189` | `kill(pid, SIGTERM)` | stop file; optional TerminateProcess after identity check |
| `daemon.py:205` | `start_new_session=True` | `CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW` |
| `herdr_socket.py:43`, `herdr_fallback.py:20` | `AF_UNIX`; fallback catches only HerdrError/OSError (AttributeError → never falls back, orphan exit after 300 s) | do not build `HerdrSocket` on Windows, or catch it |
| `herdr_cli.py:45` | `subprocess.run` | add `CREATE_NO_WINDOW` |
| `state_store.py:31-39,58` | dir fsync, `os.replace` | no-op; retry on PermissionError |
| `sidebar_patch.py:183` | `~/.config/herdr/config.toml` | honor `XDG_CONFIG_HOME`; Windows `%APPDATA%\herdr\config.toml` |
| `main.py:41` | `~/.claude/projects` | works; `CLAUDE_CONFIG_DIR` ignored on every OS (existing gap) |

Tests not portable: `test_daemon.py` (module-level `fcntl`, SIGHUP, SIGKILL, `#!/bin/sh` fakes, env without `SYSTEMROOT`), `herdr_fakes.py` (shebang fake bin, `/tmp`, AF_UNIX server), `test_main.py` (shebang), `test_herdr_cli.py` (X_OK/chmod), `test_tick.py` (`os.geteuid` at import, `chmod(0)`), `test_sidebar_patch.py` (modes, symlink), `test_claude_locator.py` (symlinks), `test_state_store.py` (fsync call count), `test_herdr_socket.py` (`/tmp`), `test_manifest.py` (`python3`).

## Approaches

| Approach | Summary | Effort / risk |
|---|---|---|
| A. Platform port | lock, spawn, stop-request and signal install behind one port with POSIX and Windows adapters; Windows manifest items; socket disabled on Windows; stop-file protocol; Windows CI | Medium (~250–400 lines) / Medium |
| B. Declare platforms only | `platforms = ["linux","macos"]` plus README note | Low / Low |
| C. Wrapper launcher | relative `.cmd`/sh wrapper as `command[0]` | Medium / High (PATHEXT on relative paths unverified, cmd quoting) |

Testing from macOS: injected platform adapters; fake herdr as `[sys.executable, fake.py]`; `skipUnless(os.name == "posix")` for POSIX-only tests; GitHub Actions `windows-latest` (free for public repos).

## Recommendation

B now as a small PR, then A in chained slices: (1) platform port + POSIX adapter, (2) Windows adapter + manifest + socket guard, (3) test portability + Windows CI, (4) README and sidebar-patch Windows config path.

## Risks

- Documented Herdr rule against detached background processes (all OSes).
- Possible kill-on-close job (needs `CREATE_BREAKAWAY_FROM_JOB`), unverified.
- Fast pid reuse on Windows: any TerminateProcess fallback needs lock + pidfile identity.
- Mandatory locking / `os.replace` sharing violations.
- `py` missing if the launcher was not installed.

## Open questions

1. B first as its own PR, or straight to A?
2. Windows stop: stop file only, or also last-resort TerminateProcess?
3. Separate Windows action ids acceptable in the palette?
4. `py -3` or `py -3.11`?
5. Accept the detached-process rule as a known risk, or rethink where the poller runs?
