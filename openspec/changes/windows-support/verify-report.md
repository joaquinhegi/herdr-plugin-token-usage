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

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:b67f3ba71b59b4824bf1d7b1e3da999e1ed1556c82e08f0dd9b8573404e820e8
verdict: fail
blockers: 0
critical_findings: 0
requirements: 1/11
scenarios: 7/26
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:66a851b3cdbaeee21032d48303e9d799452fc39c126478454567a3ed1cf527e3
build_command: python3 -B -c "import ast,pathlib; [ast.parse(p.read_text(), str(p)) for p in pathlib.Path('src').rglob('*.py')]; print('build ok')"
build_exit_code: 0
build_output_hash: sha256:5c3d57cf803c92ff537694cda191d9c10c44f33c39eaf5f45e91e34f6413e254
```

## Verification Report

**Change**: windows-support, Slice 3 (test portability + CI)
**Candidate**: branch `win-3-portability-ci` (PR #3), HEAD `e57a57a`, tree `357d4d7e`; scope `git diff origin/main win-3-portability-ci` (`ae414cf..e57a57a`: e1bef42, 3ea3a4d, 9d114e6, e57a57a; 14 files, +211/-19). No `src/` change.
**Mode**: Strict TDD (runner: unittest)
**Scope note**: Totals (11 requirements, 26 scenarios, counted from the three delta specs) are change-wide. Slices 2a, 2b, 4 and 5 are pending, so the incomplete counts are expected. They do not block this slice. evidence_revision = sha256 of (tree, test output hash, build output hash).

### Completeness (Slice 3)
| Metric | Value |
|--------|-------|
| Tasks total (3.1, 3.1a, 3.2) | 3 |
| Tasks complete | 3 |
| Tasks incomplete | 0 |
Later-slice tasks (2.x, 4.x, 5.x) are unchecked by design (execution order 1 -> 3 -> 2a -> 2b -> 4).

### Build & Tests Execution
All local runs used `git archive` copies under the session scratchpad and `python3 -B` (Homebrew 3.14.8). The repository was not written.

**Build**: Passed (AST parse of `src/**/*.py`, exit 0).

**Tests (macOS, local)**: 215 passed, 0 failed, 0 skipped (exit 0). Baseline `origin/main` (`ae414cf`): 210 passed, 0 skipped.
Per-test outcome diff (custom result collector, base vs candidate): all 210 baseline test ids are `ok` on both trees. The only difference is 5 new `ok` tests (`test_state_store` x2, `test_host_port.HostInjectionTest` x2, `test_host_port.PosixHostTest` x1). No POSIX test was skipped or removed. Conditional in-test guards (`test_herdr_cli.py:55`, `test_claude_locator.py:102`, `test_sidebar_patch.py:168,176`) take the original path on POSIX.

**CI (GitHub Actions, PR #3)**
| Run | Head | Result |
|-----|------|--------|
| 38632130339 | 9d114e6 | 4 jobs green (ubuntu, macos); 2 windows jobs FAILED (failures=2, errors=2, skipped=49) |
| 38632379459 | e57a57a | 6/6 green |
Green run: ubuntu and macos (3.11, 3.13) `Ran 215 tests ... OK` (0 skips). windows-latest 3.11 and 3.13 `Ran 215 tests ... OK (skipped=51)`, so 164 tests run on Windows. Both Windows jobs have the same skip set. The 8 `needs_symlink` tests and the cross-OS `FakeHost` tests run and pass on Windows.
First-run Windows failures and how e57a57a fixed them:
- `test_non_uuid_and_traversal_are_none`: `*` is an invalid Windows filename. That one input is skipped on non-POSIX; the other 6 inputs still run.
- `test_invalid_value_seq_ttl_rejected_before_spawn`: the positive step runs a shebang bin. It is now POSIX-only; the 7 rejection asserts still run on Windows.
- `test_unwritable_state_dir`: a real product gap (`main.py` builds `PosixHost`, so `import fcntl` raises a Traceback). The test is skipped with "until slice 2b".
- `test_default_config_is_under_home...`: `Path.home()` raised `RuntimeError`. `child_env` now passes `USERPROFILE`, and the test is skipped with "until slice 4".

**Coverage**: Not available.

### Windows skip inventory (51) and unskip plan
| Tests | Count | Reason | Status |
|-------|-------|--------|--------|
| `test_herdr_socket.HerdrSocketTest` (`test_herdr_socket.py:15`) | 10 | AF_UNIX `FakeServer` | Permanent (Windows is CLI-only by design) |
| `test_tick` unreadable transcript x2 (`test_tick.py:214,237`) | 2 | chmod(0) semantics | Permanent |
| `test_sidebar_patch.test_backup_preserves_private_mode` (`:209`) | 1 | POSIX modes | Permanent |
| `test_herdr_cli.test_non_executable_rejected` (`:62`) | 1 | X_OK semantics | Permanent (replaced by the `.exe` rule in 2.7) |
| `test_state_store.test_atomic_write_uses_fsync_then_replace` (`:48`) | 1 | directory fsync | Permanent |
| `PosixHostTest` (`test_host_port.py:102`), `test_signal_handlers` (`test_daemon.py:180`) | 2 | flock / SIGHUP | Permanent; Windows equivalents due in 2.1/2.4 |
| `test_daemon` TestRun 7, TestRunHardening 5 (excl. signal), TestStart 9, TestStatus 2 (`test_daemon.py:83,152,213,306`) | 23 | `hold_lock` uses fcntl | **SHOULD run on Windows after 2a** (needs a host-agnostic lock helper) |
| `TestRealSpawn` (`test_daemon.py:322`) | 1 | real flock daemon + shebang bin | **Windows real-spawn equivalent after 2a/2b** |
| `test_herdr_cli` list_panes, metacharacters, clear_argv, timeout (`:70,78,89,98`) | 4 | shebang fake bin | **SHOULD run on Windows after 2b** (`launcher=[sys.executable]` per design.md Testing Strategy) |
| `FallbackTest` x3 (`test_herdr_fallback.py:18`), including `test_attribute_error_from_missing_transport_falls_back_to_cli` | 3 | shebang fake bin | **SHOULD run on Windows after 2b**; this is the "No AF_UNIX" scenario's natural Windows test |
| `test_main.test_unwritable_state_dir` (`:41`), `test_start_rejects_bad_bin_path` (`:48`) | 2 | fcntl Traceback / X_OK | **Unskip after 2b** (host selection, `.exe` rule) |
| `test_sidebar_patch.test_default_config_is_under_home...` (`:261`) | 1 | Windows default path | **Unskip after 4.1** |
Every skip has a reason string. The class/test-level `posix_only` sites in `test_daemon.py`, `test_state_store.py`, `test_main.py:48` and `test_herdr_fallback.py:18` add a specific inline comment. All skips are justified for the current product state. 34 should become runnable on Windows after 2a/2b/4.

### Carry-over mutation testing (archive copy, `os.kill` guard: pid < 20000 and the user's poller pid 59645 blocked)
| Mutant | Result | Killing test |
|--------|--------|--------------|
| A5 `state_store.py:59` back to `os.replace` | KILLED | `test_save_survives_transient_replace_failure` |
| A6 `daemon.py:54` back to `os.replace` | KILLED | `test_pidfile_write_survives_transient_replace_failure` |
| A7 `_write_pidfile` keeps `.tmp` on failure | KILLED | `test_pidfile_persistent_failure_leaves_no_tmp` |
| H6 `record_identity` without `ftruncate` | KILLED | `PosixHostTest.test_record_identity_truncates_a_longer_stale_pid` |
| D3b `stop` always returns `stopped` | KILLED | `test_stop_passes_no_pid_when_identity_unverified` |
| T1 FakeHost `request_stop` reverted (always frees) | KILLED | same |
| D3 `_wait_free` loop uses `is_running(state_dir)` instead of `host.held` | **SURVIVED** | see W1 |
| D2 start drops popen/kill passthrough (S4) | KILLED in 37.5 s (was a 150 s hang) | 3 TestStart tests |
| D7 terminate skips request_stop (S4) | KILLED in 52.9 s (was a hang) | TestRealSpawn, TestStart, 2 HostInjection |
| D7 with `time_limit` disabled (control) | hangs > 150 s | confirms S4 bound is what makes it fail fast |
Process safety: `pgrep -fl main.py` before and after showed only the user's poller (59645), which was never signalled. The guard blocked 2 `os.kill(4242, SIGTERM)` calls made by mutant D2 against the fixture pid.

### Spec Compliance Matrix (change-wide; slice-3-relevant rows)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Atomic state replace retry | Transient sharing violation | `test_state_store > test_save_survives_transient_replace_failure`, `test_host_port > test_pidfile_write_survives_transient_replace_failure`, `test_atomic` | COMPLIANT (also passes on Windows CI) |
| Atomic state replace retry | Persistent failure | `test_state_store > test_persistent_replace_failure_keeps_previous_file_and_no_tmp`, `test_host_port > test_pidfile_persistent_failure_leaves_no_tmp` | COMPLIANT |
| CI and documentation status | Matrix | run 38632379459: 6 jobs (3 OS x 3.11/3.13) ran the unittest suite on `pull_request` | COMPLIANT (docs half of the requirement is slice 4) |
| CLI-only Herdr transport | AttributeError on POSIX | `test_herdr_fallback > test_attribute_error...` | COMPLIANT |
| Single detached poller | Handoff re-run, Stale pidfile | TestStart / TestRun (POSIX) | COMPLIANT |
| Stop and status actions | Stop | TestRun, TestRealSpawn (POSIX) | COMPLIANT |
| CLI-only Herdr transport | No AF_UNIX | fake AttributeError test, POSIX only | PARTIAL (Windows run after 2b) |
| Windows-only scenarios, manifest, sidebar paths | 17 | slices 2a/2b/4 | UNTESTED (out of slice) |
**Compliance summary**: 7/26 scenarios compliant. 1/11 requirements fully complete (Atomic state replace retry).

### Correctness (Static Evidence)
| Item | Status | Notes |
|------|--------|-------|
| `tests/support.py` guards | Correct | `CAN_CHMOD0` short-circuits before `os.geteuid` (absent on Windows) (`support.py:10`). `_can_symlink` probes once at import, inside a temp dir. On the Windows runner it returned True and the symlink tests passed. |
| `child_env` | Correct | Passes PATH + SYSTEMROOT; `USERPROFILE` defaults to HOME (`support.py:26-34`). On POSIX the extra `USERPROFILE` is inert. |
| `time_limit` | Correct | SIGALRM per test, restored in cleanup, no-op without SIGALRM (`support.py:37-52`). It covers `test_daemon.Base` (30 s) and `TestRealSpawn` (60 s). LIFO cleanup order clears the alarm before temp-dir removal. |
| `/tmp` usage | Accepted deviation | `herdr_fakes.py:39` keeps `mkdtemp(dir="/tmp")` because of the AF_UNIX path-length limit on macOS. It is only reachable from POSIX-only classes. |
| FakeHost change | Correct for POSIX | `fake_host.py:39-42`: unverified `request_stop` no longer frees the lock, matching POSIX `PosixHost` (no kill without a verified pid). |

### CI security (`.github/workflows/ci.yml`)
| Check | Result |
|-------|--------|
| SHA pins | `actions/checkout@3d3c42e5...` = tag v7.0.1 (and v7), commit 2026-07-17; `actions/setup-python@5fda3b95...` = tag v7.0.0 (and v7), commit 2026-07-20. Verified with `gh api .../commits/<sha>` and `.../tags`; the run log downloads the same SHAs. |
| Permissions | top-level `contents: read` (`ci.yml:8-9`), no job override |
| Secrets | none referenced |
| Credentials | `persist-credentials: false` (`ci.yml:24`) |
| Trigger | `pull_request` plus `push` on `main` only (`ci.yml:3-6`); no `pull_request_target` |
| Timeout | `timeout-minutes: 15` per job (`ci.yml:15`); `fail-fast: false` |
| Command | `python -B -m unittest discover -v` (matches task 3.2) |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| FakeServer / `/tmp` / TestRealSpawn skip off POSIX | Yes | |
| `mkdtemp()` without `dir` | Yes, with one exception | FakeServer keeps `/tmp` (justified above) |
| SYSTEMROOT in child envs | Yes | via `child_env` |
| CI `on: [push, pull_request]` | Tighter | push limited to `main`; no loss of PR coverage |
| Matrix, pins, `contents: read`, `persist-credentials: false` | Yes | |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| RED for carry-over tests | Yes (mutation) | Each new test fails against its mutant (A5, A6, A7, H6, D3b, T1) |
| GREEN | Yes | 215/215 local, 6/6 CI |
| Safety net | Yes | 210 baseline ids unchanged, all `ok` on POSIX |

### Issues Found
**CRITICAL**: None

**WARNING**:
- W1 Carry-over W3 is only partly closed. Mutant D3 (`daemon.py:151` loop checks `is_running(state_dir)` instead of `host.held`) still survives. The only FakeHost stop test uses `wait=0` (`test_host_port.py:46`), so the `_wait_free` loop body (`daemon.py:150-153`) never executes and only the final `host.held` check is exercised. This matters in 2a: with an injected `WindowsHost`, a default-host call in the loop would import fcntl. apply-progress #178 reports D3 as FAIL. That holds only if the final `return not host.held(...)` (`daemon.py:154`) is also mutated. The slice-1 definition, which mutates only the loop, still survives. Add one FakeHost stop/start test with `wait>0`, a fake clock and a holder that frees after N polls.
- W2 Windows product gap visible only through a skip: `sidebar_patch.py:183` and `main.py:41` call `Path.home()`. On Windows without USERPROFILE/HOME this raises an uncaught `RuntimeError` (Traceback seen in run 38632130339). The test-side fix (`child_env` USERPROFILE) hides it. Task 4.1 covers path order but not this failure mode; add it to slice 4 (clean error, no Traceback).

**SUGGESTION**:
- S1 tasks.md 3.1 says "~48 of 215 tests skip on Windows". The actual number is 51 (49 + 2 added in e57a57a). Update the count.
- S2 `FakeHost.request_stop` (`fake_host.py:39-42`) now models POSIX semantics only. On Windows, `request_stop` creates `poller.stop` regardless of pid (design.md table). 2a will need a Windows-mode fake or a stop-file flag, so the cooperative-stop scenarios are tested against Windows semantics rather than POSIX ones.
- S3 `child_env` forwards only PATH/SYSTEMROOT/USERPROFILE. Slice 4 (`%APPDATA%` default) and Windows real-spawn tests (2a) will likely also need `APPDATA`, `LOCALAPPDATA` and `TEMP`/`TMP`.
- S4 `posix_only` uses one generic reason string, and `test_herdr_cli.py:62,70,78,89,98` and `test_herdr_socket.py:15` have no site comment. Per-site reasons (or a reason parameter) would make the CI skip log self-explanatory and make the 2b unskip list greppable.
- S5 CI: consider `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`. The `@posix_only` on `test_signal_handlers` (`test_daemon.py:180`) is redundant inside a `posix_only` class (harmless).

### Verdict
Envelope `fail` means the change-wide evidence is incomplete (1/11 requirements, 7/26 scenarios; slices 2a/2b/4/5 pending), so the change is not archive-ready. It does not indicate a slice-3 defect: 0 blockers, 0 CRITICAL.

Slice 3 verdict: PASS WITH WARNINGS
POSIX coverage is unchanged: 210/210 baseline tests still pass, plus 5 new, with 0 skips on macOS/ubuntu. The matrix is green on 6/6 jobs, 51 Windows skips are all reasoned, and the CI workflow is pinned and read-only. The slice-1 carry-overs W2 (mutants A5/A6/A7), H6 and S4 are closed; only D3 remains (W1 above).
