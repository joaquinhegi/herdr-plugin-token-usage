# Security notes

- Local-first: no network, no telemetry, stdlib only.
- Inputs are read-only: `~/.claude/projects/*/<uuid>.jsonl` (+ `subagents/`), after UUID validation and `realpath` containment.
- Writes: the plugin state dir and Herdr pane metadata only. The sidebar patch writes the Herdr config only on explicit `--apply`, after a backup, and only edits an existing config (it never creates one).
- Subprocesses: argv lists only (`HERDR_BIN_PATH` absolute and executable, `sys.executable`); no shell.
- Logs hold event names, counts, exception types, pane ids and 8-char session prefixes; never transcript content, exception messages or paths.

| Threat | Response |
|---|---|
| Session id as path (`../`, non-UUID, symlink escape) | strict UUID regex + realpath containment |
| Command injection via bin path / values | validated absolute path, argv only, values rendered from ints |
| Duplicate or stale poller | `flock` on the lock file; signals only to the pid recorded under the lock |
| Corrupt or oversized transcripts / state | bounded reads per tick, per-session isolation, atomic state writes |
| Content leak | sentinel tests over state and logs |
| Wrong process terminated on Windows (stale or recycled pid) | `force_terminate` only runs after the cooperative stop times out. It requires the lock to be held, the lock-file pid to equal the pidfile pid, and the process creation time to be at or before the pidfile `started_at` and within 60 s of it. It acts on one `OpenProcess` handle, so the checked process is the terminated one. Any doubt or Win32 error is a refusal. `os.kill` is never used on Windows |
| Stale stop request stopping a new poller (Windows) | The stop file names the target poller's pid and `started_at`; a starting poller clears a stop file that does not name itself and the poller clears it on exit |
| Console window or shell on Windows | The poller is spawned with `CREATE_NO_WINDOW`, argv lists only; `cmd.exe` is never invoked. `HERDR_BIN_PATH` must be an absolute `.exe` path |

## Known residual risks

- A same-user process can plant symlinks or hardlinks inside the state dir or Claude dirs; same-user is already full trust.
- PID reuse (POSIX): a microsecond window remains between reading the pid and signalling it. On Windows the creation-time check and the pinned handle close this window.
- Windows support is experimental and covered by CI only, not by a manual run on a real machine.
- `CLAUDE_CONFIG_DIR` is not honored on any OS: only `~/.claude/projects` is read.
- On slow Herdr, a handoff may wait up to `WAIT_S` (8 s) for the old poller to finish an in-flight call before respawning. The handoff can fail and leave no poller running: it logs `handoff_failed` and exits 1. Recovery: run `start`.
