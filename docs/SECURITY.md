# Security notes

- Local-first: no network, no telemetry, stdlib only.
- Inputs are read-only: `~/.claude/projects/*/<uuid>.jsonl` (+ `subagents/`), after UUID validation and `realpath` containment.
- Writes: the plugin state dir and Herdr pane metadata only. The sidebar patch writes the Herdr config only on explicit `--apply`, after a backup.
- Subprocesses: argv lists only (`HERDR_BIN_PATH` absolute and executable, `sys.executable`); no shell.
- Logs hold event names, counts, exception types, pane ids and 8-char session prefixes; never transcript content, exception messages or paths.

| Threat | Response |
|---|---|
| Session id as path (`../`, non-UUID, symlink escape) | strict UUID regex + realpath containment |
| Command injection via bin path / values | validated absolute path, argv only, values rendered from ints |
| Duplicate or stale poller | `flock` on the lock file; signals only to the pid recorded under the lock |
| Corrupt or oversized transcripts / state | bounded reads per tick, per-session isolation, atomic state writes |
| Content leak | sentinel tests over state and logs |

## Known residual risks

- A same-user process can plant symlinks or hardlinks inside the state dir or Claude dirs; same-user is already full trust.
- PID reuse: a microsecond window remains between reading the pid and signalling it.
- On slow Herdr, a handoff may wait up to `WAIT_S` (8 s) for the old poller to finish an in-flight call before respawning.
