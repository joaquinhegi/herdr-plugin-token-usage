```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:abc1b9dfa2fb497e70ab39026d094346e4386dbbb954d6716e37bae0f572932f
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 3/3
scenarios: 4/4
test_command: python3 -m unittest discover
test_exit_code: 0
test_output_hash: sha256:1b7269679e4340b87856656f97c3cfeefe91beced688274e2fbd810e6aa62318
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 3a (tasks 3.1-3.5)

**Change**: agent-token-usage-mvp
**Section**: Slice 3a: spike (3.1), strict pane mapping (3.2/3.3), contained Claude transcript locator (3.4/3.5)
**Candidate**: branch `slice-3a-mapping`, HEAD `3050589` (tree `be8d5dd`), on `slice-2-state` `7f3e7e9`. Commits `6e1915f` (feat: mapping, locator, spike notes) and `3050589` (fix: subagent glob narrowed from `*.jsonl` to `agent-*.jsonl`). Diff `git diff slice-2-state...slice-3a-mapping`: 7 files, +226/-6 (within the 400-line budget).
**Mode**: Strict TDD
**Scope note**: Slice 3 was split by the user. Tasks 3.6-3.7 (Herdr CLI, socket and fallback clients) belong to slice 3b and are DEFERRED, not failures. The envelope counts only the session-mapping requirements whose mapping/locator layer is delivered here: 3 requirements and 4 scenarios. "Session change and resume" (2 scenarios) and the tick-level clauses (clearing `tokens`, showing a figure) belong to slice 4. The full change has 17 requirements and 26 scenarios across 4 specs.
**Evidence revision**: sha256 over the exact bytes `tree:be8d5ddc34ecefcc930349021fecf015bec785db\ntest:sha256:<test output hash>\nbuild:sha256:<build output hash>\n`. The test output contains a wall-clock duration, so its hash is specific to this run.

### Completeness
| Metric | Value |
|--------|-------|
| Slice 3a tasks total | 5 (3.1-3.5) |
| Tasks complete | 5 |
| Tasks incomplete | 0 |
| Deferred to slice 3b | 3.6, 3.7 (unchecked, out of scope) |

### Build & Tests Execution
**Build**: Passed. `python3 -m compileall -q src tests`, exit 0, empty output.
**Tests**: 67 passed, 0 failed, 0 skipped. `python3 -m unittest discover`, exit 0 (Python 3.14.8). 54 prior tests plus 5 mapping and 8 locator tests.
**Coverage**: Not available (no `coverage` module installed).

### Spec Compliance Matrix (slice 3a scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Strict Claude resolution | Same repo, two sessions | `test_mapping > test_two_claude_panes_same_cwd_map_to_own_ids`, `test_claude_locator > test_two_sessions_same_project_map_to_own_files` | COMPLIANT |
| Strict Claude resolution | Subagents included | `test_claude_locator > test_subagents_are_included_and_other_sessions_are_not`, `test_escaping_subagent_symlink_is_dropped_only` | COMPLIANT |
| No reliable session, no figure | Missing file | `test_claude_locator > test_missing_logs_one_safe_line`, `test_ambiguous_across_projects_is_none_with_one_line`; `test_mapping > test_codex_absent_and_malformed_value_are_none`, `test_non_dict_agent_session_is_none` | COMPLIANT at locator/mapping layer (None plus one safe diagnostic). "tokens cleared, never 0" deferred to slice 4. |
| Codex panes unmapped | Codex pane | `test_mapping > test_codex_absent_and_malformed_value_are_none`, `test_each_strict_field_is_required` | COMPLIANT at mapping layer (Codex pane resolves to None; no `~/.codex` access exists). "Only the Claude pane shows a figure" deferred to slice 4. |
| Session change and resume | New session / Resume | (slice 4) | DEFERRED |

**Compliance summary**: 4/4 in-scope scenarios compliant.

### Correctness (Static Evidence)
| Check | Status | Notes |
|-------|--------|-------|
| Mapping requires `source == "herdr:claude"`, `kind == "id"`, canonical UUID | Implemented | `mapping.py:10-17`. Also requires `agent == "claude"` (stricter than spec, matches the spike record). `UUID.fullmatch` is used; the regex is lowercase-only. |
| Codex, absent, malformed, non-dict `agent_session` -> None | Implemented | `isinstance(ref, dict)` guard; non-str values rejected. |
| cwd never consulted | Implemented | No `cwd` read in `mapping.py` or `claude_locator.py`. |
| Locator UUID gate | Implemented | `claude_locator.py:27` uses `UUID.fullmatch` before any filesystem access. |
| Realpath containment | Implemented | Root resolved once; main file and every subagent file checked with `realpath(...).is_relative_to(root_real)`. Probes: project-dir symlink, main symlink and subagent symlink escapes rejected; a symlinked projects root is resolved and works. |
| Subagents limited to `<uuid>/subagents/agent-*.jsonl` | Implemented | Fixed in `3050589`; `notes.jsonl` and other-session subagents excluded. |
| Zero or >1 matches -> None + one safe log line | Implemented | `log_event(..., "locate_failed", reason=missing|ambiguous, matches=N)`; no id or path. Test asserts the id and root are absent from the line. |
| Inaccessible entries | Implemented | Probe: an unreadable (mode 000) project directory beside a valid one does not raise (Python 3.14 `Path.is_file` swallows `OSError`); a missing root is caught by `except OSError`. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Locator: `~/.claude/projects/*/<uuid>.jsonl`, ambiguous -> None + one log line | Yes | Root is injected (`projects_root`), which keeps tests hermetic. |
| Main + `subagents/agent-*.jsonl` share one session | Yes | After `3050589`. |
| Session id -> path threat: UUID regex + realpath containment | Yes | See WARNING 2 for the check-to-use gap. |
| Open Question: socket framing | Resolved | design.md records newline-delimited JSON for `pane.list` (verified) and marks `pane.report_metadata` as documented-only (not exercised). |
| Spike privacy | Yes | design.md and Engram #159/#162 record pane key names and the `agent_session` shape only. No cwd, title, path or real session id values. The herdr fixture uses `/synthetic/repo` and synthetic UUIDs. |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Yes | apply-progress #159 table has rows 3.1, 3.2/3.3, 3.4/3.5 |
| All tasks have tests | Yes | 3.2/3.3 `tests/unit/test_mapping.py`; 3.4/3.5 `tests/adapters/test_claude_locator.py`; 3.1 is a documented spike |
| RED confirmed (tests exist) | Yes, with caveat | Mapping RED: 12 subtest errors against a NotImplementedError stub. Locator RED: 3 errors + 2 failures against a None stub; the None-asserting threat tests passed trivially at RED. |
| GREEN confirmed (tests pass) | Yes | 5/5 mapping, 8/8 locator in this run |
| Triangulation adequate | Partial | See the mutation replay below and WARNING 1 |
| Safety net for modified files | Yes | All source/test files are new; 54 prior tests ran before the change |

**RED caveat judgment (mutation replay)**: The tests were replayed against mutated copies extracted with `git archive` into a scratch directory (the repository was not touched).
| Mutant | Result |
|--------|--------|
| `locate` always returns None (apply stub) | 3 errors + 2 failures (positive and log tests catch it) |
| Containment check removed (`_contained` returns True) | 3 failures: main, project-dir and subagent symlink tests. The threat tests are discriminating. |
| Subagent glob widened to `*.jsonl` | 1 failure (`notes.jsonl` excluded). Confirms the `3050589` RED. |
| Mapping `fullmatch` -> `search` | 1 failure (suffix subtest) |
| Mapping `agent` check dropped | 1 failure |
| Locator UUID gate removed | Only the `A.upper()` subtest fails, and only because macOS APFS is case-insensitive. On a case-sensitive filesystem this mutant survives the whole file. |
| Locator `fullmatch` -> `match` | Survives (8/8 pass) |

Verdict on the caveat: the trivially-passing RED is acceptable for the containment tests, which kill the containment-removal mutant. It is not acceptable for the UUID/traversal subtests (WARNING 1).

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 5 | 1 (`tests/unit/test_mapping.py`) | unittest |
| Adapter (tempdir, real filesystem and symlinks) | 8 | 1 (`tests/adapters/test_claude_locator.py`) | unittest |
| E2E | 0 | 0 | not installed |
| **Total (slice 3a)** | **13** | **2** | |

### Changed File Coverage
Coverage analysis skipped. No coverage tool detected.

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| `tests/adapters/test_claude_locator.py` | 73-78 | `assertIsNone(self.locator.locate(bad))` for `../outside/x`, `..`, `-proj/secret`, `*`, `A + "x"`, `""` | No file exists at any resolved target, so these pass with or without the UUID gate. Precondition does not exercise the guarded path. | WARNING |

**Assertion quality**: 0 CRITICAL, 1 WARNING. No tautologies, ghost loops or mock-heavy tests.

### Quality Metrics
**Linter**: Not available
**Type Checker**: Not available

### Issues Found
**CRITICAL**: None

**WARNING**:
1. Locator UUID gate is not proven by the traversal tests. In `test_non_uuid_and_traversal_are_none`, every subtest except `A.upper()` passes even after the gate is removed, and `A.upper()` only fails on a case-insensitive filesystem. Probe: with the gate removed, `locate("../-proj/<A>")` returns a `Located` for `projects/-proj/../-proj/<A>.jsonl`. The shipped code is correct; the test must place a real file at the traversal target (for example `../-proj/<A>` and `<A>x` with a matching `<A>x.jsonl`) so the gate is load-bearing on any filesystem.
2. Containment is checked at locate time, but `Located.main` and `Located.subagents` are the unresolved paths. A consumer that opens them later follows symlinks again (check-to-use gap). A probe also shows an in-root symlink `<A>.jsonl -> <B>.jsonl` maps session A to B's transcript, which conflicts with "never attribute another session's usage". This needs same-user write access to the projects root, so it is not exploitable remotely. Before slice 4 consumes the locator, return the resolved path and require the resolved basename to be `<uuid>.jsonl` (and the resolved subagent parent to be `<uuid>/subagents`), or open with `O_NOFOLLOW` in the tailer.
3. apply-progress #159 is stale. Its Learned line still says "Locator globs subagents/*.jsonl", which `3050589` corrected, the TDD table has no row for the `3050589` RED/GREEN, and it reports 225 insertions against an actual 226.

**SUGGESTION**:
1. `ClaudeLocator.locate(None)` raises `TypeError` from `UUID.fullmatch`. Mapping only yields `str`, but an `isinstance(session_id, str)` guard keeps the adapter total.
2. The locator logs one line per failed call. Slice 4 polls every 4 s, so a pane with a missing transcript would log continuously; log on state change only.
3. Both the mapping and locator regexes are lowercase-only. The spike did not record Herdr's UUID casing; uppercase values fail safe (pane shows nothing). On case-insensitive filesystems an uppercase on-disk file name matches a lowercase query (same session, harmless). Record the casing in design.md.
4. Inside the project loop, `subs` is reassigned for each matching main. This is harmless because more than one match returns None, but collecting subagents after the uniqueness check would be clearer.

### Deferred
- 3.6/3.7 (slice 3b): Herdr CLI argv threat tests, `herdr_cli.py`, `herdr_socket.py`, `herdr_fallback.py`. `pane.report_metadata` framing is still unverified and is validated through the CLI path first.
- Session change and resume, tick-level clearing and figure display (slice 4).

### Verdict
PASS WITH WARNINGS
All 5 slice-3a tasks are complete, 67/67 tests pass, the build is clean, and 4/4 in-scope session-mapping scenarios are compliant. The locator UUID-gate tests are not discriminating (WARNING 1), and the check-to-use symlink gap must be closed before slice 4 consumes the locator (WARNING 2).

---

## Slice 2 Section (history, unchanged)

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:e66d53700633d496add4c36b1aa18572084a9460023dc2645e5d8eb2cf5a7696
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 4/4
scenarios: 5/5
test_command: python3 -m unittest discover -v
test_exit_code: 0
test_output_hash: sha256:1d76f355b033b470941e691c9095a6acdad6153c28f8da86cabdfb4da5a5d94d
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 2 (re-verification after corrections)

**Change**: agent-token-usage-mvp
**Section**: Slice 2 (tasks 2.1-2.5) plus user-approved carry-overs (a) subagent `isSidechain` counting and (b) requestId -> message.id alias
**Candidate**: branch `slice-2-state`, HEAD `c3b6fd9` (tree `fd2daee`), clean working tree. Correction commit `c3b6fd9` on top of `dc3c8e1` (prior verify report). Correction diff: `git diff dc3c8e1..c3b6fd9` (9 files, +94/-7, 101 changed lines). The slice-2 feature commit `7833cdb` was verified in the prior run (PASS WITH WARNINGS, 47 tests).
**Mode**: Strict TDD
**Scope note**: The envelope counts only slice-2 scoped requirements and scenarios: 4 requirements and 5 scenarios. The full change has 17 requirements and 26 scenarios across 4 specs. Later-slice items are deferred, not failures. The envelope above describes the corrected slice-2 candidate; the slice-1 section is kept below as history.
**Evidence revision**: sha256 over the exact bytes `tree:fd2daee59c040d9a6581f1836434945a5faf1bf3\ntest:sha256:<test output hash>\nbuild:sha256:<build output hash>\n`. The test output contains a wall-clock duration, so its hash is specific to this run.

### Re-verification Delta
| Prior finding | Status now | Evidence |
|---|---|---|
| W1: tail fragment check used remaining file bytes | RESOLVED | `jsonl_tail.py:45-52` now re-reads `min(available, max_fragment + 1)` and skips only when that window has no newline and exceeds `max_fragment`. Test `test_midsize_line_kept_when_much_data_follows` passes. The prior probe (`max_read=32, max_fragment=64`, 52-byte line followed by 160 bytes) now returns the line (offset 61, 2 objects). Boundary probe: a 64-byte line is kept and a 65-byte line is skipped at `max_fragment=64`, which matches "fragment > 16 MiB is skipped". The correction introduces a new resource deviation (WARNING 1 below). |
| W2: `Ledger.apply` returned False on alias-only changes | RESOLVED | `ledger.py:36-50` tracks `changed` for new or remapped aliases and for late binding. Tests `test_apply_true_when_only_alias_learned` (True, True, then False on repeat) and `test_apply_true_on_late_binding` (True, total 3) pass. |
| W3: `.match` with `^...$` accepted a trailing `\n` | RESOLVED | `state_store.py:54` and `log.py:32` use `fullmatch`; no other `.match(` call remains in `src/`. Tests `test_trailing_newline_id_rejected` and `test_token_with_trailing_newline_is_redacted` pass. |
| W4: no tailer -> parser -> ledger test across truncation or rotation | RESOLVED | New `tests/adapters/test_tail_ledger_integration.py`: truncation keeps the total at 12; rotation (`os.replace` plus a new file with an extra id) gives 14, not 26. Both pass. The truncation case is weak (SUGGESTION 7). |

**RED replay (verifier)**: the corrected test tree (`c3b6fd9:tests`) was run over the pre-correction source (`dc3c8e1:src`) in the scratchpad. Result: `Ran 54 tests`, `FAILED (failures=4, errors=1)`. The failures match the apply-progress table exactly: `IndexError` (W1), `'session=?' not found in '... session=x\n\n'` (W3 log), `ValueError not raised` (W3 state), and `False is not true` twice (W2). The two W4 integration tests pass on the old code, as reported (characterization).

### Completeness (slice 2)
| Metric | Value |
|--------|-------|
| Tasks total (slice 2) | 5 (2.1-2.5) plus 2 carry-overs plus 4 verify corrections |
| Tasks complete | 5 (`tasks.md` slice-2 items `[x]`); carry-overs and W1-W4 corrections implemented and tested |
| Tasks incomplete | 0 |
| Later-slice tasks (3.x-6.x) | Unchecked, out of scope |

### Build & Tests Execution
**Build**: Passed (`python3 -m compileall -q src tests`, exit 0, empty output)
**Tests**: 54 passed / 0 failed / 0 skipped (`python3 -m unittest discover -v`, exit 0, Python 3.14.8, `Ran 54 tests ... OK`). New since the prior run: test_jsonl_tail +1 (10), test_log +1 (5), test_state_store +1 (8), test_ledger +2 (11), test_tail_ledger_integration 2 (new file).
**Coverage**: Not available. The `coverage` module is not installed.

### Spec Compliance Matrix (slice-2 scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Incremental tail (RF03, C9) | Growing file: half-written final line counted exactly once | `test_jsonl_tail > test_partial_line_is_counted_once_when_completed`, `test_growth_returns_only_new_lines` | COMPLIANT |
| Incremental tail (RF03, C9) | Truncation: rescan without double-counting known ids | `test_jsonl_tail > test_truncate_rescans_from_start`, `test_rotation_new_inode_rescans`; `test_tail_ledger_integration > test_truncation_rescan_does_not_double_count`, `test_rotation_reread_does_not_double_count` | COMPLIANT (now covered end to end through tailer, parser and ledger) |
| State and retention (RF01, S7) | Pruning after 30 days; state survives restart | `test_state_store > test_prune_removes_sessions_older_than_30_days`, `test_roundtrip_restores_ledger_with_aliases`, `test_unknown_version_or_corrupt_means_rebuild`, `test_rejects_absolute_or_escaping_keys_and_ids`, `test_trailing_newline_id_rejected` | COMPLIANT |
| Least privilege and safe logging (S2-S8), state/log part | Content never stored | `test_log > test_sentinel_never_reaches_state_or_logs`, `test_event_fields_are_ints_or_safe_tokens_only`, `test_token_with_trailing_newline_is_redacted`, `test_exception_logs_type_only`, `test_rotation_settings` | COMPLIANT |
| Claude per-call dedupe, carry-over (b) | Replay with requestId-only duplicate: 5, not 10, incl. late binding and persisted restore | `test_parsers > test_request_id_only_duplicate_resolves_to_message_key`; `test_ledger > test_alias_late_binding_and_restore`, `test_apply_true_on_late_binding`, `test_apply_true_when_only_alias_learned`; `test_state_store > test_roundtrip_restores_ledger_with_aliases` | COMPLIANT |

**Compliance summary**: 5/5 slice-2 scenarios compliant. Carry-over (a) remains covered by `test_parsers > test_subagent_sidechain_lines_are_counted` (passes).

### Correction Risk: per-call read size (RF03 resource bounds)
The spec's Incremental tail requirement sets no byte limits; the bounds come from design.md:57 ("Read <=4 MiB per file per tick ... A fragment >16 MiB without newline is skipped"). The design implicitly allows a single line of 4-16 MiB to be read whole, so a read of up to `max_fragment + 1` bytes (16 MiB + 1) is within the design's own ceiling. That read is a hard bound: it is never larger, and the pre-correction code could already read up to 16 MiB (`fh.read(available)` when `available <= max_fragment`). Verifier measurements with default caps (scratchpad probe, `tracemalloc` peak per call):

| Case | Pre-correction | Corrected |
|---|---|---|
| 40 MiB of ~1 KiB lines (baseline) | 4.0 MiB consumed, 14.7 MiB peak | same |
| 10 MiB line followed by 40 MiB of ~1 KiB lines | line dropped (W1), 4.3 MiB peak | line kept, 16.0 MiB consumed, 6,686 objects, 52.4 MiB peak |
| 17 MiB line followed by 10 lines | skipped, 4.3 MiB peak | skipped, 20.1 MiB peak |

Judgment: the per-call buffer is bounded and matches the design ceiling, so the read size alone is acceptable. However, the fragment branch keeps parsing up to the last newline of the 16 MiB window, so it also consumes about 6 MiB of ordinary lines after the oversized line in the same tick. That goes beyond what the fragment rule needs and breaks the 4 MiB per-tick cadence (WARNING 1). The skip case now buffers 16 MiB + 1 before it decides to skip (SUGGESTION 8). Neither one breaks a spec scenario.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Atomic state write | Implemented | `mkstemp` -> write -> `flush` -> `os.fsync` -> `os.replace`; temp unlinked on any exception. |
| Dirty-only writes | Implemented | In-memory payload comparison per path; `apply()` now also signals alias changes. |
| Unknown `v` / corrupt -> rebuild | Implemented | Unchanged. |
| 30-day retention | Implemented | Unchanged. |
| Ids, offsets, counters only; relative keys | Implemented | Session id is now checked with `fullmatch`. |
| Incremental tail | Implemented | The oversized check uses the current line's length (bounded window of `max_fragment + 1`). See WARNING 1 for the per-tick window. |
| Safe logging | Implemented | Tokens are checked with `fullmatch`; `"x\n"` is redacted to `?`. |
| requestId alias | Implemented | `apply()` returns True when entries or aliases change; False on an exact repeat. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Tailer `{inode, dev, size, offset}`, rescan on inode change or `size < offset` | Yes | `skip` flag still undocumented in design (SUGGESTION 6). |
| Read <= 4 MiB per file per tick, consume to last newline | Partial | Holds for normal ticks. After a 4-16 MiB line, one tick consumes up to 16 MiB including the following lines (WARNING 1). |
| Fragment > 16 MiB without newline skipped | Yes | Now decided on fragment length; boundary verified (64 kept, 65 skipped at cap 64). |
| State schema v1, per-session files, `published.json` | Yes | `aliases` key still missing from design.md (SUGGESTION 6). |
| Atomic write temp -> fsync -> replace | Yes | |
| Logs: counts, exception type, safe tokens; never content | Yes | Anchoring fixed. |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Yes | "Slice 2 corrections" table in apply-progress #159 (W1, W2, W3, W4). |
| All tasks have tests | Yes | 4/4 corrections have test files; all exist. |
| RED confirmed (tests exist) | Yes | Verifier replay over `dc3c8e1:src` reproduced every reported failure (4 failures, 1 error); W4 is declared as characterization and passes on the old code. |
| GREEN confirmed (tests pass) | Yes | 54/54 pass. |
| Triangulation adequate | Yes | W2: learn, repeat (False), late binding. W1: new mid-size case plus the existing oversized-skip and partial-line tests. W4: truncation and rotation. W3: one case per regex (adequate for a single anchoring defect). |
| Safety Net for modified files | Yes | 47 tests reported passing before the correction; all still pass. |

**TDD Compliance**: 6/6 checks passed

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 29 | 3 | unittest |
| Adapter (tempdir I/O) | 23 | 3 | unittest, tempfile |
| Integration (tailer + parser + ledger) | 2 | 1 | unittest, tempfile |
| E2E | 0 | 0 | not installed |
| **Total** | **54** | **7** | |

### Changed File Coverage
Coverage analysis skipped. No coverage tool was detected.

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| `tests/adapters/test_tail_ledger_integration.py` | 40-42 | `assertEqual(self.ledger.total, 12)` after truncation | The same value results whether the tailer rescanned or read nothing, so this test alone cannot prove the rescan. `test_truncate_rescans_from_start` covers the rescan at tailer level, and the rotation test does distinguish (14 vs 12 vs 26). | SUGGESTION |

**Assertion quality**: 0 CRITICAL, 0 WARNING. All other new assertions check concrete values produced by production code.

### Quality Metrics
**Linter**: Not available
**Type Checker**: Not available

### Issues Found
**CRITICAL**: None

**WARNING**:
1. `jsonl_tail.py:47-52` (introduced by the W1 correction). When the first 4 MiB has no newline, the fragment branch reads `min(available, max_fragment + 1)` and then consumes up to the last newline of that whole window. The read is bounded at 16 MiB + 1, which is within the design ceiling. But one tick also parses every ordinary line that follows the oversized line inside that window. Measured: a 10 MiB line followed by small lines gives 16.0 MiB consumed and 52.4 MiB peak in one call, against 14.7 MiB for a normal 4 MiB tick. This deviates from design.md:57 ("Read <=4 MiB per file per tick") beyond what the 16 MiB fragment rule requires. Minimal fix: in the fragment branch, consume only through the first newline (`data.find(b"\n")`), so the next tick returns to the 4 MiB cadence. Not blocking: bounded, transient, rare, and no spec scenario is affected.

**SUGGESTION** (prior S1-S6 re-validated: all still open; none was in scope for the correction):
1. Still open: `prune` globs `*.json` only, so a `.tmp` orphaned by a hard kill is never removed.
2. Still open: no parent-directory fsync after `os.replace`.
3. Still open: file keys `""`, `"."`, `"~/x"` are accepted; consider an allowlist.
4. Still open: same-inode truncate that regrows past the old offset between polls is not detected; document it.
5. Still open: `make_logger` (`log.py:10-20`) adds a duplicate handler when called twice with the same name.
6. Still open: design.md State Schema lacks the `aliases` map and the tailer `skip` flag.
7. New: strengthen `test_truncation_rescan_does_not_double_count` by writing a new id after truncation (for example `m1` plus `m3`), so the assertion can distinguish a rescan from a no-op.
8. New: the skip decision now buffers up to 16 MiB + 1 before it falls back to 64 KiB chunk scanning (20.1 MiB peak against 4.3 MiB before). This is within the design bound; a streaming newline search beyond `max_read` would avoid the large buffer.

### Verdict
PASS WITH WARNINGS
W1-W4 are resolved with reproduced RED and passing GREEN (54/54), the build is clean, and all 4 slice-2 requirements and 5/5 scenarios are compliant. The W1 correction keeps the per-call read within the design's 16 MiB ceiling, but it lets one tick consume ordinary lines past an oversized line (WARNING 1, non-blocking). Prior suggestions S1-S6 remain open.

---

## Slice 1 Section (history, unchanged)

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:ae822dca66b6ff8188002c11718a94596c1815efada1233082d6dfcf722e88ca
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 4/4
scenarios: 6/6
test_command: python3 -m unittest discover -v
test_exit_code: 0
test_output_hash: sha256:cb6393158b845e8417cc8b6da7ef798aa5c270f221342307417a8e654a4c3663
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: agent-token-usage-mvp
**Section**: Slice 1 (tasks 1.0-1.7): domain + parsers (re-verification #3)
**Candidate**: branch `slice-1-domain`, HEAD `9c93cc5` (tree `e266b4d`), clean working tree. Code commit `419482c` over `main` `720c2cc`. `9c93cc5` adds one ledger test, rewords the `codex.py` docstring (no behavior change), and commits the prior verify report.
**Mode**: Strict TDD
**Scope note**: The envelope counts cover only slice-1 requirements and scenarios: 4 requirements and 6 scenarios. The full change has 17 requirements and 26 scenarios across 4 specs. Requirements for later slices are listed as deferred, not as failures.
**Evidence revision**: sha256 over `tree:<HEAD tree>\ntest:<test output hash>\nbuild:<build output hash>\n`.

### Re-verification Delta
| Prior finding | Status now | Evidence |
|---|---|---|
| CRITICAL 1: "Three prompts" scenario PARTIAL (5/6) | RESOLVED | `tests/unit/test_ledger.py > LedgerTest.test_total_grows_after_each_of_three_responses` applies `msg_1`..`msg_3` (per-call totals 12, 14, 16) and asserts the total read after each apply equals `[12, 26, 42]`, which is strictly increasing. It passed at runtime (24/24). |
| WARNING 1: `codex.py` docstring says "open question resolved" | RESOLVED (doc); assumption remains | `src/token_usage/sources/codex.py:11-13` now says "Assumes ... (unproven; see design.md open questions)", which matches design.md. The assumption itself is still tracked for slice 6. |
| WARNING 2: no subagent-counting test | CARRIED OVER (user-approved) | Recorded in apply-progress as slice-2 carry-over (a). |
| SUGGESTION 2: requestId and message.id alias double count | CARRIED OVER (user-approved) | Recorded in apply-progress as slice-2 carry-over (b). |
| SUGGESTIONS 1, 3, 4 | UNCHANGED | Informational. |

### Completeness (slice 1)
| Metric | Value |
|--------|-------|
| Tasks total (slice 1) | 8 (1.0-1.7) |
| Tasks complete | 8 (`tasks.md` lines 34-41 `[x]`) |
| Tasks incomplete | 0 |
| Later-slice tasks (2.x-6.x) | Unchecked, out of scope |

### Build & Tests Execution
**Build**: Passed (`python3 -m compileall -q src tests`, exit 0, empty output)
**Tests**: 24 passed / 0 failed / 0 skipped (`python3 -m unittest discover -v`, exit 0, Python 3.14.8, `Ran 24 tests ... OK`). Per file: test_formatting 6, test_ledger 8, test_parsers 10.
**Coverage**: Not available. The `coverage` module is not installed.

### Spec Compliance Matrix (slice-1 scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Formatting (RF05) | Examples (950, 1250, 125400, 1200000) | `test_formatting > FormatTokensTest.test_spec_examples`, `test_boundaries`, `test_max_length` | COMPLIANT |
| Total definition (RF02) | Sum = 135 (thinking 8 not re-added) | `test_formatting > UsageCallTest.test_thinking_not_added_again`, `test_parsers > test_basic_total_and_thinking_not_added` | COMPLIANT |
| Claude per-call dedupe | Repeated lines | `test_ledger > test_repeated_id_counts_once`, `test_parsers > test_duplicates_and_request_id_fallback` | COMPLIANT |
| Claude per-call dedupe | Replay | `test_ledger > test_replay_leaves_total_unchanged`, `test_parsers > test_resume_copy_and_replay_do_not_double_count` | COMPLIANT |
| Claude per-call dedupe | Three prompts (grows monotonically when polled after each) | `test_ledger > test_total_grows_after_each_of_three_responses` (3 responses, total read after each: 12, 26, 42) | COMPLIANT (domain level; end-to-end polling is slice 4) |
| Codex cumulative parsing | Snapshots 100, 250, 250 -> 250 | `test_parsers > CodexParserTest.test_snapshots_use_latest_not_sum`, `test_null_info_ignored` | COMPLIANT |

**Compliance summary**: 6/6 slice-1 scenarios compliant.

**Deferred to later slices (not failures)**:
- README documentation of the total: slice 6 (task 6.3).
- Persistence across restart, and end-to-end polling: slices 2 and 4.
- Incremental tail, state, and retention: slice 2.
- Session mapping: slice 3.
- Publish and clear: slice 4.
- Plugin lifecycle: slice 5.
- Approval-gated config patch: slice 6.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Formatting | Implemented | Integer round-half-up. Output capped at 80 characters. Internal values stay integers. |
| Total definition | Implemented | `UsageCall.total = input + output + cache_creation + cache_read`. `thinking` is informational only. |
| Claude per-call dedupe | Implemented | Key is `message.id`, with `requestId` as fallback. Ledger takes the field-wise max and updates the total incrementally. Synthetic, error, and malformed lines are skipped. |
| Codex cumulative parsing | Implemented (assumption) | Uses the latest `total_token_usage`. Null `info` is ignored. No snapshots yields `None`. Total `input + output` is an unproven assumption (WARNING 1). |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Pure `sources/` parsers | Yes | No I/O. |
| Ledger: message.id -> requestId, field-wise max, incremental total | Yes | Alias fix carried over to slice 2. |
| Subagents share one session ledger | Yes (parser side) | Regression test carried over to slice 2. |
| Fixture list | Partial | `partial_tail.jsonl` and the subagent fixture belong to slices 2 and 3. |
| Open question: Codex total | Yes | design.md and the `codex.py` docstring now agree that it is unproven. |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Yes | Table in apply-progress #159 (rows 1.0, 1.1/1.2, 1.3/1.4, 1.5-1.7). |
| All tasks have tests | Yes | 1.1/1.2 -> test_formatting.py, 1.3/1.4 -> test_ledger.py, 1.5-1.7 -> test_parsers.py. Task 1.0 is approved bootstrap with no code. |
| RED confirmed (tests exist) | Yes (with caveat) | 3/3 test files exist. RED is actor-reported; the single code commit cannot show it in history. The new three-response test is a characterization test of existing behavior with no production change, so no RED phase applies to it; it is judged on assertion quality and runtime pass only. |
| GREEN confirmed (tests pass) | Yes | 24/24 pass. The apply-progress count for test_ledger.py (7/7) predates the added test; the file now has 8. |
| Triangulation adequate | Yes | Distinct expected values per behavior; the new test asserts three different cumulative totals. |
| Safety Net for modified files | Yes | `test_ledger.py` was modified in `9c93cc5`; the full suite passes with the prior 7 ledger tests unchanged. `codex.py` change is docstring-only. |

**TDD Compliance**: 6/6 checks passed

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 24 | 3 | unittest |
| Integration | 0 | 0 | not applicable in slice 1 |
| E2E | 0 | 0 | not installed |
| **Total** | **24** | **3** | |

### Changed File Coverage
Coverage analysis skipped. No coverage tool was detected.

### Assertion Quality
**Assertion quality**: All assertions verify real behavior. The new test calls production code (`Ledger.apply`, `Ledger.total`) inside a loop over a fixed three-element list (not a ghost loop), and asserts the full sequence after the loop with one exact-value assertion.

### Quality Metrics
**Linter**: Not available
**Type Checker**: Not available

### Issues Found
**CRITICAL**: None

**WARNING**:
1. The Codex total (`input + output`) remains an unproven assumption. It ignores `cache_write_input_tokens` and the upstream `total_tokens`. design.md and the docstring now both track it for validation in slice 6. Risk is low because Codex is fixture-only in the MVP.
2. No test guards subagent (`isSidechain: true`) counting. User-approved carry-over to slice 2.

**SUGGESTION**:
1. Claude: a malformed `thinking_tokens` drops the whole line. Consider ignoring just that field.
2. requestId and message.id alias double count: user-approved carry-over to slice 2, including persisting the alias map.
3. Codex: cross-check against `total_tokens` when present.
4. Add `coverage` as an optional dev tool.
5. Refresh apply-progress #159 to mention the added characterization test (test_ledger.py now 8 tests, suite 24).

### Verdict
PASS WITH WARNINGS
All 4 slice-1 requirements and 6/6 scenarios are covered by passing tests (24/24), the build is clean, and the prior CRITICAL is resolved; the remaining warnings are a tracked Codex assumption and a user-approved slice-2 carry-over.
