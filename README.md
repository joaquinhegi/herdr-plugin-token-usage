# Token Usage — Herdr plugin

[![CI](https://github.com/joaquinhegi/herdr-plugin-token-usage/actions/workflows/ci.yml/badge.svg)](https://github.com/joaquinhegi/herdr-plugin-token-usage/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Platforms](https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows%20(experimental)-lightgrey)
![Dependencies](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A [Herdr](https://herdr.dev) plugin that shows the cumulative token usage of every Claude Code session right in the agents sidebar, for example `125.4k tokens`.

- **Per session, never mixed.** Each pane shows only the tokens of the session Herdr reports for it.
- **Local and offline.** No network, no telemetry. It reads Claude transcripts read-only and stores only ids, offsets and counters.
- **No dependencies.** Python standard library only.

## Platform support

| Platform | Status | Notes |
|---|---|---|
| macOS | Supported | Tested in CI and validated manually on a live Herdr install |
| Linux | Supported | Tested in CI; not yet validated manually |
| Windows | Experimental | Tested in CI on `windows-latest`; not yet validated on a real Windows machine with a live Herdr. Needs manual validation before it can be called supported (see [Windows](#windows-experimental)) |

Requirements: Herdr 0.8.2 or later, and Python 3.11 or later available as `python3` on the `PATH` Herdr uses (on Windows, see [Windows](#windows-experimental)). On macOS, `/usr/bin/python3` is 3.9; install a newer Python (for example with Homebrew) or the plugin exits with a clear message.

## What the number means

```
total = input + output + cache_creation + cache_read
```

- Thinking tokens are already part of `output` and are not counted twice.
- Subagent transcripts count toward their parent session.
- Repeated log lines for the same API response are counted once (deduplicated by message id).
- Only Claude Code panes show a figure. Codex panes, unmapped panes and empty sessions show nothing, never a misleading `0`.

## Install

From GitHub:

```sh
herdr plugin install joaquinhegi/herdr-plugin-token-usage
herdr plugin enable local.token-usage
herdr plugin action invoke start --plugin local.token-usage
```

From a local clone:

```sh
git clone https://github.com/joaquinhegi/herdr-plugin-token-usage
herdr plugin link /path/to/herdr-plugin-token-usage
herdr plugin enable local.token-usage
herdr plugin action invoke start --plugin local.token-usage
```

Herdr runs the plugin's startup hook only when it restores a session, so start the poller once after enabling. From then on it starts automatically. No Herdr restart is needed.

Check that it is running:

```sh
herdr plugin action invoke status --plugin local.token-usage
herdr plugin log list --plugin local.token-usage --limit 1   # running pid=… last_tick=… panes=N
```

## Windows (experimental)

Windows support is implemented and tested in CI, but has not been validated on a real machine yet. Treat it as experimental.

- **Python launcher.** The plugin starts through the `py` launcher (`py -3`). Install Python from python.org or with the Python install manager, which provide `py.exe`. A Python installed only from the Microsoft Store does not include `py.exe`.
- **Python 3.11 or later.** `py -3` selects the newest Python 3 it finds; if that is older than 3.11, the plugin exits with a clear message instead of starting.
- **Actions.** Windows has its own actions: `start-windows`, `stop-windows` and `status-windows`. Use them instead of `start`, `stop` and `status`:

  ```sh
  herdr plugin action invoke start-windows --plugin local.token-usage
  herdr plugin action invoke status-windows --plugin local.token-usage
  herdr plugin action invoke stop-windows --plugin local.token-usage
  ```

- **Herdr binary.** `HERDR_BIN_PATH` must be an absolute path to `herdr.exe`. Other file types are rejected.
- **Herdr config.** The default config path used by `sidebar-patch` is `%APPDATA%\herdr\config.toml` (still overridable with `$HERDR_CONFIG_PATH` or `$XDG_CONFIG_HOME`).
- **Transport.** The plugin talks to Herdr through the CLI only; it does not use the Unix socket on Windows.
- **Stopping.** `stop-windows` asks the poller to exit through a stop file. If the poller does not exit within the wait budget, a guarded force-terminate runs (see [`docs/SECURITY.md`](docs/SECURITY.md)).

## Show it in the sidebar

Herdr displays `$tokens` only when a sidebar row includes it. Herdr's default sidebar rows ship commented out in `herdr --default-config`, so most configs need this once. Add it to your Herdr config (`~/.config/herdr/config.toml`, `%APPDATA%\herdr\config.toml` on Windows, or `$HERDR_CONFIG_PATH`):

```toml
[ui.sidebar.agents]
rows = [["state_icon", "workspace", "tab"], ["agent", "$tokens"]]
```

If your config already has `[ui.sidebar.agents]` rows, add `"$tokens"` to the agent row instead. Then apply it live:

```sh
herdr config check
herdr server reload-config
```

The plugin also ships a helper that edits an existing rows section for you. It previews a diff first and backs up the file before writing:

```sh
python3 src/main.py sidebar-patch --print [--config PATH]   # preview, writes nothing
python3 src/main.py sidebar-patch --apply [--config PATH]   # backup config.toml.bak-<timestamp>, then atomic replace
```

It never creates a rows section, since that would replace Herdr's default layout. It is idempotent, keeps comments and symlinks, and never runs at startup.

## How it works

```
every 4 s:  herdr pane list ──► pane → Claude session id (agent_session, strict UUID)
                                   │
            ~/.claude/projects/*/<session>.jsonl  (+ subagents/agent-*.jsonl)
                                   │  incremental read from the last offset
                                   ▼
            dedupe by message id ──► per-session total ──► herdr pane report-metadata
                                                           --token tokens=<value> --ttl-ms 60000
```

- A single detached poller runs per Herdr server, guarded by a file lock. `start` is idempotent and hands over cleanly when the Herdr socket changes.
- Published values are refreshed every 20 s with a 60 s TTL, so a stopped poller never leaves stale numbers behind.
- If Herdr is unreachable, the plugin skips that tick and clears nothing. If it stays unreachable for 5 minutes, the poller exits.

## Testing

| Layer | Tests | Scope |
|---|---|---|
| Unit | 50 | Token accounting, dedupe ledger, formatting, session mapping, reconcile rules, parsers |
| Adapters | 79 | Transcript tailer, state store, Claude locator, Herdr CLI and socket clients, logging privacy |
| Scenarios | 24 | Full poll ticks with fakes: two sessions, resume after restart, corrupt transcripts, Herdr down |
| Lifecycle | 136 | Daemon lock and handoff, host adapters, stop flow, terminate guard, entrypoint errors, manifest, sidebar patch |
| Support | 3 | Shared test helpers |
| **Total** | **292** | |

- **CI:** GitHub Actions on Ubuntu, macOS and Windows with Python 3.11 and 3.13. On Windows, 35 POSIX-specific tests are skipped with a reason, for example flock, Unix sockets and file modes; on macOS and Linux, 8 Windows-only tests are skipped.
- **Method:** built test-first. Each slice was verified independently against the spec, including deliberate mutations to confirm the tests catch regressions.
- **Run locally:**

  ```sh
  python3 -B -m unittest discover
  ```

## Security

- Reads only `~/.claude/projects` (`%USERPROFILE%\.claude\projects` on Windows), read-only, after resolving symlinks and checking the result stays inside that directory.
- Writes only to the plugin's state directory and to Herdr pane metadata.
- Runs subprocesses with argument lists only: no shell, absolute verified binary paths, timeouts.
- Logs contain event names and counts, never transcript content or paths.

See [`docs/SECURITY.md`](docs/SECURITY.md) for the threat model and residual risks.

## Operations

- **Logs:** `herdr plugin log list --plugin local.token-usage`, plus `<state dir>/token-usage.log`.
- **Restart:** run the `stop` action, then `start`.
- **Disable:** run the `stop` action first, so the poller clears its tokens and exits. Then run `herdr plugin disable local.token-usage`.
- **Uninstall:** run the `stop` action, then `herdr plugin unlink local.token-usage` (linked) or `herdr plugin uninstall local.token-usage`. Remove the plugin state directory if it is left behind.
- **Shell fallback for stop:** `HERDR_PLUGIN_STATE_DIR=<state dir> python3 -B src/main.py stop` (on Windows, `py -3 -X utf8 -B src/main.py stop`).
- **Revert the sidebar change:** remove the `"$tokens"` entries, or restore the `.bak-*` backup next to the config.

## Known limitations

- **Claude Code only.** Codex sessions are not tracked yet.
- **Detached poller.** The plugin keeps a detached background poller (on Windows, a hidden detached process). Herdr's plugin docs ask plugins to stop detached processes before their parent command exits. Herdr 0.8.2 does not enforce this; if a future version does, the poller would need a redesign.
- **Windows is experimental.** It has not been validated on a real Windows machine with a live Herdr; see [Windows](#windows-experimental).
- **`CLAUDE_CONFIG_DIR` is not supported (all platforms).** Transcripts are read only from `~/.claude/projects`; a relocated Claude config directory is not followed.
- **Forced stops leave stale values.** After a forced stop, the sidebar values disappear when their 60 s TTL expires.

## Development

```
src/token_usage/
  domain/      pure logic: usage, ledger, mapping, reconcile, formatting
  sources/     Claude and Codex line parsers
  adapters/    Herdr CLI/socket, transcript tailer, locator, state store, logging
  app/         TickService: one poll tick
  lifecycle/   daemon, host platform port, sidebar patch
tests/         unit, adapters, scenarios, lifecycle
openspec/      specs, designs and verification reports for each change
```

Changes go through pull requests against `main`, and CI must pass. The maintainer reviews and merges them. Run the test suite before opening one.

## License

[MIT](LICENSE)
