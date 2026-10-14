# Proposal: Windows Support

## Intent

On Windows, install/enable succeed but `start`/`status` exit 9009 (`python3` is the Store alias), and the lifecycle depends on `fcntl`, signals and `AF_UNIX`. Make the plugin run on Windows without changing POSIX behavior.

## Scope

### In Scope
- Platform port (lock, spawn, stop request/check, signal install, liveness); POSIX adapter (current behavior) and Windows adapter, selected in `main.py`.
- Windows stop: stop file polled by the loop; after 8 s, TerminateProcess only if lock holder and pidfile identity match. Never `os.kill(pid, 0)`.
- `msvcrt.locking` lock; pid kept outside the locked range.
- Spawn with `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`; CLI calls with `CREATE_NO_WINDOW`.
- Manifest: item-level `platforms`; `start-windows`/`stop-windows`/`status-windows` using `["py","-3","-X","utf8","-B","src/main.py",...]`; POSIX items keep `python3`; top-level adds `windows`.
- CLI-only Herdr transport on Windows; `FallbackHerdr` catches `AttributeError` on all OSes.
- `os.replace` retry on `PermissionError`.
- Sidebar-patch config path: `HERDR_CONFIG_PATH` > `XDG_CONFIG_HOME/herdr/config.toml` > `%APPDATA%\herdr\config.toml` (Windows) > `~/.config/herdr/config.toml`.
- Portable tests and GitHub Actions matrix (ubuntu/macos/windows x 3.11/3.13).
- Docs: Windows install, `py` prerequisite, detached-process risk, `CLAUDE_CONFIG_DIR` gap.

### Out of Scope
- Codex support; `CLAUDE_CONFIG_DIR`; named-pipe socket client; supervised (non-detached) poller.

## Capabilities

### New Capabilities
- `platform-support`: supported OSes, per-OS launcher and action ids, per-OS Herdr transport, CI matrix.

### Modified Capabilities
- `plugin-lifecycle`: stop/liveness defined per platform (signal vs stop file + guarded TerminateProcess); detached-poller rule documented as known risk.
- `sidebar-metadata`: default config path resolution.

## Approach

Approach A, delivered as chained PRs against `main` (≤400 lines each): (1) port + POSIX adapter, no behavior change; (2) Windows adapter + manifest + socket guard; (3) test portability + CI; (4) docs + config path. Depends on PR #1 (`platforms = ["linux","macos"]`).

## Affected Areas

| Area | Impact |
|------|--------|
| `src/token_usage/lifecycle/daemon.py`, new platform adapters | Modified/New |
| `src/main.py` | Modified (adapter selection) |
| `herdr_socket.py`, `herdr_fallback.py`, `herdr_cli.py`, `state_store.py`, `sidebar_patch.py` | Modified |
| `herdr-plugin.toml` | Modified |
| `tests/`, `.github/workflows/` | Modified/New |
| `README.md`, `docs/SECURITY.md` | Modified |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Herdr rule against detached processes (not enforced in 0.8.2) | Med | Documented; stop action; revisit if enforced |
| Kill-on-close job needs `CREATE_BREAKAWAY_FROM_JOB` (unverified) | Med | Manual validation |
| Pid reuse | Med | Lock + pidfile identity before TerminateProcess |
| Mandatory locking / sharing violations | Med | Pid outside range; replace retry |
| `py` missing | Low | Documented prerequisite |
| `agent_session` on Windows unverified | Med | Manual validation; no figure when absent |
| Only one Windows machine (user's) | High | CI + manual checklist |

## Rollback Plan

Revert the slice PR (squash commits). Windows users: `stop-windows`, then `herdr plugin uninstall`. POSIX unaffected after revert of slice 1 (no behavior change).

## Success Criteria

- [ ] POSIX tests and behavior unchanged; CI green on all 6 jobs.
- [ ] User's Windows PC: install from GitHub, `start-windows`, `status-windows` reports running, totals appear in sidebar, `stop-windows` leaves no process.
- [ ] No new network, writes, or content in logs.

## Assumptions to confirm
- `py -3` (not `-3.11`) is acceptable.
- New `platform-support` capability rather than folding into `plugin-lifecycle`.
- Windows stop clears tokens the same way POSIX stop does.

## Proposal question round
1. Should Windows be documented as "experimental" until manual validation passes?
2. If Herdr starts enforcing the detached-process rule, is losing the poller acceptable until redesign?
3. Must `status-windows` distinguish "stopping" from "running"?
