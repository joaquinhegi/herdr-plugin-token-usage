# Token Usage (Herdr plugin)

Shows the running token total of each Claude pane as a `$tokens` sidebar token (e.g. `125.4k tokens`).

- Total = input + output + cache_creation + cache_read. Thinking tokens are inside output; subagent transcripts count in the parent session.
- Claude only: Codex panes show nothing. Panes without a reliable session mapping show nothing (never `0`).
- Reads `~/.claude/projects` read-only (the transcripts of sessions Herdr reports). Writes only its state dir and Herdr pane metadata. See `docs/SECURITY.md`.

## Requirements

Python >= 3.11 (for `tomllib`) as `python3` on the PATH Herdr uses (macOS `/usr/bin/python3` is 3.9 and exits with an error). Stdlib only.

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
python3 src/main.py sidebar-patch --apply [--config PATH]   # backup config.toml.bak-<timestamp> (same mode), then atomic replace
```

Default config: `~/.config/herdr/config.toml`. The patch adds `"$tokens"` to the last row of `rows` and of `rows_by_agent.claude` (each only when it exists; re-runs are no-ops). A symlinked config is patched at its target and the link is kept. It never creates a rows section, because that would replace Herdr's default layout: with no config file or no `[ui.sidebar.agents]` rows it refuses (exit 1, nothing written) and prints manual steps. Run `herdr --default-config`, paste its `[ui.sidebar.agents]` rows into your config, add `"$tokens"` to the agent row, then re-run `sidebar-patch --print`. It never runs at startup.

## Logs, disable, uninstall

- Logs: `herdr plugin log list`, plus `<state dir>/token-usage.log` (events and counts only, never content or paths).
- Disable: `herdr plugin disable local.token-usage` (the poller clears its tokens on stop).
- Uninstall: first run the plugin's `stop` action (or `python3 -B src/main.py stop`) so no poller is left running, then `herdr plugin unlink local.token-usage` (linked) or `herdr plugin uninstall local.token-usage`. Herdr removes the plugin files; if `$HERDR_PLUGIN_STATE_DIR` is left behind, remove it manually.
- Revert the sidebar patch by removing the `"$tokens"` entries or restoring the `.bak-*` backup next to the config. The patch only edits an existing config, so if no backup exists it never changed your file; nothing else is touched.
