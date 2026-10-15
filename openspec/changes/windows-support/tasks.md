# Tasks: Windows Support

## Review Workload Forecast

| Slice | Content | Est. lines | Risk |
|-------|---------|-----------|------|
| 1 | Port, PosixHost, daemon refactor, atomic.py, AttributeError | ~330 | Low |
| 2a | WindowsHost lock/identity/stop, stopping status | ~210 | Low |
| 2b | force_terminate, CLI flags/.exe, main selection, manifest | ~190 | Low |
| 3 | Test portability, CI matrix | ~300 | Low |
| 4 | Sidebar path, docs | ~150 | Low |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

Delivery: auto-chain; one branch + PR per slice against protected `main`, squash merge. Execution order (user-approved): 1 → 3 → 2a → 2b → 4, so the Windows CI job exercises 2a/2b before review. Total ~1,180. Slice 2 split (design ~380). PR #1 (platforms linux/macos) must merge before 2b manifest. STRICT TDD: RED then GREEN. Runner: `python3 -m unittest discover`.

### Suggested Work Units

| Unit | Goal | PR | Focused test | Runtime harness | Rollback |
|------|------|----|--------------|-----------------|----------|
| 1 | Host port, no behavior change | PR1 | `-s tests/lifecycle` | existing 199 tests green | revert PR1 |
| 2a | Windows lock/stop | PR2a | `-p "test_host_windows*"` | real child on Windows (CI) | host_windows.py, daemon stopping |
| 2b | Terminate guard, manifest | PR2b | `-p "test_manifest*"` | manifest tomllib | manifest, herdr_cli |
| 3 | Portable tests + CI | PR3 | full suite | Actions matrix | tests, ci.yml |
| 4 | Config path + docs | PR4 | `-p "test_sidebar*"` | N/A: docs | sidebar_patch, docs |

## Slice 1: Port + PosixHost (PR1)

- [x] 1.1 RED `tests/lifecycle/fake_host.py` + test: daemon start/stop/status use injected `host=` (spec: adapter selection).
- [x] 1.2 GREEN `ports.py` `HostPlatform`; `lifecycle/host_posix.py` (fcntl imported inside class); `daemon.py` uses host.
- [x] 1.3 RED test: `FallbackHerdr` falls back on `AttributeError`.
- [x] 1.4 GREEN `herdr_fallback.py` catch.
- [x] 1.5 RED `tests/adapters/test_atomic.py`: transient PermissionError retried; persistent fails after 5 tries.
- [x] 1.6 GREEN `adapters/atomic.py`; use in `state_store.py`, `_write_pidfile`.
- [x] 1.7 Verify: all 199 existing tests unchanged and green.

## Slice 2a: WindowsHost (PR2a)

- [x] 2.1 RED (nt only) `test_host_windows.py`: second lock fails; crashed holder frees; pid at offset 16 readable; liveness never `os.kill`.
- [x] 2.2 GREEN `host_windows.py` lock, identity, `held`, `holder_pid`, `release`, spawn flags.
- [x] 2.3 RED FakeHost: stop creates `poller.stop`; stale file removed at startup/exit; `status` prints `stopping pid=…`.
- [x] 2.4 GREEN `daemon.py` stop flow, `Poller.is_stopping`, `_wait` slices, `stopping` status; signal handlers INT/BREAK.
- [x] 2.4a Carry-overs: FakeHost stop-file mode + wait>0 fake-clock tests (kills D3); `child_env` forwards APPDATA/LOCALAPPDATA/TEMP/TMP; `TestRun`, `TestRunHardening`, `TestStatus` unskipped on Windows via host-agnostic `hold_lock`. Still POSIX-only in test_daemon: `TestStart` (PosixHost popen/kill/SIGTERM) and `TestRealSpawn` (2b).

## Slice 2b: Terminate + manifest (PR2b)

- [x] 2.5 RED terminate guard: mismatched pid, unheld lock, creation time after `started_at` or >60 s → no terminate.
- [x] 2.6 GREEN `WindowsHost.force_terminate` (ctypes, same handle); daemon force step after 8 s, wait 2 s.
- [x] 2.7 RED `HerdrCli`: `CREATE_NO_WINDOW` asserted; `.cmd`/`.bat` rejected, `.exe` required on Windows.
- [x] 2.8 GREEN `herdr_cli.py`; `main.py` selects host, no `HerdrSocket` if `not supports_socket`.
- [x] 2.9 RED `test_manifest.py`: item `platforms`, top-level adds `windows`, `*-windows` argv `py -3 -X utf8 -B`.
- [x] 2.10 GREEN `herdr-plugin.toml` (after PR #1 merged).
- [x] 2.10a Carry-overs: W1 conditional stop-file clear (`clear_stop(d, older_than)`), W2 default `_wait` test, W3 `daemon.default_host` (no `os.kill` on Windows), S1 `_safely` around `clear_stop`, S2 SIGTERM/SIGHUP not registered on Windows; `test_main` unwritable/bad-bin unskipped on Windows. Still skipped on Windows: `test_herdr_cli` shebang tests and `FallbackTest` (HerdrCli has no launcher; argv semantics not changed for tests).

## Slice 3: Portability + CI (PR3)

- [x] 3.1 Skip `FakeServer`/`/tmp`/`TestRealSpawn` off POSIX; `mkdtemp()` without `dir`; `SYSTEMROOT` in envs. Shared guards in `tests/support.py`; ~48 of 215 tests skip on Windows (per simulation); per-test SIGALRM limit in daemon tests.
- [x] 3.1a Carry-overs from slice 1 verify: W2 (retry wiring for `StateStore._write` and `_write_pidfile`), W3 (`stop` returns `failed` on unverified holder; `record_identity` truncates, H6), S3 (baseline 199), S4 (bounded tests).
- [x] 3.2 `.github/workflows/ci.yml`: ubuntu/macos/windows x 3.11/3.13, SHA-pinned, `contents: read`, `persist-credentials: false`, `python -B -m unittest discover -v`.

## Slice 4: Config path + docs (PR4)

- [ ] 4.1 RED `test_sidebar*`: `HERDR_CONFIG_PATH` > XDG > `%APPDATA%` (nt) > `~/.config`.
- [ ] 4.2 GREEN `sidebar_patch.py`.
- [ ] 4.3 `README.md`, `docs/SECURITY.md`: Windows experimental, `py` prerequisite, detached-process risk, `CLAUDE_CONFIG_DIR` gap, `.exe` bin.

## Slice 5: Manual validation

- [ ] 5.1 [APPROVAL] On user's Windows PC: install from GitHub; `start-windows`; `status-windows` running; totals in sidebar.
- [ ] 5.2 [APPROVAL] `stop-windows` shows stopping then stopped; no python process remains.
- [ ] 5.3 [APPROVAL] Herdr restart runs startup action.
- [ ] 5.4 [APPROVAL] Does poller survive Herdr closing? Record whether `CREATE_BREAKAWAY_FROM_JOB` is needed.
- [ ] 5.5 [APPROVAL] Record `agent_session` values on Windows; no figure when absent.
