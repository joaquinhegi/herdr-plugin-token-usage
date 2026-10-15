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

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:571dd9d3a89021eb70093ce511f4eb64cbd29646de75343528c6d557ae64b07b
verdict: fail
blockers: 0
critical_findings: 0
requirements: 1/11
scenarios: 9/26
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:d421c1ccffd30ac24c1d505f3ba98013f54f15b1983c4c8836a9b27009bd5faa
build_command: python3 -B -c "import ast,pathlib; [ast.parse(p.read_text(), str(p)) for p in pathlib.Path('src').rglob('*.py')]; print('build ok')"
build_exit_code: 0
build_output_hash: sha256:5c3d57cf803c92ff537694cda191d9c10c44f33c39eaf5f45e91e34f6413e254
```

## Verification Report

**Change**: windows-support, Slice 2a (WindowsHost lock/identity/stop file, cooperative stop, stopping status)
**Candidate**: branch `win-2a-windows-host` (PR #4), HEAD `c7dad95`, tree `363ce6a6`; scope `git diff origin/main win-2a-windows-host` (`311218d..c7dad95`: 10f7520, 7c20152, c7dad95; 9 files, +472/-36, overage accepted by the user).
**Mode**: Strict TDD (runner: unittest)
**Scope note**: Totals (11 requirements, 26 scenarios, counted from the three delta specs) are change-wide. Slices 2b, 4 and 5 are pending, so the incomplete counts are expected and do not block this slice. evidence_revision = sha256 of (tree, test output hash, build output hash).
**Process note**: PR #4 was already MERGED (merge commit `0a8117d`, 2026-10-15T05:34:33Z) before this verification ran. This is a post-merge verification of the same head `c7dad95`.

### Completeness (Slice 2a)
| Metric | Value |
|--------|-------|
| Tasks total (2.1, 2.2, 2.3, 2.4, 2.4a) | 5 |
| Tasks complete | 5 |
| Tasks incomplete | 0 |
Later-slice tasks (2.5-2.10, 4.x, 5.x) are unchecked by design. Task 2.1 is checked, but one of its listed items ("liveness never `os.kill`") has no test (W3).

### Build & Tests Execution
All local runs used `git archive` copies under the session scratchpad, `python3 -B` (Homebrew 3.14.8), and an `os.kill` guard (`sitecustomize`, blocks pids < 20000 and the user's poller 59645). The repository was not written. The guard log stayed empty.

**Build**: Passed (AST parse of `src/**/*.py`, exit 0).

**Tests (macOS, local)**: 243 run, 239 passed, 0 failed, 4 skipped (exit 0). The 4 skips are the nt-only `LockTest` (3) and `CrossProcessTest` (1). Baseline `origin/main` (`311218d`): 215 passed.
Per-test outcome diff (custom result collector, base vs candidate): all 215 baseline test ids are `ok` on both trees. The candidate adds 28 ids: 24 `ok`, 4 nt-only skips. No baseline test changed outcome.

**CI (GitHub Actions run 38637551697, head `c7dad95`)**: 6/6 jobs green.
| Job | Result |
|-----|--------|
| ubuntu / macos x 3.11, 3.13 | `Ran 243 tests` OK |
| windows-latest 3.11 (job 116104463889), 3.13 (job 116104463819) | `Ran 243 tests ... OK (skipped=37)` |
Windows log confirms the nt-only tests ran: `LockTest` x3 and `CrossProcessTest.test_live_holder_blocks_and_a_killed_holder_frees_the_lock` all `... ok` on both Windows jobs. `test_daemon` on Windows: TestRun 7 ok, TestRunHardening 5 ok (1 skip: signal handlers), TestStatus 2 ok, TestStart 9 skipped, TestRealSpawn 1 skipped. Skips went from 51 to 37, and the 14 unskipped tests are exactly TestRun + TestRunHardening (excluding signals) + TestStatus, all using the real `WindowsHost` through `hold_lock`.

**Coverage**: Not available.

### msvcrt lock semantics (focus 1)
| Step | Code | Result |
|------|------|--------|
| Lock | `host_windows.py:35-36` `lseek(0)` then `locking(LK_NBLCK, 1)` | Correct. Byte 0 from position 0; on failure the fd is closed (`:38`). The `lseek` is redundant on a freshly opened fd but defensive. |
| Identity write | `:42-44` `lseek(16)` then 16-byte write; position ends at 32 | Correct. Never touches byte 0. |
| Release | `:51` blank identity (seek 16) while locked, then `:53` `lseek(0)`, then `:54` `LK_UNLCK` 1 byte, `finally` close (`:56`) | Correct order. The re-seek to 0 happens AFTER the offset-16 write, so the unlock targets byte 0. If unlock ever raised, the `finally` close still drops the lock. On real Windows a wrong-range unlock raises `OSError`, so `test_second_lock_fails_until_release_and_release_wipes_identity` would error. It passed on both Windows jobs. |
| Probe | `:58-63` acquire; if won, `release` blanks the stale pid | Correct. It wipes only when it wins (`test_probe_wipes_a_stale_identity_when_it_wins`, CrossProcessTest after `proc.kill()`). |
| holder_pid | `:65-71` separate `open(..., "rb")`, `seek(16)`, read 16 bytes, `int(strip)` | Never reads byte 0. Blank or short file gives `ValueError`, which returns None. Cross-process readability confirmed on Windows CI. |
| Inheritance | `os.open` fds are non-inheritable by default (PEP 446, `O_NOINHERIT` on Windows). `spawn` passes `close_fds=True` (`:74`). `start` probes with `held()`, which closes its handle before `spawn` (`daemon.py:189,195`). | The child cannot inherit the lock handle. |

### Stop-file protocol (focus 2)
- Created only by `request_stop` (`host_windows.py:79`), which `daemon._terminate` calls only after `held()` is True (`daemon.py:181,192,201`). The path is fixed: `Path(d) / "poller.stop"` in the state dir passed to that host, and the content is ignored. A file can only affect the poller that owns the same state dir. Anyone who can write the state dir can stop that poller, which matches the owner trust boundary.
- Cleared after lock + identity at startup (`daemon.py:104-105`) and on exit after `_cleanup` and before `release` (`:111-113`), matching the design data flow.
- POSIX ignores a planted `poller.stop`: `PosixHost.stop_requested` is False (`host_posix.py:63-64`). Probe: candidate `is_stopping()` stays False with the file present.
- Race (stop issued while a new poller starts): reproduced with a hybrid host (real flock + real `WindowsHost` stop-file methods). A `stop` that lands between lock acquisition and the startup `clear_stop` has its file erased. The poller keeps running and that `stop` returns `failed`. A follow-up `stop` works (`stopped`, no stop file left). See W1.

### POSIX unchanged (focus 3)
- `status` output is byte-identical on base and candidate (`'stopped'`, `'running pid=4242 last_tick=00:00:02Z panes=1'`), with a planted stop file on the candidate.
- `_wait` with `stop_poll_s is None` performs a single `_stop.wait(seconds)` (`daemon.py:81-84`). `_loop` uses `is_stopping()`, which equals `_stop.is_set()` on POSIX. `clear_stop` is a no-op.
- All 215 baseline ids are `ok`.

### is_stopping latch and should_stop wiring (focus 4)
- `daemon.py:75-78`: the first time the host reports a stop request, `is_stopping()` sets `_stop`. The latch survives the file being removed (`test_is_stopping_follows_the_host_and_latches`; mutant S2 killed). Setting `_stop` also wakes any in-progress `_stop.wait` slice.
- `main.py:44` already sets `svc.should_stop = poller.is_stopping`, so `TickService` (`tick.py:42,53`) sees a stop-file request between sessions and actions without code change.

### Spawn (focus 5)
`host_windows.py:74-76`: argv `[sys.executable, "-X", "utf8", "-B", *argv_tail]`, `creationflags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` (0x200 | 0x08000000), no `DETACHED_PROCESS`, no `start_new_session`, `close_fds=True`, and DEVNULL stdio. All of these are asserted by `SpawnTest` (mutants W2, W3 and W4 killed).

### Mutation testing (22 mutants, full suite, archive copy, kill guard on)
| Mutant | Result | Killing test |
|--------|--------|--------------|
| D3 `_wait_free` loop uses `is_running` (carry-over) | **KILLED** | 3 `StopWaitTest` tests |
| S1 `is_stopping` ignores the host | KILLED (suite crash/timeout) | stop-flow tests |
| S2 no latch | KILLED | `test_is_stopping_follows_the_host_and_latches` |
| S3 no startup `clear_stop` / S4 no exit `clear_stop` / S5 `clear_stop` before `record_identity` / S10 `clear_stop` after `release` | KILLED | `test_stale_stop_file_is_cleared_after_the_lock_and_again_on_exit` (+ `test_poller_run_uses_host_lock_and_identity` for S10) |
| S6 status always `running` | KILLED | `test_stopping_when_held_and_stop_requested` |
| S7 `_wait` ignores `stop_poll_s` | KILLED | `test_wait_wakes_in_slices_when_the_host_polls` |
| S8 `_loop` checks only the event | KILLED | `test_stop_request_ends_the_loop_between_ticks` |
| S9 default `self._sleep = sleep or self._stop.wait` | **SURVIVED** | see W2 |
| S11 status probes a default PosixHost | KILLED | 3 tests |
| W1 `request_stop` only with a verified pid | KILLED | `test_request_stop_creates_the_stop_file_ignoring_pid` |
| W2 DETACHED_PROCESS / W3 drop `-X utf8` / W4 `close_fds=False` | KILLED | `test_spawn_flags_and_argv` |
| W5 also register SIGTERM | **SURVIVED** | see S2 |
| W6 `stop_poll_s=None` / W7 `supports_socket=True` | KILLED | `test_capabilities` |
| W8 `clear_stop` without `missing_ok` | KILLED | `test_clear_stop_is_idempotent` |
| T1 FakeHost stop-file frees immediately | KILLED | 3 `StopWaitTest` tests |
| T2 `child_env` drops APPDATA | KILLED | `ChildEnvTest` |
The msvcrt seek/unlock mutants cannot run on macOS. Their killing tests (`LockTest`, `CrossProcessTest`) ran and passed on Windows CI, and a wrong-range unlock raises there. This is static reasoning plus CI evidence, not a local mutation run.
Process safety: `pgrep -fl main.py` before and after showed only the user's poller (59645). It was never signalled, and the guard log is empty.

### Tests quality (focus 6)
- Windows tests are meaningful. `CrossProcessTest` uses a real child Python process that holds the lock (`HOLDER` script), proves cross-process blocking and pid readability, crashes it with `proc.kill()`, and then proves the lock is freed and the stale pid is wiped. `LockTest` uses two real handles in the same process.
- FakeHost stop-file mode is faithful enough. `request_stop` sets the flag only when a holder exists, while the real host touches the file unconditionally. The two are equivalent because the daemon calls `request_stop` only after `held()` is True. `free_after` models the poller exiting after N polls. The flag is not cleared when the holder frees, which is harmless because status checks `held()` first.
- D3 carry-over is closed with `wait>0`, a fake clock, and frees after N polls.

### Spec Compliance Matrix (change-wide; slice-2a-relevant rows)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Windows single-instance lock | Second instance | `CrossProcessTest`, `LockTest.test_second_lock_fails...`, `TestRun.test_second_run_exits_zero_without_ticking` (WindowsHost, Windows CI) | COMPLIANT |
| Windows single-instance lock | Crashed holder | `CrossProcessTest` (killed holder frees lock, re-acquire works) | PARTIAL (`start` with WindowsHost untested; main selection is 2b) |
| Windows spawn | Spawn flags | `SpawnTest.test_spawn_flags_and_argv` | PARTIAL (CLI `CREATE_NO_WINDOW` is 2.7) |
| Windows liveness without signals | Liveness probe | `TestStatus` with WindowsHost on Windows CI | PARTIAL (no assertion that nothing is signalled; W3) |
| Stop and status actions | Stopping status | `StatusStoppingTest` x3 (6 jobs) + `StopFileTest` (real file) | COMPLIANT |
| Stop and status actions | Windows cooperative stop | `test_stop_request_ends_the_loop_between_ticks`, `StopWaitTest`, `TestRun` cleanup (event path) | PARTIAL (no real stop-file end-to-end with token clearing; hybrid probe confirms) |
| Single detached poller | Windows concurrent starts | lock tests + `test_second_run...` on Windows | PARTIAL (`start` concurrency needs 2b selection) |
| Previously compliant (Handoff re-run, Stale pidfile, Stop, Atomic x2, Matrix, AttributeError on POSIX) | 7 | unchanged, all pass | COMPLIANT |
| Forced termination, Pid reuse guard, manifest, Windows/No-AF_UNIX selection, sidebar paths | 10 | slices 2b/4 | UNTESTED (out of slice) |
**Compliance summary**: 9/26 scenarios compliant (7 before, plus Second instance and Stopping status). 1/11 requirements fully complete.

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| `msvcrt.locking(fd, LK_NBLCK, 1)` on byte 0 after `lseek(0)`, pid at offset 16, release = wipe, `LK_UNLCK`, close | Yes | |
| Liveness by lock probe only | Yes | No `os.kill` in `host_windows.py` |
| Stop file, poll `stop_poll_s = 0.5` | Yes | |
| Spawn flags and argv | Yes | |
| `supports_socket = False` | Yes (property only; main wiring is 2b) | |
| Startup `lock -> record_identity -> clear_stop`, exit `cleanup -> clear_stop -> release` | Yes | Design-inherent race, see W1 |
| `is_stopping` sets `_stop`; POSIX single wait | Yes | |
| Signal handlers INT and BREAK, no HUP | Yes | |
| `force_terminate` | Stub `False` | Planned for 2b; a stuck Windows poller reports `failed` until then |

### TDD Compliance (focus 7)
| Check | Result | Details |
|-------|--------|---------|
| TDD Cycle Evidence table | Missing | apply-progress #178 has no table and no RED/GREEN record for 2a. RED and GREEN are combined in the same commits (10f7520, 7c20152). |
| RED reproduced independently | Yes | `test_host_windows` against base src: ImportError. `test_stop_flow` at 7c20152 against 10f7520 src: 6/14 fail (4 FAIL, 2 ERROR). The other 8 characterize existing `_wait_free` behavior (the D3 carry-over) and pass by design. `test_support` against base `support.py`: fails. |
| GREEN | Yes | 243/243 local (4 nt skips), 6/6 CI |
| Safety net | Yes | 215 baseline ids unchanged |

### Issues Found
**CRITICAL**: None

**WARNING**:
- W1 A stop request that lands during poller startup is lost (`daemon.py:96-105`). `stop` touches `poller.stop` as soon as `held()` is True. A poller that has just taken the lock then runs `clear_stop` at `:105` and erases the request. Reproduced: the concurrent stop returned `failed`, the poller kept running, and a follow-up stop succeeded. The failure is visible, not silent: rc 1 and `handoff_failed` is logged (`main.py:89-91`). A `start` handoff in the same window returns `failed` and does not spawn. The window is microseconds (lock -> identity write -> clear), and the behavior matches the design data flow. Once 2b lands, guarded `force_terminate` will turn this into a forced stop. Fix option: note the time before `acquire_lock` and clear only a stop file whose mtime is older than that time. Do not clear before taking the lock: that would let a losing `run` delete the live poller's pending request.
- W2 Mutant S9 survives. Nothing tests the default `self._sleep = sleep or self._wait` (`daemon.py:67`). Every test either injects `sleep=` or calls `_wait` directly. Production (`main.py:43`) relies on the default. Reverting it would delay noticing a Windows stop by up to one full interval (4 s) plus the tick, which is half of `WAIT_S`. Add a Poller test with no `sleep=` and a `stop_poll_s` host that asserts `run()` exits soon after the stop flag is set.
- W3 Task 2.1 lists the RED item "liveness never `os.kill`", but no test asserts it: `test_host_windows.py` never patches `os.kill`. Static evidence: `host_windows.py` has no `os.kill`, and `status` calls only `held`/`stop_requested`. `daemon.start`/`stop` still default to `PosixHost(kill=os.kill)` when no host is passed (`daemon.py:187,200`). `main.py` passes no host until 2b, so add the assertion together with host selection in 2b.
- W4 Strict TDD evidence format: the apply-progress has no TDD Cycle Evidence table (repeat of slice-1 W4). The strict module would rate this CRITICAL. It is kept as a WARNING, consistent with the slice-1 precedent, because RED and GREEN were reproduced independently above and every new behavior has a killing test except S9 and W5.

**SUGGESTION**:
- S1 `clear_stop` is unguarded. At `daemon.py:105` it runs before the `try`. At `:112` it runs inside `finally`, before `release`. On Windows, `unlink` can raise `PermissionError` if another handle has `poller.stop` open (for example an AV scanner or a concurrent `touch`). At startup this ends `run` with "state directory is not usable" (rc 1, `main.py:67-69`). In `finally` it skips `release` (the OS frees the lock on exit) and masks any loop exception. Wrap both calls with `_safely`.
- S2 Mutant W5 (also registering SIGTERM) survives because the fake `signal` module in `SignalTest` has no `SIGTERM`. Add `SIGTERM`/`SIGHUP` to the fake spec and assert they are not registered.
- S3 Between `_cleanup` (pidfile removed) and `release`, Windows `status` can print `stopping pid=None`. The POSIX analogue `running pid=None` already exists. Cosmetic.
- S4 Stop-flow tests import `Base` from `test_daemon`, so a WindowsHost import problem breaks both modules at once. Acceptable, but a shared fixture module would isolate failures.
- S5 PR #4 merged before verification completed. In later slices, gate the merge on the verify report.

### Verdict
The envelope says `fail` because change-wide evidence is incomplete: 1/11 requirements and 9/26 scenarios, with slices 2b, 4 and 5 pending. The change is not archive-ready. This does not indicate a slice-2a defect: 0 blockers, 0 CRITICAL.

Slice 2a verdict: PASS WITH WARNINGS
The msvcrt seek, lock and unlock order is correct and proven on real Windows CI by the cross-process and in-process lock tests. The stop-file protocol, the `is_stopping` latch and the stopping status match the design. POSIX output and the 215 baseline tests are unchanged. D3 is now killed. Open items: the startup stop race (W1, visible as `failed`), the untested default-sleep wiring (W2), the missing no-`os.kill` assertion (W3), and the TDD evidence format (W4).

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:2e56b387a9b2a0c5e98f0dff71474aefee20d95bdc7b27c4dec1ab68a9aa318b
verdict: fail
blockers: 0
critical_findings: 0
requirements: 5/11
scenarios: 15/26
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:c91268a077836bf31cf7356f3ab71f462ca6a4e211a8014fd9e5ad27b81d60e2
build_command: python3 -B -c "import ast,pathlib; [ast.parse(p.read_text(), str(p)) for p in pathlib.Path('src').rglob('*.py')]; print('build ok')"
build_exit_code: 0
build_output_hash: sha256:5c3d57cf803c92ff537694cda191d9c10c44f33c39eaf5f45e91e34f6413e254
```

## Verification Report

**Change**: windows-support, Slice 2b (guarded force_terminate, host selection, exe-only herdr bin, CREATE_NO_WINDOW, manifest Windows items, 2a carry-overs)
**Candidate**: branch `win-2b-terminate-manifest` (PR #5, OPEN), HEAD `2cf9619`, tree `11556e83`; scope `git diff d09c10c win-2b-terminate-manifest` (ebd8e4c, 02ce75f, 66f4054, 2cf9619; 17 files, +560/-63 = 623 changed lines, overage accepted by the user).
**Mode**: Strict TDD (runner: unittest)
**Scope note**: Totals (11 requirements, 26 scenarios) are counted from the three delta specs and are change-wide. Slices 4 and 5 are pending, so the envelope verdict is `fail` (not archive-ready). This is not a slice-2b defect: 0 blockers, 0 CRITICAL. evidence_revision = sha256 of (tree, test output hash, build output hash).

### Completeness (Slice 2b)
| Metric | Value |
|--------|-------|
| Tasks total (2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.10a) | 7 |
| Tasks complete | 7 |
| Tasks incomplete | 0 |
Slice 4 (4.1-4.3) and slice 5 (5.1-5.5, manual) are unchecked by design.

### Build & Tests Execution
All local runs used `git archive` copies under the session scratchpad (`w2b` = candidate, `b2b` = base `d09c10c`), `python3 -B` (Homebrew 3.14.8), and an `os.kill` guard in `sitecustomize`. The repository was not written. No real herdr, socket, `~/.claude/projects` or `~/.config/herdr` was touched (HOME redirected for main.py probes).

**Build**: Passed (AST parse of `src/**/*.py`, exit 0).

**Tests (macOS, local)**: `Ran 281 tests ... OK (skipped=8)`, exit 0. The 8 skips are the nt-only `LockTest` (3), `CrossProcessTest` (1) and `RealTerminateTest` (4). Base `d09c10c`: 243 run, OK (skipped=4).
Per-test outcome diff (base vs candidate): every base test id is still `ok` except 3 ids intentionally replaced (`test_force_terminate_is_deferred_to_the_guarded_implementation`, `test_declares_only_posix_platforms`, `test_startup_and_actions_are_argv_lists`); their successors pass.

**CI (GitHub Actions run 38689444566, head `2cf9619`)**: 6/6 jobs green.
| Job | Result |
|-----|--------|
| ubuntu / macos x 3.11, 3.13 | `Ran 281 tests` OK (skipped=8) |
| windows-latest 3.11 (job 116271698611), 3.13 (job 116271698404) | `Ran 281 tests` OK (skipped=36) |
`RealTerminateTest` really ran on both Windows jobs: `test_matching_child_is_terminated_and_frees_the_lock`, `test_started_at_mismatch_leaves_the_child_alive`, `test_pid_that_is_not_the_lock_holder_is_refused`, `test_liveness_and_stop_never_use_os_kill` are all `... ok` (log lines 286-289 and 1291-1294). The 36 Windows skips break down as: HerdrCliTest 5, WindowsBinTest 1 (POSIX X_OK), FallbackTest 3, HerdrSocketTest 10, StateStoreTest 1, TestRealSpawn 1, TestRunHardening 1, TestStart 9, PosixHostTest 1, sidebar TestApply 1 + TestCli 1 (slice 4), TickTest 1, plus 1 session-mapping scenario = 36. The previous run 38689340353 (head `66f4054`) failed on both Windows jobs with `PermissionError [WinError 32]` on `token-usage.log` in `test_socket_client_is_built_only_when_the_host_supports_it`; 2cf9619 closes the test's logger before removing the dir (test-only fix).

**Coverage**: Not available (`coverage` not installed).

### Force-terminate guard (focus 1)
`host_windows.py:130-147`, called only from `daemon._terminate` (`daemon.py:191-198`).
| Step | Code | Result |
|------|------|--------|
| pid sanity | `:132-134` int, not bool, > 1, != own pid; `started_at` int/float, not bool | Runs first. It is cheap and side-effect free, so running it before `held()` is equivalent to the design order. |
| held, then holder_pid == pid | `:135` | held() runs first, so a winning probe wipes a stale identity before holder_pid is read. |
| pidfile match | `_verified_pid` (`daemon.py:184-188`): pidfile pid == holder_pid, > 1, != own pid; `_terminate` forces only if this was non-None (`:196`) | Correct. `started_at` comes from the pidfile (`:192`). |
| OpenProcess | `:138` `PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE`; NULL returns False without close (`:139-140`) | Correct. |
| Creation window | `:143` refuse if unknown, `created > started_at`, or `started_at - created > 60` | Correct, both bounds tested at the boundary (+0.001, -60, -60.001). |
| Terminate same handle, close in finally | `:141-147` | Correct; `close` runs on every path after a successful open, including an exception. |
| ctypes | `:36-40` `OpenProcess.restype = wintypes.HANDLE`, `HANDLE` argtypes for GetProcessTimes/TerminateProcess/CloseHandle | `wintypes.HANDLE is c_void_p` (verified locally, 8 bytes): no 64-bit truncation. A NULL return becomes `None`, and `or None` normalizes it (`:43`). |
| FILETIME to epoch | `:49-50` `((high << 32) | low - 116444736000000000) / 1e7` | Delta verified independently (1601-01-01 to 1970-01-01 = 1.16444736e17 x 100 ns); round-trip probe exact. The real Windows test proves the value lands within 60 s of `time.time()`. |
Pid-reuse argument: TerminateProcess can only hit the process whose pid is the current lock holder at check time. If that holder dies and the pid is recycled before OpenProcess, the new process was created after the poller exited, which was after `started_at`, so `created > started_at` refuses it. The handle then pins the object until TerminateProcess. No path terminates without the full identity.

### POSIX unchanged (focus 2)
Parity probe `parity2b.py` (real flock holders, injected popen/kill/clock) on base and candidate: byte-identical output for free, same-socket, stuck-other-socket and unverified-holder scenarios (start/stop/status results, every kill/sleep/popen call, files left), and for `main._build_poller` on POSIX (`PosixHost`, `HerdrSocket` built, `supports_socket` True). `PosixHost.clear_stop` ignores `older_than` and `force_terminate` returns False (`host_posix.py:66-70`), so `_terminate` returns False on the same path with the same sleeps. `valid_bin` keeps `isabs + isfile + X_OK` off nt (`herdr_cli.py:37-43`).

### W1 stop-race fix (focus 3)
`daemon.py:105,117` stamps `began = wall()` before `acquire_lock`; `host_windows.py:120-128` keeps a stop file with `st_mtime > began`. On POSIX the call is a no-op, so APFS/ext4 granularity is irrelevant. On Windows the race it targets lasts microseconds (lock, identity write, clear). NTFS stamps the file with the coarse system time (clock-tick resolution, about 15.6 ms by default). On Python 3.11/3.12 `time.time()` reads the same coarse clock, so a touch in that window usually gets `mtime == began` and `>` clears it. On 3.13+ `time.time()` is precise, so the touch's coarse `mtime` is usually below `began` and it is cleared as well. The fix therefore rarely saves the real race (W1). No regression: the outcome is the 2a behavior (`failed`, rc 1, `handoff_failed` logged, retry works). In that window the pidfile is absent or stale, so `_verified_pid` is None and no force step runs. Clock skew: a stale file can only be kept if the wall clock steps backward past it; the new poller then exits at once, and the result is visible (S6).

### HerdrCli and manifest (focus 4, 5)
- `valid_bin` (`herdr_cli.py:37-43`): nt requires `bin_path.lower().endswith(".exe")`; `.cmd`, `.bat`, `.ps1`, bare, `herdr.exe.cmd` rejected; `HERDR.EXE`/`herdr.Exe` accepted. `CREATE_NO_WINDOW` only when `os_name == "nt"` (`:51`); POSIX passes no `creationflags` (passing it there would raise ValueError).
- Manifest (`herdr-plugin.toml`): top-level `["linux","macos","windows"]`; every startup/action item has `platforms` (POSIX `["linux","macos"]`, Windows `["windows"]`); ids `start, stop, status, start-windows, stop-windows, status-windows` are unique across platforms, as the Herdr rules in explore.md:17 require; all commands are argv lists. Windows argv `py -3 -X utf8 -B src/main.py <cmd>`: the py launcher consumes `-3` and passes `-X utf8 -B` to python.exe. Regarding the 9009 report: Windows has App Execution Aliases for `python.exe`/`python3.exe` only, not `py.exe`. Without a launcher, Herdr gets a not-found spawn error instead of the Store stub (or 9009 if Herdr goes through cmd). A Store-only Python install has no `py.exe` (S4).

### Mutation testing (42 mutants, full suite, archive copy)
| Mutant | Result | Killing test |
|--------|--------|--------------|
| F1 no held() / F2 no holder match / F7 own pid / F8 `pid < 1` / F10 started_at unchecked | KILLED | `test_refused_before_any_handle_is_opened` |
| F3, F3b (`>=`), F4, F4b (`>=`) creation window | KILLED | `test_creation_time_guard_is_bounded_on_both_sides` |
| F5 terminate via a fresh handle | KILLED | `test_matching_identity_terminates_the_same_handle_then_closes_it` |
| F6 close only on success | KILLED | 3 GuardTest tests |
| F12 access without QUERY_LIMITED | KILLED | 3 GuardTest tests |
| D1 force without verified pid / D2 force waits `wait` / D3 no wait after force / D4 started_at dropped | KILLED | ForceTerminateFlowTest |
| D5 unconditional startup clear / D6 stamp after lock / D7, D8 unguarded clear | KILLED | PollerStopFileTest W1/S1 tests |
| D10 nt -> PosixHost / D11, D12 defaults bypass selection | KILLED | TestHostSelection |
| WC2 clear_stop ignores older_than | KILLED | `test_clear_stop_older_than_keeps_a_newer_request` |
| H1 case-sensitive / H2 accepts .cmd / H3 flags on POSIX / H4 flags dropped / H5 nt needs X_OK | KILLED | WindowsBinTest (+ HerdrCliTest for H3) |
| M1 socket regardless of host | KILLED | `test_socket_client_is_built_only_when_the_host_supports_it` |
| T1-T4 manifest (python3 on Windows, unscoped POSIX item, dropped `-X utf8`, duplicate id) | KILLED | TestManifest |
| F2b holder_pid before held / F9 bool pid allowed / F11 None creation as 0 / WC3 OSError unlinks / M2 Poller host not passed | SURVIVED | Equivalent: both conditions are still required; `True <= 1`; `started_at - 0 > 60`; unlink of a missing file is a no-op; the default host is the same selection |
| WC1 `>` to `>=` | **SURVIVED** | boundary untested; see W1 |
| D9 exit clear made conditional | **SURVIVED** | low impact; see S2 |
| M3 main keeps the old X_OK check | SURVIVED locally | killed only on Windows CI by the unskipped `test_start_rejects_bad_bin_path` (static reasoning) |
Process safety: the first guard blocked `pid < 20000`. The macOS pid counter wrapped during the run, so the guard blocked the tests' own `sleep 30` children (SIGKILL) and caused 30 s timeouts in `test_unverified_pid_is_never_signaled` from D10 on. Those mutants were rerun with a descendant-only guard (blocks pid <= 1, the user's poller 59645, and any non-descendant), and the results above are from the rerun. The user's poller (59645) was never signalled; neither guard log names it.

### Spec Compliance Matrix (change-wide)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Platform adapter selection | Windows selection | `test_default_host_follows_the_os_name`; Windows CI `test_main` subprocess runs (a PosixHost on nt would raise ModuleNotFoundError for fcntl) | COMPLIANT |
| Platform adapter selection | POSIX selection | parity probe identical; 240 base ids ok; TestHostSelection | COMPLIANT |
| Windows single-instance lock | Second instance | LockTest, CrossProcessTest (Windows CI) | COMPLIANT |
| Windows single-instance lock | Crashed holder | CrossProcessTest; RealTerminateTest frees the lock | PARTIAL (no `start` with a real WindowsHost after a crash) |
| Windows spawn | Spawn flags | `SpawnTest.test_spawn_flags_and_argv`; `test_windows_runs_with_create_no_window_and_no_shell` | COMPLIANT |
| Windows liveness without signals | Liveness probe | `RealTerminateTest.test_liveness_and_stop_never_use_os_kill` (Windows CI) | COMPLIANT |
| Launcher and manifest | Manifest | TestManifest (5 tests) | COMPLIANT |
| CLI-only Herdr transport | No AF_UNIX | `test_socket_client_is_built_only_when_the_host_supports_it` (all OS); `test_no_socket_uses_cli...` (POSIX only) | PARTIAL (W2) |
| CLI-only Herdr transport | AttributeError on POSIX | `test_attribute_error_from_missing_transport_falls_back_to_cli` | COMPLIANT |
| Atomic state replace retry | Transient sharing violation / Persistent failure | test_state_store, test_host_port, test_atomic | COMPLIANT (2) |
| CI and documentation status | Matrix | run 38689444566, 6 jobs | COMPLIANT (docs half is slice 4) |
| Single detached poller | Handoff re-run / Stale pidfile | TestStart, TestRun (POSIX) | COMPLIANT (2) |
| Single detached poller | No connectivity (C13) | baseline behavior, not re-audited | PARTIAL |
| Single detached poller | Windows concurrent starts | lock tests + `test_second_run_exits_zero_without_ticking` on Windows | PARTIAL (no concurrent `start` on Windows) |
| Stop and status actions | Stop | TestRun, TestRealSpawn (POSIX) | COMPLIANT |
| Stop and status actions | Windows cooperative stop | stop-file unit tests, StopWaitTest | PARTIAL (no real end-to-end) |
| Stop and status actions | Stopping status | StatusStoppingTest | COMPLIANT |
| Stop and status actions | Forced termination | ForceTerminateFlowTest (6), GuardTest, `RealTerminateTest.test_matching_child...` (Windows CI) | COMPLIANT |
| Stop and status actions | Pid reuse guard | GuardTest refusals, `test_no_force_without_a_verified_pid`, `RealTerminateTest.test_pid_that_is_not_the_lock_holder_is_refused` | PARTIAL ("stale request is cleared" relies on the next poller's startup clear; not asserted in this flow) |
| Approval-gated config patch | 5 scenarios | slice 4 | UNTESTED (out of slice) |
**Compliance summary**: 15/26 scenarios compliant (9 before), 6 PARTIAL, 5 pending slice 4. 5/11 requirements fully complete (Platform adapter selection, Windows spawn, Windows liveness, Launcher and manifest, Atomic retry).

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Guarded TerminateProcess via ctypes, same handle, 60 s window | Yes | Sanity checks run before held(); equivalent |
| Stop: wait 8 s, then force, then wait 2 s | Yes | 2 s wait only when force returned True (documented deviation, sensible) |
| `main.py` selects host; no HerdrSocket when `not supports_socket` | Yes | Selection centralized in `daemon.default_host` |
| HerdrCli `.exe` only on Windows, `CREATE_NO_WINDOW` | Yes | "test `launcher` prefix" from design File Changes not implemented; shebang tests stay skipped on Windows (tasks 2.10a) |
| Manifest items per platform | Yes | |
| Interface text (`clear_stop(d)`, `force_terminate(d)`) | No (text stale) | ports.py now has `older_than` and `(pid, started_at)`; see S5 |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Cycle Evidence table | Missing | apply-progress #178 reports RED/GREEN in prose (counts, triangulation), not as the table (W3) |
| RED reproduced independently | Yes | Candidate tests on base src: test_terminate_guard 23 errors; test_stop_flow 4 failures + 4 errors; test_herdr_cli 4 errors; test_main 3 errors; test_manifest 1 failure + 3 errors; test_host_windows 1 error |
| GREEN | Yes | 281/281 local (8 nt skips), 6/6 CI |
| Triangulation | Yes | 10 pre-handle refusals, 7 creation-time boundaries, open/terminate/probe failures, real child on Windows |
| Safety net | Yes | 240 base ids unchanged, 3 intentionally replaced |

### Test Layer Distribution
Unit: test_terminate_guard (8), test_herdr_cli WindowsBinTest (4), test_stop_flow additions (11), test_manifest (5), TestHostSelection (3). Integration (real processes, Windows CI only): RealTerminateTest (4). E2E: none (manual slice 5).

### Issues Found
**CRITICAL**: None

**WARNING**:
- W1 The 2a-W1 fix rarely covers the real race on Windows (`daemon.py:105,117`, `host_windows.py:120-128`). NTFS timestamps have clock-tick resolution (about 15.6 ms). The race window (lock, identity write, clear) is microseconds after `began`. On Python 3.11/3.12 a racing touch usually gets `mtime == began` and is cleared by the strict `>`. On 3.13+ (precise `time.time()`) the coarse mtime is usually below `began`, so it is cleared too. The unit tests use plus or minus 5 s (`test_host_windows.py:61-67`), and mutant WC1 (`>=`) survives. This is analysis, not reproduced on Windows. No regression: the outcome stays the visible 2a behavior (`failed`, rc 1, retry works). Fix options: compare with `>=` against `began - margin` (for example one tick, 0.05 s), or write the holder pid into the stop file and clear at startup only a file that does not name this pid.
- W2 The CLI is the only Windows transport, yet no test executes `HerdrCli._run` against a real process on Windows. HerdrCliTest (5) and FallbackTest (3) stay skipped there (shebang fake bin), and WindowsBinTest mocks `subprocess.run`. Argv quoting through `list2cmdline`, `CREATE_NO_WINDOW` with `capture_output`, and the "No AF_UNIX" listing path therefore depend on manual check 5.1. A fake `herdr.exe` (for example a copy of a tiny compiled stub, or `sys.executable` driven through a test-only launcher, as design.md planned) would close this.
- W3 Strict TDD evidence format: there is still no TDD Cycle Evidence table (repeat of slice-1/2a W4). The strict module rates this CRITICAL. It is kept as a WARNING, consistent with precedent, because RED was reproduced independently for every new test module and every non-equivalent mutant is killed except WC1 and D9.

**SUGGESTION**:
- S1 Refused-force false negative (`daemon.py:194-197`). If the poller exits between the last `_wait_free` poll and `force_terminate`'s `held()`, the guard correctly refuses, but `stop` reports `failed` for a stopped poller. Returning `not host.held(state_dir)` when force is refused would fix it.
- S2 Mutant D9 survives. Nothing asserts that the exit-time `clear_stop` is unconditional (`daemon.py:123`). Impact is low, because the next startup clears an older file.
- S3 `_terminate` reads the pidfile twice (`daemon.py:184-185` and `:192`). The guard stays safe (a mismatched pair can only refuse), but one read would keep pid and started_at consistent.
- S4 `py` prerequisite (slice 4, task 4.3): a Store-only Python has no `py.exe`; `py -3` may select a 3.10 (main.py then exits cleanly with rc 2). Document both and the missing-launcher symptom.
- S5 Update design.md "Interfaces / Contracts" (`clear_stop(d, older_than)`, `force_terminate(d, pid, started_at)`) and the tasks forecast (~190 estimated vs 623 actual).
- S6 A backward wall-clock step can make a stale stop file look newer than `began`, so a fresh poller exits immediately (visible as `stopped`). Rare; the W1 pid-in-file option also removes this.
- S7 `force_terminate` propagates exceptions from the Win32 layer (asserted by `test_handle_is_closed_even_if_the_probe_raises`). In `stop`, an OSError would surface as "state directory is not usable" and anything else as a traceback. Consider mapping it to a refusal in `_terminate`.
- S8 Kill-guard note for future verifies: use a descendant-only guard, not a pid threshold (pid wraparound).

### Verdict
The envelope says `fail` because change-wide evidence is incomplete: 5/11 requirements and 15/26 scenarios, with slices 4 and 5 pending. Not archive-ready; 0 blockers, 0 CRITICAL.

Slice 2b verdict: PASS WITH WARNINGS
The terminate guard is correct and complete: identity, held lock, pidfile, creation window, same handle, close in finally, and 64-bit-safe ctypes. It is proven on real Windows CI. Locally, 34 of 37 non-equivalent mutants are killed (WC1 and D9 survive; M3 is killed only on Windows CI); 5 more are equivalent. POSIX behavior is byte-identical to base. Host selection, the `.exe` rule, `CREATE_NO_WINDOW` and the manifest are correct and tested. Open items: W1 (the mtime-based race fix is mostly ineffective at NTFS granularity), W2 (no real Windows CLI execution test) and W3 (TDD table).

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:1f5ab17a86e8b9c2c347bf12b525bd9ff32a022d2a5dcf641089f8ffd5d5e842
verdict: fail
blockers: 0
critical_findings: 0
requirements: 7/11
scenarios: 20/26
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:5e6037f7363ff6e21a716d1d2deee63ce72f8a6d46e4df2240b387f921b8b562
build_command: python3 -B -c "import ast,pathlib; [ast.parse(p.read_text(), str(p)) for p in pathlib.Path('src').rglob('*.py')]; print('build ok')"
build_exit_code: 0
build_output_hash: sha256:5c3d57cf803c92ff537694cda191d9c10c44f33c39eaf5f45e91e34f6413e254
```

## Verification Report

**Change**: windows-support, Slice 4 (config path, stop-file identity, S1/S5/S7 carry-overs, docs). This is the last code slice, so this report also includes a change-wide pass.
**Candidate**: branch `win-4-config-docs` (PR #6, OPEN), HEAD `7901b36`, tree `1e789730`; scope `git diff origin/main win-4-config-docs` (99b246f, 1b2a65f, 7901b36; 16 files, +245/-90).
**Mode**: Strict TDD (runner: unittest)
**Scope note**: The totals (11 requirements, 26 scenarios) are counted from the three delta specs and cover the whole change. Slice 5 (manual Windows validation, tasks 5.1-5.5) is still pending, so the envelope verdict is `fail`: the change is not archive-ready. This is not a slice-4 defect (0 blockers, 0 CRITICAL). evidence_revision = sha256 of (tree, test output hash, build output hash).

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total (change) | 30 (25 code/doc + 5 manual) |
| Tasks complete | 25 (slices 1, 2a, 2b, 3, 4) |
| Tasks incomplete | 5: 5.1-5.5, `[APPROVAL]` manual validation on the user's Windows PC |
Slice 4: 4.1, 4.2 and 4.3 are checked and match the code.

### Build & Tests Execution
All local runs used `git archive` copies under the session scratchpad (`w4` = candidate, `b4` = base `origin/main` 35fd2b4) with `python3 -B` (Homebrew 3.14.8), HOME redirected, and a descendant-only `os.kill` guard (`guard4/sitecustomize.py`). The guard blocks pid <= 1, the user's poller 59645 and any non-descendant for sig != 0; its block log is empty. Poller 59645 was alive before and after every run.

**Build**: Passed (AST parse of `src/**/*.py`, exit 0).

**Tests (macOS, local)**: `Ran 292 tests ... OK (skipped=8)`, exit 0. The 8 skips are nt-only: LockTest 3, CrossProcessTest 1, RealTerminateTest 4.

**CI (run 38700599818, head 7901b36)**: 6/6 green. Ubuntu and macOS (3.11, 3.13): 292 run, OK (skipped=8). Windows 3.11 (job 116307571620) and 3.13 (job 116307571938): 292 run, OK (skipped=35). The log has 35 `skipped '` lines: HerdrCliTest 5, WindowsBinTest 1, FallbackTest 3, HerdrSocketTest 10, StateStoreTest 1, TestRealSpawn 1, TestRunHardening 1, TestStart 9, PosixHostTest 1, sidebar TestApply 1, TickTest 1, plus 1 multi-line scenario. That is one fewer than 2b's 36 because the slice-4 skip on `test_default_config_is_under_home_and_never_used_by_startup` was removed. LockTest, CrossProcessTest and RealTerminateTest ran `ok` on Windows.

**Coverage**: Not available (`coverage` is not installed).

**Base tests against candidate src**: 281 run, 21 fail. All 21 are FakeHost/WindowsHost API-shape tests that the slice intentionally replaced: the old FakeHost has no `started_at` parameter, and `older_than`, `wall` and the raising `force_terminate` test are gone. Every real-process POSIX test passes unchanged (test_daemon TestStart/TestRun/TestRealSpawn/TestStatus, test_main, TestCli).

**RED reproduced**: Running the candidate tests against base src gives 3 failures and 9 errors, all in the new tests (TestDefaultPath 4, TestApplyReplace 1, StopFileTest 2, GuardTest S7 2, S1 1, identity 2). Two tests are regression locks that already pass on base: `test_creation_window_boundaries_are_inclusive` and `test_run_without_a_home_directory_is_a_short_error`.

### Focus 1: config path precedence and no-home handling
`sidebar_patch.py:178-187` follows this order: `HERDR_CONFIG_PATH` > `XDG_CONFIG_HOME/herdr/config.toml` > `%APPDATA%\herdr\config.toml` (only when `os.name == "nt"`) > `home()/.config/herdr/config.toml`. Empty values count as unset. Home is resolved lazily (`(home or Path.home)()`), so a higher source never needs a home. This matches spec sidebar-metadata order exactly. `main()` (`:197-200`) maps RuntimeError/KeyError/OSError to `sidebar-patch: cannot locate the home directory; pass --config PATH` with rc 1 and no traceback. `--config` still overrides everything.

`src/main.py:39` resolves `Path.home()` before `make_logger`, and `_dispatch` maps the failure to `cannot start (RuntimeError)`, rc 1. Reproduced on macOS: the base ignores `XDG_CONFIG_HOME` (it points at `$HOME/.config/herdr/config.toml`), and the candidate patches `$XDG_CONFIG_HOME/herdr/config.toml`. On POSIX a "no home" state is practically unreachable, because `Path.home()` falls back to `pwd`.

### Focus 2: W1 stop-file identity protocol
- **Write** (`host_windows.py:116-118`): `poller.stop` = `{"pid": verified_pid, "started_at": started_at}`. `daemon._terminate` (`daemon.py:190-192`) passes the pidfile `started_at`. Both values are null when the identity is unverified.
- **Read**: in the loop, `stop_requested` is `exists()` (`:120-121`), so any stop file is honored, whatever it names. At startup, `clear_stop(d, own)` (`:123-133`) keeps the file only when it parses to a dict whose `(pid, started_at)` equals `own` exactly. Unreadable, malformed, non-dict or other-identity files are unlinked. On exit, the clear is unconditional (`daemon.py:122`, guarded by `_safely`, before `release`).
- **Startup clear placement** (`daemon.py:114-118`): lock, then `record_identity`, then `info` (pid, `clock.now()`), then `clear_stop(own)`, then pidfile write. `started_at` is the poller's own float, and the pidfile is written only after the clear. A stop that names this poller can therefore be written only after its startup clear. The "keep" branch is defensive and can never discard a fresh named request.
- **Stale honored at startup?** No. That would need a stop file naming the exact same pid and the exact same float `started_at`, which a recycled pid of an older run cannot produce. Verified with a hybrid host (real `WindowsHost` stop-file methods plus an in-memory lock): a stale file naming `(same pid, 999.0)` and a file naming `(null, null)` are both cleared, and the poller runs.
- **Stop lost?** Yes, in a residual window. A `stop` whose `held()` sees the new poller (or a dying predecessor) before the new poller's pidfile exists sends an unverified `{null, null}`, or a stale `{A}`, request. If that write lands before the new poller's startup unlink, the request is erased. Reproduced: the racing stop has `verified_pid=None`, so no force step runs, the result is `failed` (rc 1, `handoff_failed` logged), and the poller keeps ticking. A follow-up stop returns `stopped` and leaves no stop file. If the write lands after the unlink, the loop honors it. Window size: from the new poller's `acquire_lock` to the unlink in `clear_stop`. Measured with real file ops on macOS APFS: about 21 us (identity write plus clear, no file) and about 227 us including the stop's own write, read and unlink. NTFS with filter drivers is likely slower; this is an estimate, not measured on Windows. The `stop` must start inside that window, or stall across a full restart handoff (predecessor exit, then `start` polls at 1 s, then interpreter startup). The outcome is always visible and retryable. This is the same inherent window as 2a and 2b, but now deterministic: no clock-granularity dependence. The 2b-W1 (NTFS mtime) defect is closed.
- **Stale honored in the loop?** Yes, narrowly. A `stop` that read the predecessor's identity and stalls across the restart handoff writes `{A}` after the new poller's startup clear, and the new poller exits (reproduced, case D). The user's intent was to stop the plugin, so the impact is limited to a stop racing a socket-change restart. SECURITY.md:17 does not mention this residual.

### Focus 3: S1 and S7
- **S1** (`daemon.py:195-196`): a refused force, or an unverified pid, now returns `not host.held(state_dir)` instead of `False`. A poller that exited between the last `_wait_free` poll and the force guard is now reported `stopped`, and a restart then spawns. A still-held lock stays `failed`, and no extra wait or signal happens. POSIX: `PosixHost.force_terminate` is always False, so the only change is the same race (SIGTERM sent, exit after 8 s, so `stopped` instead of `failed`). Correct. Killed by `test_refused_force_after_the_poller_exited_meanwhile_is_stopped`.
- **S7** (`host_windows.py:140-161`): every Win32 step (`Win32()` construction, `open_process`, `creation_time`, `terminate`) is inside `try`. Any `Exception` prints `force terminate refused (<TypeName>)` to stderr, with no message text, so no path leaks, and returns False. `finally` closes only a non-null handle, and a close error is swallowed. When `Win32()` or `open_process` raises, `handle` is None, so the unbound-`win32` reference in `finally` is never reached. Correct.
- **S5**: `sidebar_patch.apply` now uses `replace_with_retry` (`:170`).

### Mutation testing (23 mutants, full suite, archive copy, descendant-only guard)
| Mutants | Result |
|---------|--------|
| P1-P8 config path (XDG before env, APPDATA on every OS, APPDATA before XDG, empty XDG as set, XDG ignored, no-home uncaught, eager home, bare `os.replace`) | 8/8 KILLED |
| W1-W9 stop file and force (pid-only match, malformed kept, unconditional clear, started_at dropped, verified-only request, force re-raises, logs message text, no close on error, no dict check) | 9/9 KILLED |
| D1-D5 daemon (S1 revert, unconditional startup clear, conditional exit clear (2b D9), request without started_at, own with wrong started_at) | 5/5 KILLED |
| M1 `projects` resolved after `make_logger` in main.py | SURVIVED (regression lock only; the visible result is identical, and only a log file is opened) |

### Focus 4: docs accuracy
| Claim | Evidence | Verdict |
|-------|----------|---------|
| Windows "Experimental", CI only, needs manual validation (README:21, 66, 165; SECURITY:24) | matches the state (slice 5 pending) | Accurate |
| `py -3` launcher; python.org or install manager provide `py.exe`; Store-only Python has none (README:68) | manifest argv `py -3 -X utf8 -B`; explore.md "Python on Windows" | Accurate |
| `py -3` picks the newest Python 3; < 3.11 exits with a clear message (README:69) | `main.py:5-7` rc 2 | Accurate (`PY_PYTHON3`/`py.ini` can change the pick; not stated) |
| `*-windows` actions (README:70-76) | `herdr-plugin.toml` ids | Accurate |
| `HERDR_BIN_PATH` absolute `herdr.exe`, other types rejected (README:78; SECURITY:18) | `herdr_cli.py:37-43` (any `.exe` is accepted, case-insensitive) | Accurate |
| `%APPDATA%\herdr\config.toml`, overridable by env/XDG (README:79, 85) | `sidebar_patch.py:178-187`; explore.md:22 (Herdr facts) | Accurate |
| CLI-only transport on Windows (README:80) | `main.py:41` `supports_socket` | Accurate |
| Stop file, then guarded force (README:81; SECURITY:16) | `host_windows.py:116-161`, `daemon.py:190-197`; 60 s window inclusive (`test_creation_window_boundaries_are_inclusive`) | Accurate |
| SECURITY:17 stale stop row | `clear_stop(own)`, exit clear | Accurate for the startup case; the in-loop stalled-stop residual is not listed (S3) |
| Test table: Unit 50, Adapters 79, Scenarios 24, Lifecycle 136, Support 3, total 292 (README:128-133) | recount from `-v` output by package: 50/79/24/136/3 = 292 | Accurate |
| CI skips: Windows 35, macOS/Linux 8 (README:135) | run 38700599818 logs | Accurate |
| `%USERPROFILE%\.claude\projects` (README:145) | `Path.home()` on nt uses USERPROFILE | Accurate |
| `CLAUDE_CONFIG_DIR` gap (README:166; SECURITY:25) | `main.py:39` | Accurate |
| "hidden detached process" (README:164) | spawn flags `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`, not `DETACHED_PROCESS` | Colloquial; could be misread as `DETACHED_PROCESS` (S4) |
| Shell fallback on Windows (README:158) | needs `HERDR_PLUGIN_STATE_DIR`; the `VAR=x cmd` prefix is POSIX syntax | Incomplete for PowerShell/cmd (S4) |
| Restart/Disable/Uninstall "run the `stop` action" (README:155-157) | on Windows the id is `stop-windows` | Implicit only via README:70 (S4) |
| SECURITY:13 "`flock` on the lock file" | Windows uses `msvcrt.locking` | Not updated for Windows (S4) |
| design.md interfaces | match `ports.py`; stale: `verified_pid ... and held()` (design:47), flow "touch poller.stop" and no refused-force branch (design:53-55), "test `launcher` prefix" (design:70) never implemented | Partly stale (S5) |
No overclaiming of Windows support was found.

### Focus 6: POSIX unchanged except the config path
The real-process POSIX tests from base pass unchanged against candidate src. POSIX daemon deltas: the extra `started_at` argument is ignored by `PosixHost.request_stop`, `clear_stop` stays a no-op, and S1 only changes a late-exit race from `failed` to `stopped`. The only user-visible POSIX change is that `sidebar-patch` now honors `XDG_CONFIG_HOME` on macOS and Linux (reproduced). The spec allows this, since XDG is an override variable, but the README documents XDG only as a Windows override (README:79). The POSIX sidebar paragraph (README:85) still lists `~/.config/herdr/config.toml` or `$HERDR_CONFIG_PATH` only. See W2.

### Spec Compliance Matrix (change-wide)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Platform adapter selection | Windows selection | `TestHostSelection.test_default_host_follows_the_os_name`; Windows CI test_main subprocess runs | COMPLIANT |
| Platform adapter selection | POSIX selection | base real-process POSIX tests pass on candidate; TestHostSelection | COMPLIANT |
| Windows single-instance lock | Second instance | LockTest, CrossProcessTest (Windows CI ok) | COMPLIANT |
| Windows single-instance lock | Crashed holder | CrossProcessTest (killed holder frees the lock) | PARTIAL (no `start` with a real WindowsHost after a crash; not in the slice-5 checklist) |
| Windows spawn | Spawn flags | `SpawnTest.test_spawn_flags_and_argv`; `test_windows_runs_with_create_no_window_and_no_shell` | COMPLIANT ("no console window appears" is visual, manual 5.1) |
| Windows liveness without signals | Liveness probe | `RealTerminateTest.test_liveness_and_stop_never_use_os_kill` (Windows CI) | COMPLIANT |
| Launcher and manifest | Manifest | TestManifest | COMPLIANT |
| CLI-only Herdr transport | No AF_UNIX | `test_socket_client_is_built_only_when_the_host_supports_it` | PARTIAL (no real `HerdrCli._run` on Windows; manual 5.1) |
| CLI-only Herdr transport | AttributeError on POSIX | `test_attribute_error_from_missing_transport_falls_back_to_cli` | COMPLIANT |
| Atomic state replace retry | Transient sharing violation | test_atomic, test_state_store, `TestApplyReplace` | COMPLIANT |
| Atomic state replace retry | Persistent failure | test_atomic | COMPLIANT |
| CI and documentation status | Matrix | run 38700599818, 6 jobs; docs: README:21/64-81/164-165 | COMPLIANT |
| Single detached poller | Handoff re-run | TestStart, TestRun (POSIX) | COMPLIANT |
| Single detached poller | Stale pidfile | TestStart (POSIX) | COMPLIANT |
| Single detached poller | No connectivity (C13) | baseline, not re-audited | PARTIAL (Herdr restart is manual 5.3) |
| Single detached poller | Windows concurrent starts | lock tests; `test_second_run_exits_zero_without_ticking` on Windows | PARTIAL (no concurrent `start` on Windows; manual 5.3 only partly) |
| Stop and status actions | Stop | TestRun, TestRealSpawn (POSIX) | COMPLIANT |
| Stop and status actions | Windows cooperative stop | StopFileTest, PollerStopFileTest, StopWaitTest | PARTIAL (no real end-to-end; manual 5.2) |
| Stop and status actions | Stopping status | StatusStoppingTest | COMPLIANT |
| Stop and status actions | Forced termination | ForceTerminateFlowTest, GuardTest, `RealTerminateTest.test_matching_child...` (Windows CI) | COMPLIANT |
| Stop and status actions | Pid reuse guard | GuardTest refusals, `test_no_force_without_a_verified_pid`, RealTerminateTest refusal; startup clear of `(null, null)` asserted (`test_a_stop_naming_another_pid_or_run_is_stale_and_cleared`) | PARTIAL ("stale request is cleared" happens at the holder's exit or the next startup, not when the timeout elapses) |
| Approval-gated config patch | Custom sidebar | TestPlan/TestApply (all OS) | COMPLIANT |
| Approval-gated config patch | Explicit override | `test_precedence_env_then_xdg_then_appdata_then_home`, `test_default_config_honors_herdr_config_path` | COMPLIANT |
| Approval-gated config patch | XDG | `test_precedence...`, `test_home_is_not_needed_when_a_higher_source_is_set` | COMPLIANT |
| Approval-gated config patch | Windows default | `test_precedence...` (os_name nt); TestCli default test runs on Windows CI | COMPLIANT |
| Approval-gated config patch | POSIX default | `test_appdata_is_ignored_off_windows...`, `test_default_config_is_under_home...` | COMPLIANT |
**Compliance summary**: 20/26 scenarios compliant, 6 PARTIAL, 0 UNTESTED, 0 FAILING. 7/11 requirements are fully complete. Incomplete: Windows single-instance lock, CLI-only transport, Single detached poller, Stop and status actions.

**Scenarios that remain covered only by manual validation (slice 5)**: No AF_UNIX real CLI path (5.1), Windows cooperative stop end-to-end (5.2), No connectivity / Herdr restart (5.3), Windows concurrent starts (only partly, through 5.3). Not on the slice-5 checklist at all: Crashed holder (`start` after a killed poller on Windows) and Pid reuse guard "stale request cleared" (see S6).

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Config path order | Yes | `sidebar_patch.py:178-187` |
| Stop file names its target; startup keeps only its own request; exit clears | Yes | design.md:55 updated |
| HostPlatform interfaces | Yes | design.md:32-35 matches `ports.py:53-55` (ports types `pid`/`started_at` as Optional) |
| `verified_pid` includes `held()` | No (text stale since slice 1) | S5 |
| Data flow diagram | Partly | still "touch poller.stop"; no refused-force branch to "stopped" |
| HerdrCli test `launcher` prefix | Not implemented | already noted in 2b; W2-2b remains |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Cycle Evidence table | Missing | apply-progress #178 reports RED/GREEN in prose (W3) |
| RED reproduced independently | Yes | 12 new tests fail on base src; 2 are declared regression locks |
| GREEN | Yes | 292/292 local (8 nt skips), 6/6 CI |
| Triangulation | Yes | precedence chain, empty values, lazy home, 4 junk payloads, 2 foreign identities, both window boundaries |
| Safety net | Yes | the 21 replaced base tests are API-shape only; all real-process base tests pass |

### Test Layer Distribution
Unit: TestDefaultPath (4), TestApplyReplace (1), StopFileTest identity (2), PollerStopFileTest (4), GuardTest S7/WC1 (3), ForceTerminateFlowTest S1 (1), test_main no-home (1). Integration: TestCli subprocess (Windows default path on Windows CI). E2E: none (manual slice 5).

### Issues Found
**CRITICAL**: None

**WARNING**:
- W1 Windows test reads the real user config. `test_sidebar_patch.py:306-310` (`test_default_config_is_under_home_and_never_used_by_startup`, unskipped in this slice) sets only HOME. `child_env` forwards the real `APPDATA` (`tests/support.py:29`), so on Windows the default resolves to the real `%APPDATA%\herdr\config.toml`. The comment "HOME is a tempdir: no real config touched" is false there. It passes on CI only because the runner has no Herdr config. On a Windows machine with Herdr configured (the slice-5 PC), `--print` reads the user's config (read-only) and the test fails (rc 0 or "already present"). Fix: pass `APPDATA=str(self.dir)` (and unset `XDG_CONFIG_HOME`) in `run_cli`.
- W2 The POSIX behavior change is undocumented. `sidebar-patch` now honors `XDG_CONFIG_HOME` on macOS and Linux (`sidebar_patch.py:183-184`, reproduced), but README:85 lists only `~/.config/herdr/config.toml`, `%APPDATA%` and `$HERDR_CONFIG_PATH`, and README:79 mentions XDG only under Windows. A macOS user with `XDG_CONFIG_HOME` set is shown or patched a different file than before. This is in-spec, but it should be stated, for example "`$XDG_CONFIG_HOME/herdr/config.toml` when set".
- W3 Strict TDD evidence format: still no TDD Cycle Evidence table (repeat of earlier slices). It is kept as a WARNING per precedent, because RED was reproduced independently and 22/23 mutants are killed.

**SUGGESTION**:
- S1 Residual lost stop (W1 protocol, `daemon.py:114-117`, `host_windows.py:123-133`). A stop written between the new poller's lock acquisition and its startup unlink is erased, and the stop returns `failed` (visible, retryable). Measured window: about 21-227 us on APFS. Optional hardening: in `_terminate`, if the wait fails, `pid` was None and the stop file is gone, re-read the identity and re-request once.
- S2 Mutant M1 survives. Nothing asserts that `Path.home()` runs before `make_logger` (`main.py:39`). Low impact.
- S3 SECURITY.md:17: add the in-loop residual. A `stop` that stalls across a restart handoff can stop the freshly started poller, because the loop honors any stop file.
- S4 README wording: "hidden detached process" (README:164; it is not `DETACHED_PROCESS`); the Windows shell fallback needs PowerShell env syntax (`$env:HERDR_PLUGIN_STATE_DIR=...`) (README:158); Restart/Disable/Uninstall should say `stop-windows` on Windows (README:155-157); SECURITY.md:13 still says only `flock`; README:69 could mention `PY_PYTHON3`/`py.ini`.
- S5 design.md: remove "`and held()` is True" (design:47), update the data-flow diagram (JSON stop file, refused force then `not held`), and drop or mark the unimplemented HerdrCli test `launcher` prefix (design:70).
- S6 Add to the slice-5 checklist: (a) kill the poller in Task Manager, then `start-windows` starts a new one (Crashed holder); (b) two quick `start-windows` invocations leave exactly one python process (Windows concurrent starts); (c) after a `stop-windows` that returns `failed`, the stop file is gone after the next start; (d) run the test suite on the PC only after the W1 fix.
- S7 Process note: during the POSIX parity probe with `env -i` (HOME unset), `Path.home()` fell back to `pwd`, and one `sidebar-patch --print` read the user's real `~/.config/herdr/config.toml` (print-only, nothing written; output "$tokens is already present"). For future probes, always set HOME, or pass `HERDR_CONFIG_PATH` or `--config`.

### Verdict
The envelope says `fail` because the change is not archive-ready: 7/11 requirements and 20/26 scenarios are proven, and slice 5 (tasks 5.1-5.5, manual Windows validation) is pending. There are 0 blockers and 0 CRITICAL.

Slice 4 verdict: PASS WITH WARNINGS
The config path matches the spec order with lazy home and a clean no-home error. The stop-file identity protocol is deterministic, honors no stale request at startup, and closes 2b-W1. Its only residual is the inherent lock-to-clear window, which is visible as `failed` and retryable. S1, S5 and S7 are correct, and 22/23 mutants are killed. Docs are accurate, with test counts recounted at 50/79/24/136/3 = 292 and CI skips 35/8. Open items: W1 (a Windows test reads the real `%APPDATA%` config), W2 (XDG on POSIX undocumented) and W3 (TDD table). Remaining for archive: run and record 5.1-5.5 on the user's Windows PC (ideally after the W1 test fix and with the S6 additions), then re-verify those six PARTIAL scenarios.
