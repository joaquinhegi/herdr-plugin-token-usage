# Design: Agent Token Usage MVP

## Technical Approach

Hexagonal Python 3.14 stdlib plugin. A pure domain (usage accounting, dedupe, mapping, reconcile, formatting) is driven by one application service, `TickService`, through ports. Adapters (Herdr socket/CLI, JSONL tailer, Claude locator, JSON state store, clock) are the only code that touches I/O. A self-detached poller runs `TickService.tick()` every 4 s (Exploration Approach 1).

## Module Layout

```
herdr-plugin.toml                 # [[startup]] + start/stop/status actions -> ["python3","src/main.py",<cmd>]
src/main.py                       # argv dispatch only; src/ is sys.path[0]
src/token_usage/
  domain/      usage.py (UsageCall, total)  ledger.py (dedupe)  mapping.py (pane -> SessionRef|None)
               reconcile.py (desired vs published -> Publish/Clear/Refresh)  formatting.py
  sources/     claude.py, codex.py      # pure: dict -> UsageCall | CodexSnapshot | None
  ports.py     # Protocols: HerdrPort, TranscriptLocator, Tailer, StateStore, Clock
  app/tick.py  # TickService
  adapters/    herdr_socket.py herdr_cli.py herdr_fallback.py jsonl_tail.py
               claude_locator.py state_store.py log.py
  lifecycle/   daemon.py (lock, pidfile, spawn, signals)  sidebar_patch.py
tests/unit/ tests/adapters/ tests/scenarios/ tests/fixtures/
```

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|---|---|---|---|
| Dedupe | Ledger per session: key `message.id` → fallback `requestId`; value `(in,out,cc,cr)` merged field-wise max; total kept incrementally (`+= new_sum - old_sum`). Lines with neither id, `<synthetic>` model, or error lines are skipped. | Sum every line; dedupe by `uuid` | Idempotent merge makes replay, resume-copied history, rotation re-reads and streaming partial usage safe. |
| Subagents | Main + `subagents/agent-*.jsonl` share one session ledger | Separate totals | User decision; ids never collide across files. |
| Duplicate guard | `fcntl.flock` on `poller.lock` held for daemon lifetime; pidfile `{pid, socket_path, started_at}` is informational | Pidfile + `kill -0` only | Lock is atomic and immune to stale pids and PID reuse. |
| Handoff | `start` with live daemon: no-op if recorded `socket_path` equals current env, else SIGTERM, wait ≤5 s, respawn | Always no-op | Startup re-runs on live handoff; the old daemon may hold a dead socket path. |
| Spawn | `subprocess.Popen([sys.executable, main.py, "run"], start_new_session=True, stdio=DEVNULL, close_fds=True)` | `os.fork` double-fork | Testable, no shell. |
| Herdr transport | Socket client first; per-call fallback to CLI argv via `HERDR_BIN_PATH`; 2 s timeouts | CLI only | Cheaper per tick; CLI covers protocol drift. |
| State files | `state/sessions/<uuid>.json` per session, written only when dirty; `state/published.json` | One big file | Rewrite cost bounded per changed session. |
| File keys | Relative keys `main` / `subagents/agent-x.jsonl` under session; no absolute paths persisted | Absolute paths | Paths contain project slugs (sensitive). Locator re-resolves. |
| Empty session | Mapped session with total 0 → cleared, not `0 tokens` | Show 0 | "Never a misleading 0". |
| `--seq` | `max(last_seq + 1, time_ns // 1e6)` persisted | Plain counter | Monotonic across restarts even if state is lost. |

## Data Flow (one tick)

```
HerdrPort.list_panes ─► mapping.resolve(pane) ─► {pane: SessionRef|None}
        │ fail: skip tick, no clears         │ distinct sessions
        ▼                                     ▼
  reconcile ◄── format(total) ◄── ledger.apply ◄── parser ◄── Tailer(new complete lines) ◄── Locator
        │                                   (try/except per session)
        ▼
  HerdrPort.report / clear ─► published.json ; StateStore.save(dirty sessions)
```

- `resolve`: only `agent_session.source == "herdr:claude"`, `kind == "id"`, value matching strict UUID regex. Codex, absent, or malformed → `None` → clear.
- Locator: `~/.claude/projects/*/<uuid>.jsonl`; zero or >1 matches → ambiguous → `None` plus one diagnostic log line.
- Reconcile per pane: publish when the value or session changed; refresh when age ≥ 20 s (TTL 60 s); clear when `None` and previously published. Panes absent from the list are forgotten.

## Tailer and Partial Lines

Per file: `{inode, dev, size, offset}`. Inode change or `size < offset` → offset 0 (safe because the ledger is idempotent). Read ≤4 MiB per file per tick; consume only up to the last `\n`; the trailing fragment stays unread. A fragment >16 MiB without newline is skipped to the next newline. Undecodable lines are counted and skipped.

## State Schema (v1)

```json
// sessions/<uuid>.json
{"v":1,"provider":"claude","last_seen":1760000000,"total":125400,
 "files":{"main":{"inode":1,"dev":1,"size":9,"offset":9}},
 "ledger":{"msg_01ab":[10,200,0,5000]}}
// published.json
{"v":1,"seq":1760000000123,"panes":{"<pane_id>":{"session":"<uuid>","value":"125.4k tokens","at":1760000000}}}
```

Atomic write: temp file in same dir → `fsync` → `os.replace`. Unknown `v` → discard and rebuild from offset 0. Sessions with `last_seen` older than 30 days are pruned at startup and hourly.

## Lifecycle

`run`: acquire lock or exit 0 → write pidfile → loop. SIGTERM/SIGINT set a stop flag; on exit: clear published tokens (best effort), persist, remove pidfile. SIGHUP ignored. Herdr unreachable for 5 min → self-exit (orphan guard). `status` prints pid, last tick, published pane count only.

## Security Boundaries

- Reads: only the two Claude globs above, after `realpath` containment under `~/.claude/projects`. Codex parser has no locator in the MVP.
- Writes: `HERDR_PLUGIN_STATE_DIR` and Herdr metadata only. Values are rendered from ints.
- Subprocess: `HERDR_BIN_PATH` (absolute, executable) and `sys.executable`; argv only.
- Logs: `RotatingFileHandler` 256 KiB×2; event names, counts, exception type, pane id, 8-char session prefix. Never line content, exception messages, or paths.
- `sidebar_patch`: `--print` renders a diff only; `--apply` (explicit) writes a timestamped backup first; it refuses to merge when `[ui.sidebar.agents]` already exists (prints manual instructions). Never called by startup.

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths | N/A: no executable-file classification | — | — |
| Git repo selection / commit / push / PR | N/A: no VCS automation | — | — |
| Subprocess argv (plugin-specific) | Applicable | Bin path validation, no shell, timeout | relative/missing bin rejected; metacharacters passed literally |
| Session id → path (plugin-specific) | Applicable | UUID regex + realpath containment | `../`, symlink escape, non-UUID → `None` |
| Self-spawn/handoff (plugin-specific) | Applicable | flock + socket_path compare | second `run` exits; changed socket path respawns |

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | formatting, ledger, parsers, mapping, reconcile, seq | Pure fixtures, no I/O |
| Adapter | tailer (growth, partial, truncate, rotate), state store (atomic, prune, bad version), locator, CLI client (fake bin script), socket client (AF_UNIX test server), lock | `tempfile` dirs |
| Scenario | Spec cases 1–12 | `TickService` with fakes |
| Security | Sentinel strings in fixtures never appear in state/logs | Scan written files |

Fixtures (synthetic): `claude/{basic,duplicate_ids,synthetic_and_errors,partial_tail,resume_copy}.jsonl`, `claude/<uuid>/subagents/agent-a.jsonl`, `codex/{snapshots,null_info}.jsonl`, `herdr/pane_list.json`.

## Migration / Rollout

No migration. Chained slices: (1) domain + parsers, (2) tailer + state, (3) mapping + Herdr client, (4) lifecycle + publishing, (5) docs + sidebar patch.

## Open Questions

- [x] Socket wire framing (slice 3 spike, read-only, herdr 0.8.2): newline-delimited JSON over the Unix socket (`HERDR_SOCKET_PATH`). Request `{"id":"req_1","method":"pane.list","params":{}}\n`; response one line `{"id":"req_1","result":{"type":"pane_list","panes":[...]}}\n` (errors: `{"id":..,"error":{"code","message"}}`). Pane keys include `pane_id`, `agent`, `cwd`, `agent_session`; Claude panes carry `agent_session` = `{source:"herdr:claude",agent:"claude",kind:"id",value:<36-char UUID>}` (verified live on 2 panes). VERIFIED for `pane.list` only; `pane.report_metadata` was not exercised (mutating, out of spike scope) and its params stay documented-only. Decision: slice 3b builds socket (reads) + CLI fallback; metadata writes are validated through the CLI path first.
- [ ] Whether the Codex `output_tokens` value includes `reasoning_output_tokens` and `input_tokens` includes `cached_input_tokens` (fixture-only; affects the Codex total). Slice 1 ASSUMES both (total = input + output; `cache_write_input_tokens` and upstream `total_tokens` ignored). Unproven — validate against real Codex data in slice 6 (compare with `total_tokens`).
- [ ] Behavior of an absent `$tokens` in a sidebar row (manual check).
