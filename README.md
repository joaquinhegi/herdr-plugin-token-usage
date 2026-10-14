# Token Usage (Herdr plugin)

Shows the running token total of each Claude pane as a `$tokens` sidebar token (e.g. `125.4k tokens`).

- Total = input + output + cache_creation + cache_read. Thinking tokens are inside output; subagent transcripts count in the parent session.
- Claude only: Codex panes show nothing. Panes without a reliable session mapping show nothing (never `0`).
- Reads `~/.claude/projects` read-only (the transcripts of sessions Herdr reports). Writes only its state dir and Herdr pane metadata. See `docs/SECURITY.md`.

## Requirements

Python >= 3.10 as `python3` on the PATH Herdr uses (macOS `/usr/bin/python3` is 3.9 and exits with an error). Stdlib only.

## Install

```
herdr plugin link /path/to/this/repo
herdr plugin enable local.token-usage
```

The poller starts from `[[startup]]`. Actions: `start`, `stop`, `status`. Reload: run `stop` then `start`.

## Sidebar

Herdr shows `$tokens` only if a sidebar row contains it. Preview first, nothing is written:

```
python3 src/main.py sidebar-patch --print [--config PATH]
python3 src/main.py sidebar-patch --apply [--config PATH]   # backup config.toml.bak-<timestamp>, then atomic replace
```

Default config: `~/.config/herdr/config.toml`. The patch adds `"$tokens"` to the last row of `rows_by_agent.claude`, else of `rows`; with no `[ui.sidebar.agents]` it appends a minimal section. If it cannot edit safely it refuses and prints manual steps. It never runs at startup.

## Logs, disable, uninstall

- Logs: `herdr plugin log list`, plus `<state dir>/token-usage.log` (events and counts only, never content or paths).
- Disable: `herdr plugin disable local.token-usage` (the poller clears its tokens on stop).
- Uninstall: `herdr plugin unlink local.token-usage` (linked) or `herdr plugin uninstall local.token-usage` removes only plugin files and state. Revert the sidebar patch by restoring its `.bak-*` backup (or deleting the `"$tokens"` entry); nothing else is touched.
