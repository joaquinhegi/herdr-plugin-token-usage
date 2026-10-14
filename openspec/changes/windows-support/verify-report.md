```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:dd482073996ec437bd1c2bbf955840404ad85be7abfa1de235f016663ec029ae
verdict: fail
blockers: 0
critical_findings: 0
requirements: 1/11
scenarios: 4/26
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:2ad8af6149cf3142801b163bf255a28dbc2d22caaff971afacea224eb78f51bb
build_command: python3 -B -c "import ast,pathlib; [ast.parse(p.read_text(), str(p)) for p in pathlib.Path('src').rglob('*.py')]; print('build ok')"
build_exit_code: 0
build_output_hash: sha256:5c3d57cf803c92ff537694cda191d9c10c44f33c39eaf5f45e91e34f6413e254
```

## Verification Report

**Change**: windows-support, Slice 1 (host port, no POSIX behavior change)
**Candidate**: branch `win-1-host-port`, HEAD `6696635`, tree `bbd95ad8`; scope `git diff e82ccd8 win-1-host-port` (11 files, +365/-72, overage accepted by the user)
**Mode**: Strict TDD (runner: unittest)
**Scope note**: This is a slice verification inside a stacked chain. Totals (11 requirements, 26 scenarios, counted from the three delta spec files) cover the whole change; slices 2a, 2b, 3, 4 and 5 are intentionally pending, so incomplete change-wide counts are expected and are not blockers for this slice.

### Completeness (Slice 1)
| Metric | Value |
|--------|-------|
| Tasks total (slice 1) | 7 |
| Tasks complete | 7 |
| Tasks incomplete | 0 |

### Build & Tests Execution
All runs were made in `git archive` copies under the session scratchpad with `python3 -B` (Homebrew 3.14.8). The repository was not written.

**Build**: Passed (AST parse of every `src/**/*.py`, exit 0; no bytecode written)

**Tests**: 209 passed, 0 failed, 0 skipped (candidate). Baseline `e82ccd8`: 199 passed.
```text
python3 -B -m unittest discover  ->  Ran 209 tests in 7.189s / OK (exit 0)
baseline e82ccd8                  ->  Ran 199 tests in 6.717s / OK (exit 0)
```
`git diff --numstat e82ccd8 win-1-host-port -- tests`: 0 deleted lines in tests. `test_daemon.py`, `test_main.py`, `test_state_store.py` are untouched; `test_herdr_fallback.py` only gains one test (+10/-0). The 199 pre-existing assertions are unmodified.

**Coverage**: Not available (`coverage` module not installed).

### Runtime parity experiments (base vs candidate, identical output)
- **E1 stale pid / probe** (pidfile -> unrelated `sleep 60`, probe holds the lock with an empty lock file): `stop` = `failed`, handoff `start` = `failed`, victim alive, no spawn. Identical on both.
- **E1 residual** (lock held without truncation, victim pid in both files): `stop` signals the victim (rc -15) on both. This is the pre-existing S-R1 window from the agent-token-usage-mvp verify report; unchanged, not a regression.
- **Probe**: a stale `99999` in a free lock file -> `is_running` False, lock file wiped to `""`, `status` = `stopped`. Own-pid guard: no signal. Verified pid 4242 -> injected kill receives `(4242, SIGTERM)`. Identical.
- **E2 slow handoff** (real daemon, tempdir HOME/state, fake herdr 1.9 s per write call and failing `pane list`, nonexistent sockets, 4 published panes): `start` started (0.1 s), lock file == pidfile pid, `status` running, same-socket `start` = `running`, handoff with new socket = `restarted` rc 0 in 4.1 s (2 clears before the 3 s cleanup deadline), old daemon gone, new daemon running, `stop` = `stopped` rc 0, lock file `''`, pidfile removed. Identical on both.
- **fcntl unavailable** (`sys.modules['fcntl'] = None` in a subprocess): baseline `daemon` import fails with `ModuleNotFoundError`; candidate imports `daemon`, `state_store`, `herdr_fallback`, `ports`, runs `start(host=FakeHost())` = `started`; only `PosixHost.held` raises `ModuleNotFoundError` (expected until 2a/2b select a Windows host).
- **AF_UNIX absent** (real `HerdrSocket` with `del socket.AF_UNIX`): baseline crashes with `AttributeError`; candidate falls back to the CLI and logs `herdr_fallback error=AttributeError` (type only, no message).
- **Retry wiring probe**: `StateStore.save_published` with 2 transient `PermissionError`s saves on the 3rd call; with a persistent error it raises after 0.78 s, the previous `published.json` is intact and no `.tmp` is left; `_write_pidfile` likewise leaves no `.tmp`. A normal POSIX save takes 0.002 s (no sleep on the success path).
- Processes: `pgrep -fl main.py` before and after showed only the user's poller (pid 59645), never signalled. All spawned daemons were stopped or SIGKILLed by the harness. Disclosure: the first, unguarded run of mutant D2 (start drops the `kill` passthrough) made the existing test fixture call the real `os.kill(4242, SIGTERM)`. No process 4242 existed when checked right afterwards, and the call was blocked by an `os.kill` guard (pids < 20000) when the mutant ran again.

### Spec Compliance Matrix (slice-1-relevant scenarios; the rest are pending later slices)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Platform adapter selection | POSIX selection | 199 baseline tests unchanged + `test_host_port` (6) + E1/E2 parity | PARTIAL (main.py selection is slice 2b) |
| Platform adapter selection | Windows selection | (slice 2b) | UNTESTED (out of slice) |
| CLI-only Herdr transport | AttributeError on POSIX | `test_herdr_fallback > test_attribute_error_from_missing_transport_falls_back_to_cli` | COMPLIANT |
| CLI-only Herdr transport | No AF_UNIX | same test (fake raises AttributeError); real AF_UNIX-absent probe passed | PARTIAL (no test deletes AF_UNIX; Windows no-socket wiring is 2b) |
| Atomic state replace retry | Transient sharing violation | `test_atomic > test_transient_permission_error_is_retried` | PARTIAL (unit only; wiring into StateStore/pidfile untested, mutations A5/A6 survive) |
| Atomic state replace retry | Persistent failure | `test_atomic > test_persistent_permission_error_fails_after_five_tries` | PARTIAL ("no partial state file is left" not asserted through StateStore; probe confirms) |
| Single detached poller | Handoff re-run | `test_daemon > TestStart.test_live_same_socket_is_noop`, `test_host_port > test_start_same_socket_is_running_noop` | COMPLIANT (POSIX) |
| Single detached poller | Stale pidfile | `TestRun.test_stale_pidfile_replaced`, `TestStart.test_stale_pidfile_spawns` | COMPLIANT (POSIX) |
| Stop and status actions | Stop | `TestRun.test_stop_clears_published_persists_and_removes_pidfile`, `TestRealSpawn.test_start_status_stop_and_missing_env` | COMPLIANT (POSIX) |
| All Windows-only scenarios, manifest, CI, sidebar path | 17 scenarios | (slices 2a, 2b, 3, 4) | UNTESTED (out of slice) |

**Compliance summary**: 4/26 change-wide scenarios fully compliant; 4 more PARTIAL in slice scope; 18 belong to later slices.

### Correctness (Static Evidence)
| Item | Status | Notes |
|------|--------|-------|
| Zero POSIX behavior change | Implemented | `host_posix.py` reproduces each removed block byte-for-byte (flock LOCK_EX/NB, ftruncate+write pid, ftruncate+close, SIGTERM/SIGINT handlers, SIGHUP ignored, `[sys.executable, "-B", main, "run"]` with `start_new_session=True`). `start/stop` keep `popen=`/`kill=` by building `PosixHost(popen=, kill=)` (`daemon.py:171,184`). Parity experiments identical. |
| fcntl lazy import | Implemented | `host_posix.py:20` |
| Port interface | Implemented | `ports.py` `HostPlatform` matches design.md:22-36 exactly (11 methods + `supports_socket`, `stop_poll_s`); `PosixHost` and `FakeHost` have no missing or extra public members. POSIX `stop_requested`=False, `clear_stop` no-op, `force_terminate`=False match the design table. |
| AttributeError fallback | Implemented | `herdr_fallback.py:20-21`, logs `type(exc).__name__` only (mutation F2 killed). |
| replace_with_retry | Implemented | `atomic.py:10-20`: 5 tries, only `PermissionError`, sleeps 0.05/0.1/0.2/0.4 (1.5 s max, under the 1.6 s design bound), re-raises on the last try; used at `state_store.py:59` and `daemon.py:54`. `sidebar_patch.py:168` still uses bare `os.replace` (not in design scope). |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| HostPlatform seam in ports.py, host_posix.py | Yes | |
| PosixHost reproduces current behavior | Yes | Verified by parity experiments |
| Injection `host=` on start/stop/status/Poller | Yes | |
| `verified_pid` includes `held()` | No | See W1 |
| Atomic writes via replace_with_retry | Yes | |
| main.py host selection | Deferred | Planned for 2b per tasks.md |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Yes (prose, no table) | apply-progress #178 lists RED/GREEN per pair |
| All tasks have tests | Yes | 1.1/1.3/1.5 RED tasks map to test files |
| RED confirmed | Yes | New tests run against `e82ccd8` src: 8 errors (6 host_port TypeError on `host=`, atomic ImportError, fallback AttributeError) |
| GREEN confirmed | Yes | 10/10 new tests pass on candidate |
| Triangulation adequate | Partial | atomic: 3 cases; fallback: 1 new case; host port: 6 cases |
| Safety net for modified files | Yes | 199 baseline tests pass unchanged |

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 10 new | 3 | unittest |
| Integration | 0 new (TestRealSpawn pre-existing) | 0 | unittest |
| E2E | 0 | 0 | not installed |

### Mutation Testing (26 mutants, full suite)
Killed (22): A1 retry any OSError, A2 TRIES=6, A3 no doubling, A4 swallow final error, F1 AttributeError not caught, F2 log message instead of type, V1 drop holder_pid check, V2 allow own pid, V3 allow pid 1, H1 held keeps stale pid, H2 release keeps pid, H3 no start_new_session, H4 SIGINT instead of SIGTERM, H5 SIGHUP not ignored, H7 spawn drops `-B`, D1 start ignores host, D2 start drops popen/kill passthrough (hang, killed by timeout), D4 status ignores host, D5 run skips record_identity, D6 Poller ignores host, D7 terminate skips request_stop (hang, killed by timeout), D8 stop ignores host.
Survived (4): A5 `state_store.py:59` back to `os.replace`; A6 `daemon.py:54` back to `os.replace`; H6 `record_identity` without `ftruncate` (pre-existing gap: baseline had the same untested truncate); D3 `_wait_free` using `is_running(state_dir)` instead of `host.held` (equivalent on POSIX today).

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| `tests/lifecycle/test_host_port.py` | 41-45 | `assertIn(("request_stop", None), host.calls)` only | return value of `stop` not asserted (would kill D3) | WARNING (folded into W3) |

### Quality Metrics
**Linter**: Not available. **Type Checker**: Not available.

### Issues Found
**CRITICAL**: None

**WARNING**:
- W1 Design deviation, no regression: `daemon.py:157-161` `_verified_pid` checks pidfile pid == `holder_pid`, > 1, != own pid, but not `held()` as design.md:46 states. Baseline `e82ccd8` `_terminate` had no `held()` re-check either, and both callers call `host.held()` immediately before (`daemon.py:173`, `:185`), so the TOCTOU window is unchanged versus baseline. Adding `held()` would not close it on POSIX (the signal is sent after any check; the residual is the pre-existing S-R1 window, reproduced identically on both trees), and on POSIX a winning `held()` truncates the lock file, so it must run before `holder_pid` if added. Fix the design text, or add the `held()` re-check in slice 2b where `force_terminate` re-verifies.
- W2 Retry wiring untested: mutants A5 (`state_store.py:59`) and A6 (`daemon.py:54`) survive; the spec scenarios "Transient sharing violation" / "Persistent failure ... no partial state file is left" are asserted only on `replace_with_retry` itself. Runtime probe confirms correct behavior. Add one StateStore test patching `os.replace` to raise `PermissionError` twice (saved) and always (raises, previous file intact, no `.tmp`).
- W3 Host-port test gaps: D3 survives because `test_host_port.py:41-45` does not assert that `stop` returns `failed` when the injected host stays held; this matters once `WindowsHost` is injected (2a). H6 (`host_posix.py:30-32` truncate before write) survives; a crashed daemon's longer pid left in the lock file would corrupt the new identity without it. Pre-existing gap, now relocated.
- W4 TDD evidence format: apply-progress #178 reports RED/GREEN in prose, without the TDD Cycle Evidence table (no triangulation/safety-net columns). RED and GREEN were reproduced independently here.

**SUGGESTION**:
- S1 `atomic.py`: on POSIX a persistent `PermissionError` from `os.replace` (for example EACCES on the state dir) now raises after about 0.75 s instead of immediately. Error path only, bounded, as designed; no success-path change (0.002 s save).
- S2 `herdr_fallback.py:20` catches every `AttributeError` from the socket client, which can mask a programming bug as a permanent CLI fallback (it is logged by type). Acceptable per design; consider narrowing in 2b, since main.py will stop building `HerdrSocket` on Windows.
- S3 Count drift: tasks.md (1.7 and the work-unit table) says 200 baseline tests; the actual baseline is 199 (apply-progress already notes this). Engram spec summary #175 says 11 and 8 scenarios; the files contain 12 and 9 (26 total).
- S4 Mutants D2 and D7 hang the suite (killed only by a 150 s timeout) instead of failing fast; a test bound would give faster feedback.
- S5 `sidebar_patch.py:168` still uses bare `os.replace`; out of design scope, but a candidate for slice 4.

### Verdict
Envelope `fail` means the change-wide evidence is incomplete (1/11 requirements, 4/26 scenarios; later slices pending), so the change is not archive-ready. It does not indicate a slice-1 defect: 0 blockers, 0 CRITICAL.

Slice 1 verdict: PASS WITH WARNINGS
Slice 1 is complete: 209/209 tests pass, the 199 baseline assertions are untouched, POSIX behavior is identical to `e82ccd8` in the E1/E2/probe experiments, `daemon` imports without `fcntl`, and the only gaps are test-wiring and design-text warnings with no regression.
