# Tasks: Agent Token Usage MVP

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,900 total: S1 330, S2 380, S3 390, S4 320, S5 330, S6 150 (+ manual validation) |
| 400-line budget risk | High (total); Low-Medium per slice |
| Chained PRs recommended | Yes |
| Suggested split | PR1 → PR2 → PR3 → PR4 → PR5 → PR6 |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

Rules: STRICT TDD (RED → GREEN → REFACTOR per task). Fixtures synthetic only. [APPROVAL] = needs explicit user approval before running. Runner: `python3 -m unittest discover`.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Domain + parsers | PR1 | `python3 -m unittest discover -s tests/unit` | N/A: pure code | `src/token_usage/domain,sources` |
| 2 | State store + tailer | PR2 | `python3 -m unittest discover -s tests/adapters -p "test_state*" ` and `test_tail*` | Tail a temp growing file | adapters/state_store, jsonl_tail |
| 3 | Mapping + Herdr client | PR3 | `python3 -m unittest discover -s tests/adapters -p "test_herdr*"` | Spike: read-only against local herdr 0.8.2 | mapping, claude_locator, herdr_* |
| 4 | Reconcile + TickService | PR4 | `python3 -m unittest discover -s tests/scenarios` | Fakes, spec cases 1-12 | domain/reconcile, app/tick |
| 5 | Lifecycle + manifest | PR5 | `python3 -m unittest discover -s tests/adapters -p "test_daemon*"` | `python3 src/main.py run/status` in temp state dir | lifecycle/daemon, main, manifest |
| 6 | Docs + patch + validation | PR6 | `python3 -m unittest discover -s tests/unit -p "test_sidebar*"` | Two live Claude sessions [APPROVAL] | docs, sidebar_patch |

## Slice 1: Domain + parsers (PR1)

- [x] 1.0 [APPROVAL] Bootstrap repo: `git init`, `.gitignore` (`__pycache__`, `state/`, `*.log`), initial commit.
- [x] 1.1 RED `tests/unit/test_formatting.py`: 950/1250/125400/1200000 → spec strings; ≤80 chars.
- [x] 1.2 GREEN `domain/formatting.py`; `domain/usage.py` (UsageCall, total=in+out+cc+cr; thinking 8 case → 135).
- [x] 1.3 RED `tests/unit/test_ledger.py`: repeated id once, requestId fallback, field-wise max, replay unchanged, incremental total.
- [x] 1.4 GREEN `domain/ledger.py`.
- [x] 1.5 Synthetic fixtures `tests/fixtures/claude/{basic,duplicate_ids,synthetic_and_errors,resume_copy}.jsonl`, `codex/{snapshots,null_info}.jsonl` with sentinel strings in content.
- [x] 1.6 RED `test_parsers.py`: skip `<synthetic>`/error/id-less; Codex 100,250,250 → 250, null info ignored.
- [x] 1.7 GREEN `sources/claude.py`, `sources/codex.py`; Codex total = input + output (cached/reasoning already inside; not added again).

## Slice 2: State + tailer (PR2)

- [x] 2.1 RED `tests/adapters/test_state_store.py`: atomic write (tmp+fsync+replace), dirty-only, unknown `v` → rebuild, 30-day prune, relative keys only.
- [x] 2.2 GREEN `adapters/state_store.py`, `ports.py` (Protocols).
- [x] 2.3 RED `test_jsonl_tail.py`: growth, partial line counted once, truncate/rotate rescan, 4 MiB cap, >16 MiB fragment skip, undecodable counted.
- [x] 2.4 GREEN `adapters/jsonl_tail.py`.
- [x] 2.5 RED+GREEN `adapters/log.py`: rotating 256 KiB×2, no content/paths/messages; sentinel test (state and logs never contain fixture content).

## Slice 3: Mapping + Herdr client (PR3)

- [x] 3.1 Spike (read-only): verify socket framing for `pane.list`/`pane.report_metadata` against local herdr 0.8.2 [APPROVAL if it touches herdr state]; record result in design; if unverified, ship CLI-only.
- [x] 3.2 RED `test_mapping.py`: `herdr:claude`+`id`+UUID only; Codex/absent/malformed → None; cwd ignored.
- [x] 3.3 GREEN `domain/mapping.py`, fixture `herdr/pane_list.json`.
- [x] 3.4 RED threat: `../`, symlink escape, non-UUID → None; zero/>1 matches → None + one log line; subagents included.
- [x] 3.5 GREEN `adapters/claude_locator.py` (realpath containment).
- [x] 3.6 RED threat argv: relative/missing bin rejected; metacharacters literal; no shell; 2 s timeout (fake bin script).
- [x] 3.7 GREEN `adapters/herdr_cli.py`; socket client `herdr_socket.py` (AF_UNIX test server) and `herdr_fallback.py` per-call fallback.

## Slice 4a: Reconcile + carry-overs (PR4a)

- [x] 4.1 RED `test_reconcile.py`: publish on change, refresh ≥20 s, clear on None/session change (closed panes are forgotten, no clear), never 0, seq monotonic `max(last+1, time_ns//1e6)`.
- [x] 4.2 GREEN `domain/reconcile.py`.
- [x] 4.0a Carry-over (locator): dedupe resolved subagent paths and resolved mains (in-root project-dir alias is not ambiguous).
- [x] 4.0b Carry-over (tailer): after the max_fragment+1 window, consume only through the first newline.

## Slice 4b: TickService (PR4b)

- [x] 4.3 RED `tests/scenarios/test_tick.py` (spec cases 1-12): two sessions, resume after restart, corrupt A / valid B, Herdr unreachable skips clears, Codex ignored.
- [x] 4.4 GREEN `app/tick.py` (per-session try/except); REFACTOR.
- [x] 4.5 Carry-overs from 4a verify: W1 negative age counts as stale (reconcile); W2 subagents are read next to the resolved main (locator test); 4.1 wording fixed (closed panes are forgotten).

## Slice 5: Lifecycle (PR5)

- [x] 5.1 RED threat `test_daemon.py`: second `run` exits 0 (flock); stale pidfile replaced; changed `socket_path` → SIGTERM + respawn; Popen argv list, no shell.
- [x] 5.2 GREEN `lifecycle/daemon.py`, `src/main.py` (run/start/stop/status; SIGTERM clears tokens; 5 min orphan self-exit).
- [x] 5.3 `herdr-plugin.toml` ([[startup]], start/stop/status) + tomllib manifest test.
- [ ] 5.3a [APPROVAL] `herdr plugin link /Users/joaquinhegi/Dev/herder-plugin-token-usage` then `herdr plugin enable local.token-usage` (not run; user-owned).

## Slice 6: Docs + patch + validation (PR6)

- [x] 6.1 RED `test_sidebar_patch.py`: custom rows + `rows_by_agent.claude` → diff adds only `$tokens`; refuses when no safe minimal edit; `--print` writes nothing.
- [x] 6.2 GREEN `lifecycle/sidebar_patch.py` (`--apply` writes timestamped backup; never from startup; rule: add `$tokens` to the last row of `rows` and of the claude override when present; never create a rows section: no file/section/rows → refuse with manual steps; symlink target patched in place). [APPROVAL, user-owned, not run] to run against `~/.config/herdr`.
- [x] 6.3 `README.md` (total definition, inspected dirs, install/reload/log/disable/uninstall) and `docs/SECURITY.md`.
- [ ] 6.4 [APPROVAL] Manual validation: two simultaneous Claude sessions show independent totals; restart/resume; check absent `$tokens` row.

## Slice 6b: Hardening carry-overs

- [x] 6b.1 R1 sidebar idempotence: a row set already containing `$tokens` in any row is a no-op (per `rows` and per claude override).
- [x] 6b.2 W1-R spec delta: `$tokens` goes to `rows` and `rows_by_agent.claude` only (Claude-only MVP).
- [x] 6b.3 W3-R/S-R2 README + manual-steps text: Disable runs `stop` first; shell fallback needs `HERDR_PLUGIN_STATE_DIR`; uncomment `--default-config` lines, `herdr config check`, reload.
- [x] 6b.4 S-R1: non-table `ui.sidebar.agents` refuses cleanly (exit 1, no traceback).
- [x] 6b.5 W-R1: `TickService.should_stop` checked per session and per publish action; poller wires `is_stopping`; stop during a slow tick ends `run()` fast.
- [x] 6b.6 State store: orphan `*.tmp` sweep (>1 h) in prune, best-effort parent-dir fsync, file-key allowlist (`main`, `subagents/agent-*.jsonl`), no duplicate log handler.
- [x] 6b.7 S-R4: default config path honors `HERDR_CONFIG_PATH` (documented in `herdr --help`).
