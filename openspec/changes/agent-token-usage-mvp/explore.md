# Exploration: agent-token-usage-mvp (Phase 1 — Inspection)

Sources: herdr.dev docs, release notes, installed reference plugin manifest (permgps.telegram-agents), installed Herdr Claude hook, key-only inspection of local Claude transcripts, and read-only `herdr` CLI checks on the local binary (0.8.2).

## Local verification (herdr 0.8.2)

- `herdr --version` → `herdr 0.8.2`.
- `herdr pane report-metadata --help` → flags confirmed: `--source <ID>` (required), `--agent`, `--applies-to-source`, `--title`/`--clear-title`, `--display-agent`/`--clear-display-agent`, `--state-label`/`--clear-state-labels`, `--token NAME=VALUE`, `--clear-token NAME`, `--seq`, `--ttl-ms`.
- `herdr plugin list --json` → plugin system active; manifest fields `actions`, `build`, `startup`, `panes`, `platforms`, `min_herdr_version` confirmed.
- `herdr pane list` → pane keys: `agent`, `agent_session`, `agent_status`, `cwd`, `focused`, `foreground_cwd`, `pane_id`, `revision`, `scroll`, `tab_id`, `terminal_id`, `terminal_title`, `terminal_title_stripped`, `workspace_id`. Live Claude panes report `agent_session = {source: "herdr:claude", agent: "claude", kind: "id", value: <36-char session UUID>}`. Panes without an agent have no `agent_session`.

## Q1 — Plugin contract (high)

- Manifest `herdr-plugin.toml`; required `id`, `name`, `version`, `min_herdr_version`; sections `[[build]]`, `[[startup]]`, `[[actions]]`, `[[events]]`, `[[panes]]`, `[[link_handlers]]`.
- Commands are argv (no shell); Python works: `command = ["python3", "src/main.py"]`.
- `[[startup]]` is one-shot after session restore and re-runs on live handoff; not supervised. No managed long-running process: plugins self-detach a daemon (pidfile + start/stop actions).
- `[[events]]` are short-lived; only `worktree.created` documented, payload undocumented.
- Env: `HERDR_SOCKET_PATH`, `HERDR_BIN_PATH`, `HERDR_ENV=1`, `HERDR_PLUGIN_ID`, `HERDR_PLUGIN_ROOT`, `HERDR_PLUGIN_CONFIG_DIR`, `HERDR_PLUGIN_STATE_DIR`, `HERDR_PLUGIN_CONTEXT_JSON`, `HERDR_WORKSPACE_ID`, `HERDR_TAB_ID`, `HERDR_PANE_ID`, `HERDR_PLUGIN_EVENT[_JSON]`.
- Local dev: `herdr plugin link <path>` (skips build); `enable`, `disable`, `list --json`, `uninstall`, `config-dir`, `log list`.

## Q2 — Pane metadata (high, verified locally)

- Limits (docs): source ≤80 chars `[A-Za-z0-9:._-]`; token name 1–32 `[A-Za-z0-9_-]`; value ≤80 chars; ≤16 keys/report; 32 retained keys and 32 sources per pane; `--ttl-ms` 1..86400000 per key; `--seq` drops out-of-order reports.
- Clear via `--clear-token tokens` (CLI) or `null` (socket `pane.report_metadata`).
- Sidebar: `"$tokens"` in `[ui.sidebar.agents].rows`; `rows_by_agent.claude|codex` replaces `rows` entirely; max 16 rows × 16 tokens.
- `~/.config/herdr/config.toml` does not exist today.
- Unverified: whether an absent `$tokens` collapses cleanly in a row.

## Q3 — Pane ↔ agent ↔ session (high for Claude)

- `agent_session` is populated only by an official integration. The Claude integration is already installed (`~/.claude/hooks/herdr-agent-state.sh`), reporting the Claude `session_id` per `HERDR_PANE_ID`, skipping subagents.
- Verified `kind: "id"` with a UUID value → maps strictly to `~/.claude/projects/*/<uuid>.jsonl`. No cwd heuristics needed; MVP does not touch Claude settings.
- Codex: same mechanism via `herdr integration install codex`, which edits `~/.codex` hooks/config (forbidden in MVP without approval). `~/.codex` does not exist locally.
- Fallbacks without integration: cwd alone (forbidden) or pid → `lsof` on open rollout file (macOS-only, weaker).
- Unverified: behaviour on `claude --resume`; whether `agent_session` clears on agent exit.

## Q4 — Claude usage format (high, local evidence)

- Transcripts: `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl`; `sessionId` == filename UUID.
- Subagents: separate files `<session>/subagents/agent-*.jsonl` with `isSidechain: true`.
- Assistant lines carry `message.id`, `requestId`, `uuid`, `parentUuid`, `message.model`, `message.stop_reason`, `message.usage`.
- `usage`: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_creation{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`, `server_tool_use`, `service_tier`, `output_tokens_details.thinking_tokens` (already inside `output_tokens` — do not add).
- Per-call, not cumulative. Confirmed duplication: one response spans several lines sharing `message.id` + `requestId` with identical usage → dedupe by `message.id` (fallback `requestId`), keep max per id.
- Skip `<synthetic>` and API-error lines. Compaction keeps earlier lines in the same file.
- `cache_read` dominates long sessions; total definition is a product decision.
- Unverified: resume behaviour (same file vs new file with copied history).

## Q5 — Codex usage format (medium, docs only)

- `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (archived flat under `archived_sessions/`; possible `.jsonl.zst` variant, unverified).
- Envelope `{timestamp, type, payload}`; session id in `session_meta` payload.
- `event_msg` with `payload.type = "token_count"`, nullable `info{total_token_usage (cumulative), last_token_usage, model_context_window}`.
- `TokenUsage{input_tokens, cached_input_tokens, cache_write_input_tokens, output_tokens, reasoning_output_tokens, total_tokens}`; cached tokens reportedly inside `input_tokens`.
- Use the latest `total_token_usage`; never sum snapshots; skip identical re-emissions; forked rollouts copy parent history.

## Q6 — Feasibility and gaps

- Feasible now: Python plugin, `$tokens` via pane metadata, strict Claude mapping, persisted state in `HERDR_PLUGIN_STATE_DIR`.
- Gap: Codex pane mapping requires the official integration (approval) — otherwise defer or show nothing.
- Gap: no supervised process → self-detached poller from startup hook with pidfile, stop action and duplicate guard on handoff re-run.
- Cost: deferred out of MVP.

## Approaches

1. **Self-detached stdlib Python poller + socket client** (recommended): every 3–5 s `pane.list` → `agent_session` → incremental tail by offset with `message.id` dedupe → `pane.report_metadata` only on change, with TTL.
2. Event hooks only — not viable (no event on transcript growth).
3. Poller + `pane.closed`/`agent_detected` events — faster cleanup, larger surface, undocumented payloads.

## Open decisions

1. Total definition: include cache tokens or not.
2. Subagent transcripts counted in the session total or not.
3. Codex: install official integration or defer pane mapping.
