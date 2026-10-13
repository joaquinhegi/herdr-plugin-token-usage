# Proposal: Agent Token Usage MVP

## Intent

Herdr users running parallel agents cannot see per-session cumulative token usage without leaving the sidebar. Show a reliable `$tokens` figure (e.g. `125.4k tokens`) per Claude pane, never attributing another session's usage.

## Scope

### In Scope
- Plugin manifest (`[[startup]]`, start/stop/status actions) and self-detached stdlib poller (pidfile, duplicate guard on handoff re-run).
- Herdr client: socket API (`HERDR_SOCKET_PATH`), CLI fallback (`HERDR_BIN_PATH`).
- Strict Claude mapping via `agent_session` (`kind: id`, UUID) to `<uuid>.jsonl` plus `subagents/agent-*.jsonl`.
- Claude parser: per-call usage, dedupe by `message.id` (fallback `requestId`, max per id), skip `<synthetic>`/errors.
- Codex parser: latest cumulative `total_token_usage`, fixture-tested only.
- Incremental offset tail with rotation/truncation detection; persisted state (offsets, per-id counters, minimal ids).
- Publish `tokens` only on change, with TTL; clear on pane close or session change.
- Formatting: `950 tokens`, `1.3k tokens`, `1.2M tokens`.
- Sidebar `config.toml` patch: backup + diff, approval-gated, never auto-applied.
- README (total definition, inspected directories), SECURITY.md, install/reload/uninstall instructions.

### Out of Scope
- Cost (`$cost`).
- Codex pane mapping (no `herdr integration install codex`, no `~/.codex` changes).
- Dashboards, global daemons beyond the plugin poller, event-hook cleanup.

## Non-Negotiables

- Offline; no network, telemetry, or dependencies.
- Read-only access to transcripts; writes only to `HERDR_PLUGIN_STATE_DIR` and Herdr metadata.
- No persisted conversation content; no edits to Claude/Codex settings or hooks.

## Capabilities

### New Capabilities
- `plugin-lifecycle`: manifest, detached poller, pidfile, start/stop/status.
- `session-mapping`: strict pane-to-session resolution; no figure when ambiguous.
- `usage-accounting`: provider parsers, dedupe, processed-token total, incremental state.
- `sidebar-metadata`: formatting, publish/clear, TTL, approval-gated config patch.

### Modified Capabilities
None.

## Approach

Exploration Approach 1: a poll loop every 3–5 s reads `pane.list`, resolves sessions, tails new bytes, and reports metadata on change. Total = input + output + cache_creation + cache_read (thinking already inside output).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `herdr-plugin.toml` | New | Manifest |
| `src/` | New | lifecycle, client, resolver, sources, state |
| `tests/` | New | Synthetic fixtures only |
| `README.md`, `docs/SECURITY.md` | New | Docs |

## Size Forecast

About 1,300–1,800 changed lines including tests, so this exceeds the 400-line budget. Chained slices: parsers + model, state + tail, mapping + client, lifecycle + publishing, docs + config patch.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Undocumented `claude --resume` file behavior | Med | Key on session UUID; tests |
| Orphaned or duplicate poller | Med | Pidfile, liveness check, stop action |
| Absent `$tokens` row layout | Low | Patch shown for review only |

## Rollback Plan

Run the stop action, then `herdr plugin disable`/`uninstall`. Delete only the plugin state dir. Clear the `tokens` metadata (TTL also expires it). Restore the `config.toml` backup if a patch was applied.

## Dependencies

- herdr >= 0.8.2 with the Claude integration installed.

## Success Criteria

- [ ] Two Claude panes in the same repo show independent, growing totals.
- [ ] The figure survives a Herdr restart and resume of the same session.
- [ ] Replay and duplicate lines are never double-counted.
- [ ] A new session or a closed pane clears the old value.
- [ ] Codex panes show no figure; no files outside the state dir are written.
