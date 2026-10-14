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

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:33268f9fd3b3d1f58c42e0e6590ab0138b4ecc05c1221d2194e0ed814410b4c4
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 3/3
scenarios: 4/4
test_command: python3 -m unittest discover
test_exit_code: 0
test_output_hash: sha256:4b0dd352398e6b7486ec701f4c6be0efe2b1fc412f14166ba9f101a691b3c8cf
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Slice 3a Re-verification (bounded correction faaca54)

**Candidate**: branch `slice-3a-mapping`, HEAD `faaca54` (tree `535aaee`), on `55a1a37`. Diff `git diff 55a1a37 faaca54`: 2 files, +48/-13 (`src/token_usage/adapters/claude_locator.py`, `tests/adapters/test_claude_locator.py`).
**Scope**: Confirms the prior slice-3a findings and looks only for regressions introduced by the correction. This is not a fresh full-slice audit. Under the single-correction rule, new non-critical observations are carry-overs.
**Evidence revision**: sha256 over `tree:535aaeeeb51b11194b790d27002415d863f47fcf\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`.

### Build & Tests
- Tests: `python3 -m unittest discover`, exit 0, `Ran 71 tests`, OK (67 prior plus 4 new locator tests).
- Build: `python3 -m compileall -q src tests`, exit 0, empty output.

### Prior Findings
| Finding | Status | Evidence |
|---|---|---|
| W1: traversal test not discriminating | RESOLVED | `test_claude_locator.py:71-80` creates a real file for each bad input. Mutation in a scratch copy (UUID guard removed, `isinstance` kept): 5 subtests FAIL (`..`, `*`, `A.upper()`, `A+"x"`, `""`). `../outside/x` and `-proj/secret` still pass because the new basename check (`claude_locator.py:38`) also rejects them (defense in depth, see S-a). |
| W2: check-to-use gap and in-root `<A>.jsonl -> <B>.jsonl` | RESOLVED | `_resolve` (`claude_locator.py:23-25`) returns the realpath only when it is inside the resolved root and is a file. The main is accepted only if the resolved basename equals `<uuid>.jsonl` (`:38`). Subagents are accepted only if the resolved path matches `agent-*.jsonl` under `<uuid>/subagents` (`:49`). `Located` now holds resolved paths. Tests: `test_in_root_main_symlink_to_other_session_is_none` (:86), `test_in_root_subagent_symlink_to_other_session_is_dropped` (:92). Verifier probes: a symlinked `<A>` dir pointing to `<B>` gives 0 subagents; a symlinked `<A>/subagents` pointing to `<B>/subagents` gives 0 subagents; an in-root project-dir alias or a main symlink to another project's `<A>.jsonl` gives None (ambiguous, fail-closed). Hardlinks are out of scope (same-user write access, indistinguishable from a regular file). |
| W3: stale apply-progress | RESOLVED | Engram #159 (`sdd/agent-token-usage-mvp/apply-progress`) records `3050589`, `faaca54`, 71 tests, +48/-13, the `agent-*.jsonl` glob, resolved-path semantics, and TDD rows for each correction (W1 mutation result matches the verifier's 5 failing subtests). |
| S1: `locate(None)` raised `TypeError` | RESOLVED | `claude_locator.py:28` `isinstance` guard; `test_non_str_session_id_is_none` (:82) covers None and int. |
| S4: subagents collected inside the loop | RESOLVED | Subagents are collected after the single-match check (`claude_locator.py:40-50`); `test_ambiguous_does_not_leak_subagents` (:101). |
| S2, S3 | OPEN (not in scope) | Log-on-change (slice 4) and UUID casing note unchanged. |

### Issues Found
**CRITICAL**: None

**WARNING** (carry-over, non-blocking):
1. Duplicate subagent paths. `claude_locator.py:47-50` does not deduplicate resolved paths. Probe: `<A>/subagents/agent-dup.jsonl -> agent-a.jsonl` in the same directory returns `agent-a.jsonl` twice. A consumer that tails each entry would count that transcript twice. Before the correction the list held two different paths to the same file, so the double count is not new, but resolving paths now makes the fix trivial: skip a `real` already in `subs` (or use a dict keyed by path). It needs same-user write access, and Claude Code does not create such links. Fix before slice 4 consumes `Located.subagents`.

**SUGGESTION** (carry-over):
1. (S-a) Subagent ownership is checked by directory names only (`claude_locator.py:49`). Probe: `-p/<A>/subagents -> -q/x/<A>/subagents` is accepted, because the target is still named `<A>/subagents`. That is the same session id, so nothing is attributed to another session. A stricter check would be `real.parent.parent == Path(os.path.realpath(project / session_id))`. Similarly, a main symlink to a non-project file named `<A>.jsonl` (for example `-p/nested/<A>.jsonl`) is accepted. That is acceptable under the same-session rule.
2. (S-b) An in-root alias of a project directory (or a main symlink to another project's `<A>.jsonl`) makes `mains` hold the same resolved file twice, so the result is "ambiguous" (None) even though only one transcript exists. This fails closed and is unchanged from before the correction. Deduplicating `mains` by resolved path would avoid hiding a figure.
3. (S-c) Two of the seven traversal subtests (`../outside/x`, `-proj/secret`) are now guarded by the basename check, not only the UUID gate. That is fine, but the test comment at `test_claude_locator.py:75` ("each would resolve to a real file without the UUID guard") overstates what those two subtests prove.

### Regressions Introduced by the Correction
None found. Resolved paths are always under `root_real`, matching the prior behavior where project paths came from `root_real.iterdir()`. No consumer of `Located` exists yet in `src/` (slice 3b/4).

### Verdict
PASS WITH WARNINGS
W1, W2, W3, S1 and S4 are resolved and 71/71 tests pass. The UUID gate is now load-bearing, and the locator returns resolved, uuid-named paths that cannot be redirected to another session's main or subagent transcripts. One carry-over WARNING remains: deduplicate resolved subagent paths before slice 4 consumes them.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:17f4170983fb79e8be37dbfcfce8b9a4fcfdd650eba6de74e282ea1547078ee2
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 2/2
scenarios: 1/1
test_command: python3 -m unittest discover
test_exit_code: 0
test_output_hash: sha256:2f52d71bc38bd761711d0edc4cd13c2f988190b91c333d891467222f446ec11b
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 3b (tasks 3.6-3.7, Herdr transport)

**Change**: agent-token-usage-mvp
**Mode**: Strict TDD
**Candidate**: branch `slice-3b-herdr`, HEAD `fc9583f` (tree `12586c7`), commits `820e2ff` and `fc9583f`. Diff `git diff slice-3a-mapping slice-3b-herdr`: 9 files, +414/-2. The user accepted the 16-line overage.
**Evidence revision**: sha256 over `tree:12586c7ba407920fb15c672230688cde7547eaf7\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`.
**Scope**: Slice-scoped. There are 2 requirements: Publish and clear (RF04, C11), transport part only, and Least privilege (S2-S8), the subprocess and logging clauses only. There is 1 scenario: "Herdr unreachable", adapter-level part only. Task 4.3 owns the end-to-end "without crashing" part.
**Safety**: The real `herdr` binary and the real socket were never used. The tests use a fake bin and an AF_UNIX fake server. Mutations and probes ran only in a scratchpad copy made with `git archive`.

### Completeness
| Metric | Value |
|---|---|
| Slice 3b tasks | 2 (3.6, 3.7) |
| Complete | 2 |
| Incomplete | 0 (slices 4-6 are out of scope) |

### Build & Tests
- Tests: `python3 -m unittest discover` exited 0. It ran 88 tests, all OK: 71 earlier tests plus 8 CLI, 7 socket and 2 fallback tests.
- Build: `python3 -m compileall -q src tests` exited 0 with empty output.
- Focused command from tasks.md work unit 3, `python3 -m unittest discover -s tests/adapters -p "test_herdr*"`, FAILS with 3 errors, `ModuleNotFoundError: token_usage`. See W1.
- Coverage: skipped because no coverage tool is installed.

### Spec Compliance Matrix
| Requirement | Scenario / clause | Test | Result |
|---|---|---|---|
| Publish and clear (RF04, C11) | Herdr unreachable: when the socket fails, the CLI fallback is tried and the failure is logged | `test_herdr_fallback > test_socket_failure_falls_back_per_call_and_retries_socket` | COMPLIANT for the transport part. Task 4.3 owns the end-to-end no-crash part. |
| Least privilege (S2-S8) | subprocess without a shell, structured arguments | `test_herdr_cli > test_metacharacters_are_literal_single_argv_item`, `test_clear_argv`, `test_invalid_ids_rejected_before_spawn` | COMPLIANT (mutation M3 `shell=True` was killed) |

### Threat Matrix (Subprocess argv row, task 3.6)
| Row | Code | Test | Mutation |
|---|---|---|---|
| relative bin rejected | `herdr_cli.py:33` `os.path.isabs` | `test_relative_bin_rejected` (:20) | M1 SURVIVED: the test passes through `isfile` because no `./herdr` exists (W2) |
| missing bin rejected | `herdr_cli.py:33` `isfile` | `test_missing_bin_rejected` (:24) | covered |
| non-executable rejected | `herdr_cli.py:33` `os.access X_OK` | `test_non_executable_rejected` (:28) | M2 KILLED |
| metacharacters literal | `herdr_cli.py:58-59` single argv item | :42 | M3 KILLED |
| no shell | `herdr_cli.py:41` `shell=False` | :42, :52 | M3 KILLED (5 failures) |
| 2 s timeout | `herdr_cli.py:32,41` | :60 (timeout=0.3) | M5 (no timeout) KILLED. M6 (default 30 s) SURVIVED (W2) |
| leading-dash IDs | `herdr_cli.py:16` | :68 | M4 KILLED |

### Correctness (Static + Probe Evidence)
| Area | Status | Notes |
|---|---|---|
| CLI argv vs `herdr pane report-metadata <PANE_ID> --source <ID> [--token NAME=VALUE] [--clear-token NAME] [--seq N] [--ttl-ms N]` | OK | `herdr_cli.py:58-64` matches the help. `list_panes` sends `pane list` and accepts the verified `{"id","result":{"type","panes"}}` envelope (`panes_from`, :20-28; probe OK). |
| Token value injection | OK for flags | `--token` and `NAME=VALUE` are 2 argv items. NAME is validated (`[A-Za-z0-9_.:-]{1,128}`, no leading `-`, no `=`), so the combined item always starts with NAME and never with `-`. Probes: values `-x` and `--ttl-ms=1` arrive as `usage=-x` and `usage=--ttl-ms=1`, and argv length stays 11. A value with `=` is safe if herdr splits on the first `=`. Values are not validated: a newline passes through literally, and a NUL raises an uncaught `ValueError` (W3). |
| ID validation before spawn | OK | `_check` (:14-17) runs before `_run`, and the test asserts that no argv.json exists (:73). |
| Socket robustness | Mostly OK | Partial reads loop until a newline (`herdr_socket.py:25-29`). There is an 8 MiB cap (:30-31), an id match and error check (:44), `closed_without_newline` (:28), connect, timeout and JSON errors mapped to `HerdrError(type name)` (:42-43), and trailing data after the first line is discarded. The timeout applies to each recv, not to the whole call (W4). |
| Fallback semantics | OK | Per call: the socket is retried on the next call (test :40-43; M14 sticky-fallback KILLED). Only `HerdrError`/`OSError` are caught (`herdr_fallback.py:20`), and `report`/`clear` always go through the CLI (:24-28). |
| Logging privacy | OK | Only `herdr_fallback error=<ExcTypeName>` is logged, through `log_event`, which reduces every value to `[A-Za-z0-9_-]{1,40}` or `?`. `HerdrError` carries fixed reason tokens, and `from None` drops chained context (no stderr, paths or messages). |
| HerdrPort / HerdrError | OK | `ports.py:29-36` |

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| Socket first, per-call CLI fallback, 2 s timeouts | Yes (reads) | Writes are CLI-only per the Open Questions decision (design.md:111). The spec still says "publish ... via the socket API with CLI fallback" (W5). |
| Security Boundaries: subprocess argv only, `HERDR_BIN_PATH` absolute and executable | Yes | |
| Logs: exception type only, never messages or paths | Yes | |
| Testing strategy: CLI fake bin, socket AF_UNIX test server | Yes | `tests/adapters/herdr_fakes.py` |

### TDD Compliance
| Check | Result | Details |
|---|---|---|
| TDD evidence reported | Yes | Engram apply-progress slice 3b table |
| All tasks have tests | Yes | 3 rows (CLI, socket, fallback) |
| RED confirmed (tests exist) | Yes, weak | RED is recorded as ImportError (module missing), not as a behavioral failure. RED-before-GREEN cannot be told apart in history because each commit holds both tests and code. |
| GREEN confirmed | Yes | 8/8, 7/7 and 2/2 pass in the full run |
| Triangulation | Yes | The claimed counts match the files (8/7/2) |
| Safety net | Yes | 71 passing. ports.py was modified, the other files are new. |

### Test Layer Distribution
| Layer | Tests | Files |
|---|---|---|
| Adapter (fake bin / AF_UNIX server) | 17 | 3 (+ `herdr_fakes.py`) |

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|---|---|---|---|---|
| `tests/adapters/test_herdr_cli.py` | 20-22 | `HerdrCli("herdr")` raises | Does not discriminate: it is rejected by `isfile` even without `isabs` (M1 survived) | WARNING (W2) |
| `tests/adapters/test_herdr_socket.py` | 36-41 | oversized raises | Does not discriminate: the server closes without a newline, so `closed_without_newline` fires even without the cap (M8 survived) | WARNING (W2) |
| `tests/adapters/test_herdr_socket.py` | 20-24 | error reply raises | Passes without the `"error" in reply` check through `unexpected_shape` (M10 survived). The behavior is still safe. | SUGGESTION |
| `tests/adapters/test_herdr_fallback.py` | 37-38 | `assertIn("herdr_fallback", ...)` | Does not pin the exact log line (M12 survived). `log_event` sanitizes anyway. | SUGGESTION |
No tautologies, ghost loops, or assertions that never call production code.

### Mutation Summary (scratch copy, `PYTHONPATH=src`, `test_herdr*`)
Killed: M2 X_OK, M3 shell=True, M4 leading-dash, M5 no timeout, M9 id match, M13 fallback re-raise, M14 sticky fallback.
Survived: M1 isabs, M6 CLI default 30 s, M7 no `_check` in `clear`, M8 size cap, M10 error check, M11 socket default timeout None, M12 log extra field, M15 `report` via socket when a socket exists, M16 no `stdin=DEVNULL`.

### Issues Found
**CRITICAL**: None

**WARNING**:
1. (W1) Test isolation and focused command. `test_herdr_cli.py`, `test_herdr_socket.py` and `test_herdr_fallback.py` do not add `src` to `sys.path`, while every other test module does (for example `test_claude_locator.py:7`). They only pass when an earlier module has already inserted it. Both `python3 -m unittest tests.adapters.test_herdr_cli` and the tasks.md work-unit-3 focused command `discover -s tests/adapters -p "test_herdr*"` fail with `ModuleNotFoundError: token_usage`.
2. (W2) Several threat guards have no discriminating test. The `isabs` guard (`herdr_cli.py:33`) is untested in effect, so M1 survived. The 2 s default timeout (task 3.6) is not asserted for the CLI (`:32`) or the socket (`herdr_socket.py:18`), so M6 and M11 survived. The socket size cap (`herdr_socket.py:30-31`) is not proven, so M8 survived. `clear` validation (`herdr_cli.py:62`) is untested, so M7 survived. Fix: run the test with a cwd that contains an executable `herdr`, assert default timeouts, send >max bytes on a still-open connection, and test `clear` with invalid IDs.
3. (W3) The token value is not validated and the error contract leaks. `herdr_cli.py:59` passes `value` verbatim. A NUL raises an uncaught `ValueError` (probe), and a non-int `seq` also raises `ValueError`. `_run` catches only `TimeoutExpired`/`OSError`/`UnicodeDecodeError` (:44), so callers expecting `HerdrError` can crash. A newline is passed into Herdr metadata as-is. Values are meant to come from the formatter (ints, at most 80 chars), but the adapter should enforce printable characters, at most 80 chars, and `seq`/`ttl_ms` as non-negative ints, and raise `HerdrError("invalid_value")`.
4. (W4) The socket timeout applies to each recv, not to the whole call. `sock.settimeout` (`herdr_socket.py:38`) bounds each `recv`. A probe server that sent 1 byte every 0.1 s held a `timeout=0.2` call for 1.56 s and then succeeded. A peer that drips bytes can stall a tick for up to (8 MiB / chunk) x 2 s. The peer is same-user local, but the design states 2 s timeouts. Fix: track a monotonic deadline and set the remaining time on each recv.
5. (W5) Spec drift. sidebar-metadata "Publish and clear" says publish goes "via the socket API with CLI fallback". The implementation publishes and clears through the CLI only (`herdr_fallback.py:24-28`; `herdr_socket.py:48-51` raises `NotImplementedError`), as decided in design.md:111. Update the spec wording or track it as an explicit deviation until socket `report_metadata` is verified.

**SUGGESTION**:
1. `HerdrSocket(None)` raises an uncaught `TypeError` (probe), and the fallback catches only `HerdrError`/`OSError`. Slice 4 wiring must pass `socket_client=None` when `HERDR_SOCKET_PATH` is unset, or the socket client must validate its path.
2. Add a test where a socket exists and `report`/`clear` still go to the CLI (M15 survived). Today a regression would hit `NotImplementedError`.
3. CLI `list_panes` has no stdout size cap, while the socket has 8 MiB. Consider matching them.
4. Negative `seq` produces `--seq -5`. That is harmless (not injection) but meaningless, so reject it with W3.
5. Pin the exact fallback log line (`herdr_fallback error=HerdrError`) and tighten the error-reply test so it fails without the `"error"` check.

### Verdict
PASS WITH WARNINGS
88/88 tests pass and the build is clean. The argv threat rows are implemented (no shell, literal metacharacters, absolute executable bin, validated IDs, timeout), and the per-call fallback with privacy-safe logging is verified. Five warnings remain: test isolation, and the focused command failing because of it; non-discriminating tests for isabs, the default timeouts and the size cap; no value validation and the `ValueError` leak; the per-recv rather than per-call socket timeout; and the spec wording for socket publish.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:54484197c5678d4199e33979e040f509e56c891b345a11482ec680ec7f482857
verdict: pass
blockers: 0
critical_findings: 0
requirements: 2/2
scenarios: 1/1
test_command: python3 -m unittest discover
test_exit_code: 0
test_output_hash: sha256:a2a2d4c5370444daca71c724f60570d0f37be0a7ca0bd73f3a57289635f6c372
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Slice 3b Re-verification (bounded correction b456422)

**Change**: agent-token-usage-mvp
**Mode**: Strict TDD
**Candidate**: branch `slice-3b-herdr`, HEAD `b456422` (tree `6ad561d`), on `887472f`. Diff `git diff 887472f b456422`: 6 files, +90/-16 (`herdr_cli.py`, `herdr_socket.py`, three `test_herdr_*.py`, `specs/sidebar-metadata/spec.md`).
**Scope**: Confirms the prior slice-3b findings (W1-W5) and looks only for regressions introduced by the correction. This is not a fresh full-slice audit. Under the single-correction rule, new non-critical observations are carry-overs. Envelope counts are unchanged from the slice-3b section: 2 requirements (Publish and clear, transport part; Least privilege, subprocess and logging clauses) and 1 scenario (Herdr unreachable, adapter-level part).
**Evidence revision**: sha256 over `tree:6ad561d2e718a9cb104ce5d859f1855a5d2a1458\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`. The test output contains a wall-clock duration, so its hash is specific to this run.
**Safety**: The real `herdr` binary and the real socket were never used. Tests use a fake bin and an AF_UNIX fake server. Commands and mutations ran in a `git archive b456422` scratch copy with `python3 -B` and no `__pycache__`. The repository was not modified.

### Build & Tests
- Tests: `python3 -m unittest discover` exited 0. It ran 94 tests, all OK (88 prior plus 6 new: 3 CLI, 3 socket). The same command in the repository with `-B` also gives 94 OK.
- Standalone: `python3 -m unittest tests.adapters.test_herdr_cli` gives 11 OK, `tests.adapters.test_herdr_socket` gives 10 OK, and `tests.adapters.test_herdr_fallback` gives 2 OK.
- Focused command from tasks.md work unit 3, `python3 -m unittest discover -s tests/adapters -p "test_herdr*"`, now gives 23 OK. Before the correction it failed with `ModuleNotFoundError`.
- Build: `python3 -m compileall -q src tests` exited 0 with empty output.
- Coverage: skipped because no coverage tool is installed.

### Prior Findings
| Finding | Status | Evidence |
|---|---|---|
| W1: test imports not standalone | RESOLVED | `sys.path.insert(0, .../src)` at `test_herdr_cli.py:9`, `test_herdr_socket.py:7`, `test_herdr_fallback.py:9`. All three modules and the focused discover command pass on their own (see Build & Tests). |
| W2: guards without discriminating tests | RESOLVED | Mutations in the scratch copy: M1 (`isabs` removed, `herdr_cli.py:38`) is KILLED by `test_relative_bin_rejected` (:24). That test now chdirs into a directory that holds an executable `herdr` and asserts it exists, so only `isabs` can reject the call. M6 (CLI default 30 s, `:37`) is KILLED by `test_default_timeout_is_2` (:33). M11 (socket default `None`, `herdr_socket.py:19`) is KILLED by `test_herdr_socket.py:53` (plus 7 TypeErrors, see S2). M8 (size cap disabled, `herdr_socket.py:35`) is KILLED by `test_oversized_with_newline` (:47), whose 9 KB reply ends in a newline. M7 (`_check` removed from `clear`, `herdr_cli.py:71`) is KILLED by `test_clear_invalid_ids_rejected_before_spawn` (:36). |
| W3: value/seq/ttl validation and ValueError leak | RESOLVED | `report` checks `value` before spawn: it must be a str of 1-80 chars and `isprintable()` (`herdr_cli.py:63-64`). `_int` (`:20-22`) rejects bool, non-int and negative values for `seq` and `ttl_ms` (`:65-66`) and for `clear` `seq` (`:72`). `_run` maps `ValueError` to `HerdrError` (`:49`). The test (`test_herdr_cli.py:43`) covers NUL, newline, empty, 81 chars, non-str, str seq, negative seq and ttl, bool seq and ttl, float ttl, and bad `clear` seq. It also asserts that nothing was spawned and that 80 chars with 0/0 is accepted. 11 of the 12 validation mutations are KILLED (each clause of the value check, each `_int` clause, each `_int` call site). Probes reject U+2028, TAB, a lone surrogate and ESC. `1.3k tokens`, `é 5`, `-x`, `--ttl-ms=1` and `a=b` still arrive as a single `usage=<value>` argv item. |
| W4: per-recv rather than per-call socket timeout | RESOLVED | A monotonic deadline is set before connect (`herdr_socket.py:42`). Each recv uses the time left (`:27-30`) and raises `deadline_exceeded` when it runs out. Restoring the `887472f` socket module makes `test_slow_drip_hits_total_deadline` (:56) fail (`10.70 not less than 1.0`). Probe: a 1-byte-per-0.1 s drip with `timeout=0.2` now stops at 0.202 s (`TimeoutError`). Before the correction it stalled 1.56 s. |
| W5: spec wording on publish via CLI | RESOLVED | `specs/sidebar-metadata/spec.md:17` now says reads (`pane list`) go through the socket with CLI fallback, and metadata writes go through `herdr pane report-metadata` until socket `report_metadata` is verified, citing design.md Open Questions (`design.md:111`). This matches `herdr_fallback.py:24-28` and `herdr_socket.py:53-56`. |

### Mutation Summary (scratch copy, `python3 -B`, per test module)
Killed (18): M1, M6, M7, M8, M11, W3a-W3k (11 validation mutations), the W4 full revert (the `887472f` socket module), and W4a+W4b combined (slow-drip test fails at 10.9 s).
Survived (3, all equivalent or unreachable):
- W3l: `_run` catching `UnicodeDecodeError` instead of `ValueError`. Every argv value is now validated before spawn, so no test can reach a `ValueError` from `subprocess.run`. The `:49` catch is defense in depth. `UnicodeDecodeError` is a `ValueError` subclass, so it is still covered.
- W4a: `settimeout(self._timeout)` with the deadline check kept. This is equivalent within one recv timeout, because the deadline check still ends the loop.
- W4b: deadline check removed. This is equivalent because `settimeout` with a negative value raises `ValueError`, which maps to `HerdrError`.

### Issues Found
**CRITICAL**: None

**WARNING**: None. The prior W1-W5 are resolved, and the correction introduced no new warning.

**SUGGESTION** (new, from the correction; carry-over under the single-correction rule):
1. (S1) `connect` and `sendall` still use the full `self._timeout` (`herdr_socket.py:44-46`), not the time left. The worst case is about 2x the timeout before `_read_line` raises `deadline_exceeded`. In practice an AF_UNIX connect plus a 60-byte send does not block. Calling `sock.settimeout(max(0, deadline - time.monotonic()))` before `sendall` would make the bound exact.
2. (S2) `HerdrSocket(path, timeout=None)` now raises an uncaught `TypeError` (`time.monotonic() + None`, `herdr_socket.py:42`), which `FallbackHerdr` does not catch. Before the correction, `None` meant blocking. Nothing in `src/` passes `None`, and the signature declares `float`. Slice 4 wiring should keep the default or reject non-positive or `None` timeouts in `__init__`. This is related to the open carry-over `HerdrSocket(None)` path `TypeError`.
3. (S3) `test_slow_drip_hits_total_deadline` asserts a wall-clock bound below 1.0 s (5x the 0.2 s timeout). The margin is generous, but on an overloaded CI runner it could flake. A looser bound (for example 2.0 s against the 10 s drip) would still discriminate.
4. (S4) The "Herdr unreachable" scenario (`spec.md:29-33`) still reads "WHEN publishing THEN the CLI fallback is tried". With writes CLI-only, that is true but trivially so. The covering test is the `list_panes` fallback. Consider rewording it to "WHEN listing panes or publishing".
5. `ttl_ms`/`seq` have no upper bound (`10**30` is accepted). This is harmless because it is a single argv item.

**Carry-overs still open from the slice-3b section**: `HerdrSocket(None)` path `TypeError`; no test where a socket exists and `report`/`clear` still go to the CLI (M15); no stdout size cap on CLI `list_panes`; the error-reply test and the fallback log line are not pinned (M10, M12). No `stdin=DEVNULL` test (M16).

### Regressions Introduced by the Correction
None that block. The widened `except` in `_run` (`ValueError` instead of `UnicodeDecodeError`) is a superset of the old catch. `list_panes` still maps JSON errors to `invalid_json`. The new socket deadline keeps the existing error mapping (`HerdrError` reason tokens; `OSError`/`ValueError` mapped to their type names). The only behavior change found is S2 (`timeout=None`), which is outside the declared type and has no caller. `test_relative_bin_rejected` changes the process cwd. Its cleanups run LIFO (chdir back, then rmtree), so later tests are not affected, and the full suite passes in any of the runs above.

### Verdict
PASS
W1-W5 are resolved with runtime and mutation evidence. 94/94 tests pass, each Herdr test module passes on its own, the focused work-unit command passes, and the build is clean. There are no CRITICAL or WARNING issues. Four new non-blocking suggestions (S1-S4) and the open slice-3b suggestions remain carry-overs under the single-correction rule. The slice-3a carry-over WARNING (deduplicate resolved subagent paths) is outside this slice and is still open for slice 4.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:118e19834af7e45c055c6a09d1b28a97822b536577e2f227a7faa300957e2137
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 5/5
scenarios: 6/6
test_command: python3 -m unittest discover
test_exit_code: 0
test_output_hash: sha256:945ed340975f08239b745d3d9c2bd09ec049b738f0b7868ec7abf7c2c2f05699
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 4a (tasks 4.0a, 4.0b, 4.1, 4.2, reconcile and carry-overs)

**Change**: agent-token-usage-mvp
**Mode**: Strict TDD
**Candidate**: branch `slice-4a-reconcile`, HEAD `9a060b5` (tree `3d90a90`), commits `55e8ed1` (locator dedupe), `23d6d8c` (tailer first newline), `9a060b5` (reconcile). Diff `git diff slice-3b-herdr slice-4a-reconcile`: 7 files, +202/-12.
**Evidence revision**: sha256 over `tree:3d90a903e73f2b1a2bba6d6f7059b653e47484bc\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`.
**Scope**: Slice-scoped. There are 5 requirements, each for the part this slice owns: Publish and clear (sidebar-metadata, reconcile decisions), Strict Claude resolution (session-mapping, subagent dedupe), No reliable session, no figure (session-mapping, clear and never 0), Session change and resume (session-mapping, clear or replace on a new id), and Incremental tail (usage-accounting, per-tick bound). There are 6 scenarios: Unchanged value, Pane closed, Subagents included, Missing file, New session in same pane, Growing file. End-to-end tick behavior (Herdr unreachable skips clears, persistence order) belongs to slice 4b (tasks 4.3-4.4).
**Safety**: herdr and real sockets were never used, and there was no network access. Mutations, probes and the RED replay ran only in `git archive` copies in the scratchpad, with `python3 -B`. Note: the first `compileall` run went to the repository and refreshed the gitignored `__pycache__` files there (for example `src/token_usage/domain/__pycache__/reconcile.cpython-314.pyc`). No tracked file changed, and `git status --porcelain` is empty.

### Completeness
| Metric | Value |
|---|---|
| Slice 4a tasks | 4 (4.0a, 4.0b, 4.1, 4.2) |
| Complete | 4 (`tasks.md`: Slice 4a, all `[x]`) |
| Incomplete | 0. Slice 4b tasks 4.3 and 4.4 are out of scope. |

### Build & Tests
- Tests: `python3 -m unittest discover` exited 0 and ran 111 tests, all OK. That is 94 earlier tests plus 15 reconcile tests and 2 locator tests. The tailer test was replaced, not added.
- Build: `python3 -m compileall -q src tests` exited 0 with empty output.
- Coverage: skipped because no coverage tool is installed.

### Spec Compliance Matrix
| Requirement | Scenario (slice part) | Test | Result |
|---|---|---|---|
| Publish and clear (RF04, C11) | Unchanged value: no redundant publish within TTL, refresh after it | `test_reconcile > test_unchanged_recent_value_emits_nothing`, `test_refresh_at_exactly_20s_but_not_before` | COMPLIANT (mutations R1 and R3 killed) |
| Publish and clear (RF04, C11) | Pane closed: A dropped, B unaffected | `test_reconcile > test_absent_pane_is_forgotten_without_action`; per-pane independence in `test_seq_strictly_increases_within_one_call` | COMPLIANT at unit level (R9 killed). No single test has A absent and B present (S4). |
| Strict Claude resolution (RF01, C1, C2) | Subagents included, once each, never another session's | `test_claude_locator > test_duplicate_subagent_symlink_in_same_dir_yields_one`, `test_project_dir_alias_to_same_file_is_not_ambiguous`, and the earlier attribution tests (:48, :86, :92, :101) | COMPLIANT (L2, L3 and L4 killed) |
| No reliable session, no figure (C10) | Missing file: cleared, never `0` | `test_reconcile > test_none_clears_previously_published_and_forgets`, `test_zero_total_clears_and_never_publishes_zero`, `test_unmapped_never_published_emits_nothing` | COMPLIANT (R4 and R5 killed) |
| Session change and resume (RF01, C4, C5) | New session in same pane: A's value replaced or cleared | `test_reconcile > test_session_change_same_value_publishes`; probe: a change to an empty B or to None emits `Clear` | COMPLIANT (R2 killed) |
| Incremental tail (RF03, C9) | Growing file: complete lines only, no loss, bounded per tick | `test_jsonl_tail > test_line_larger_than_read_cap_is_consumed_through_first_newline_only` and the earlier tail tests | COMPLIANT (T1 killed) |

### Correctness (Static + Probe Evidence)
| Area | Status | Notes |
|---|---|---|
| Publish on value or session change | OK | `reconcile.py:45-50` publishes unless the session and formatted value match and the age is < 20 s. Totals that format the same (1250 and 1260 are both `1.3k tokens`) do not republish, which matches "publish only when the value changes". |
| Refresh at >= 20 s | OK with a gap | `reconcile.py:46` uses `now - at < REFRESH_S`, so the boundary is exact (19.9 s keeps, 20 s refreshes). A negative age counts as fresh (W1). |
| Clear only if previously published | OK | `reconcile.py:40-43`. None or total <= 0 gives `Clear` only when `prev` exists, and the pane is never put into the new state. `0 tokens` cannot be produced, because `format_tokens` is only reached when total > 0. |
| Session changes to unmapped or None | OK | Probe: prev `{session: A}` with desired `(B, 0)` gives `[Clear]`, and with desired `None` gives `[Clear]`. With `(B, n > 0)` it gives `Publish`, which replaces A's value. |
| Absent panes forgotten | OK | The loop runs only over `desired` (`:37`). Absent panes produce no action and are left out of the new state. |
| seq | OK | `next_seq` (`:31-34`) is `max(last + 1, now_ms)` for each action. It strictly increases within a call (+1 per action) and stays monotonic when the clock goes backwards (prev seq NOW_MS+500 gives NOW_MS+501). It is unchanged when there are no actions. Missing seq defaults to 0. |
| previous not mutated | OK | Kept entries are copied (`dict(prev)`, `:48`), and `old` is only read. Mutations R11a and R11b (pop from previous, write seq back) were killed. A mutation of a prev entry on the publish path (R11c) survived (S1). |
| Published-state schema | Faithful | Reconcile returns `{"seq", "panes": {id: {"session", "value", "at"}}}`. `StateStore._write` adds `"v": 1` (`state_store.py:27`), and `_read` rejects other versions (`:49`). Probe: a previous state that includes `v` is accepted, and `v` is dropped from the result. This matches design.md:66-67 once persisted. |
| Locator, subagent dir from the resolved main | Safe | `claude_locator.py:43-46`: `main` is a realpath inside `root_real` with basename `<uuid>.jsonl`, so `main.parent` is inside the root. Each subagent is resolved again (`:49`), checked against the root, and must sit under `<session_id>/subagents/agent-*.jsonl` (`:50`). It cannot escape the root or pull subagents named for another session (L4 killed; `test_in_root_subagent_symlink_to_other_session_is_dropped` and `test_escaping_subagent_symlink_is_dropped_only` still pass). Probe: when a main symlink points to another in-root project, subagents come from the target project, and stale files under the alias project are ignored. That choice has no discriminating test (W2). |
| Locator dedupe | OK | Mains are keyed by resolved path (`:39`), so an alias is not ambiguous. Two distinct real files are still ambiguous (`test_ambiguous_across_projects_is_none_with_one_line`; L3 key-by-project killed). Subagents are deduped by resolved path (`:51`; L2 killed). |
| Tailer per-tick bound | OK | `jsonl_tail.py:50` `find` consumes only the first completed line after the `max_fragment + 1` window. Default-cap probe with a 10 MiB line followed by 40,000 lines of about 1 KiB: tick 0 gives 1 object and consumes 10.00 MiB; ticks 1 and 2 consume 4.00 MiB each; 40,001 of 40,001 objects arrive in 12 ticks, and the final offset equals the file size. That fixes the slice-2 WARNING 1. Tick 0 peaks at 46.1 MiB, which is the existing slice-2 S8 and is not new. |
| Replaced tail test proves no loss | OK | It asserts 1 object, `offset == len(big)`, and then `r2.objects == [{"a": 2}]`. |

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| Reconcile: publish on change, refresh at age >= 20 s (TTL 60 s), clear on None if previously published, forget absent panes (design.md:53) | Yes | `REFRESH_S=20`, `TTL_MS=60000` |
| `--seq` = `max(last_seq + 1, time_ns // 1e6)`, persisted (design.md:37) | Yes | Callers pass `now_ms`. Persistence is the store's job (4b). |
| Empty session: total 0 is cleared, never `0 tokens` (design.md:36) | Yes | |
| published.json schema v1 (design.md:66-67) | Yes | The store owns `v` |
| Tailer: <= 4 MiB per tick, fragments > 16 MiB skipped (design.md:57) | Yes | One oversized line (4-16 MiB) per tick is the design's own ceiling |

### TDD Compliance
| Check | Result | Details |
|---|---|---|
| TDD evidence reported | Yes | Engram #159, slice 4a table (4 rows) |
| RED confirmed | Yes (replayed) | The slice-4a tests run over the `slice-3b-herdr` src gave `Ran 25`, `FAILED (failures=3, errors=1)`. The failures are the 2 new locator tests and the replaced tail test, and the error is the `test_reconcile` ImportError. This matches the reported RED exactly. |
| GREEN confirmed | Yes | 111/111 |
| Triangulation | Yes | Reconcile has 15 cases covering every rule plus the boundaries (19.9 s and 20 s, 0 and -5, clock backwards for seq) |
| Safety net | Yes | The locator and tailer files were modified with their earlier tests kept. `reconcile.py` and `test_reconcile.py` are new. |

### Test Layer Distribution
| Layer | Tests | Files |
|---|---|---|
| Unit (pure) | 15 | `tests/unit/test_reconcile.py` |
| Adapter (tempdir) | 3 changed or added | `test_claude_locator.py`, `test_jsonl_tail.py` |

### Mutation Summary (scratch copy, `python3 -B`, per test module)
Killed: R1 `<` to `<=`, R2 no session compare, R3 no value compare, R4 `<= 0` to `< 0`, R5 always clear, R6 seq = now_ms, R7 seq = last + 1, R8 keep cleared pane, R9 keep absent panes, R11a pop from previous, R11b write seq into previous, R12 `at` not refreshed, L2 no subagent dedupe, L3 key mains by project, L4 drop the subagent parent-name check, T1 `find` back to `rfind`.
Survived: L1 `project = mains[main]` (the unresolved project dir; W2), R11c mutating a prev entry on the publish path (S1), R10 returning `prev` without a copy (aliasing only; S1), R13 unsorted iteration (equivalent for the test inputs; ordering is not a requirement).

### Issues Found
**CRITICAL**: None

**WARNING**:
1. (W1) A negative age suppresses the TTL refresh. `reconcile.py:45-46` keeps an entry whenever `now - at < 20`, and that includes `now < at`. Probe: with `at=2000` and `now` set to 1990, 1900 or 1000, the result is `[]`. `at` is persisted in published.json (design.md:67). After a backwards wall-clock step, or if 4b passes a monotonic clock that resets on reboot, no refresh is sent until `now >= at + 20`. Meanwhile the 60 s TTL expires in Herdr and the figure disappears for that long. seq handles the clock going backwards explicitly, but `at` does not. Fix: treat a negative age as stale (`not 0 <= now - at < REFRESH_S`) and add a test.
2. (W2) The resolved-main subagent directory is untested. `claude_locator.py:44` (`project = main.parent`) is the key 4.0a decision, but mutation L1 (`project = mains[main]`, the first unresolved project dir) passes every test. Probe: when `-proj/<A>.jsonl` is a symlink to `-real/<A>.jsonl`, the code returns `-real/<A>/subagents/*` and ignores `-proj/<A>/subagents/*`. Under L1 the result is the reverse. Both stay attribution-safe because the session-id filter holds, but the chosen behavior is not covered by a test. Add a test with a main symlink to another in-root project that has subagents.

**SUGGESTION**:
1. `test_previous_state_is_not_mutated` covers only the Clear path. Also check the publish and refresh paths (R11c survived), and assert that the returned entries are not the objects in `previous` (R10).
2. tasks.md 4.1 says "clear on None/close/session change". Closed panes are forgotten without a `Clear` (design.md:53), which is correct because the pane no longer exists. Align the task wording.
3. For slice 4b: reconcile returns a state that assumes every action succeeded. TickService should persist the new published state only for actions that were applied, and must skip reconcile entirely when Herdr is unreachable (spec case "Herdr unreachable skips clears").
4. Add an explicit Pane closed test with A absent and B present and unchanged, asserting that B produces no action and keeps its entry.
5. Still open from slice 2 (S8): an oversized-line tick buffers up to 16 MiB + 1 (46.1 MiB peak measured with a 10 MiB line).

### Prior Findings Addressed
| Finding | Status |
|---|---|
| Slice-2 re-verify WARNING 1 (fragment branch consumed past the oversized line) | RESOLVED by 23d6d8c (probe above) |
| Slice-3a re-verify WARNING 1 (duplicate subagent paths) | RESOLVED by 55e8ed1 |
| Slice-3a S-b (an in-root alias made the result ambiguous) | RESOLVED by 55e8ed1 |

### Verdict
PASS WITH WARNINGS
111/111 tests pass and the build is clean. All 4 slice-4a tasks are done, with RED replayed and matching the reported evidence. Reconcile implements publish on change, refresh at >= 20 s, clear only when previously published, never `0`, forgetting absent panes, and a monotonic seq. The locator dedupe stays inside the root and attribution-safe, and the tailer bound holds with no data loss. Two warnings remain: a negative age blocks the TTL refresh, and the resolved-main subagent directory has no discriminating test.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:0a7fb01978cd278208256532f52b0e52dbbc1ec32e9cd44c28f225f9abd3d7ae
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 8/8
scenarios: 12/12
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:31f03259d0b8c254a98c7e1df1b92a552f3e6293625eee42df0ab3a2bf03d436
build_command: python3 -B -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 4b (tasks 4.3, 4.4, 4.5, TickService and carry-overs)

**Change**: agent-token-usage-mvp
**Mode**: Strict TDD
**Candidate**: branch `slice-4b-tick`, HEAD `620e97b` (tree `00090e8`), commits `2468845` (reconcile negative age), `f65e9e9` (locator pin test), `620e97b` (TickService and scenarios). Diff `git diff slice-4a-reconcile slice-4b-tick`: 8 files, +359/-4.
**Evidence revision**: sha256 over `tree:00090e89b0ad0d5f1c77373af7e109c89f712235\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`. The test output contains a timing line, so its hash is not reproducible byte for byte.
**Scope**: Slice-scoped, following the slice 4a convention. There are 8 requirements: Strict Claude resolution, No reliable session no figure, Codex panes unmapped, and Session change and resume (session-mapping); Publish and clear (sidebar-metadata); Fault isolation, and Least privilege and safe logging (plugin-lifecycle); Incremental tail (usage-accounting). There are 12 scenarios: Same repo two sessions, Subagents included, Missing file, Codex pane, New session in same pane, Resume after restart, Unchanged value, Pane closed, Herdr unreachable, Corrupt transcript, Content never stored, Growing file. Out of scope: Handoff, Stale pidfile, No connectivity, Stop (slice 5); Uninstall, Custom sidebar (slice 6); Pruning (state store slice 2, wiring slice 5). The full spec set has 17 requirements and 26 scenarios.
**Safety**: herdr, real sockets, real `~/.claude` and the network were never used. Tests, mutations, probes and RED replays ran only in a `git archive` copy in the scratchpad, with `python3 -B`. `compileall` also ran only in the scratch copy. Repository `git status --porcelain` is empty.

### Completeness
| Metric | Value |
|---|---|
| Slice 4b tasks | 3 (4.3, 4.4, 4.5) |
| Complete | 3 (`tasks.md` Slice 4b, all `[x]`) |
| Incomplete | 0. Slices 5 and 6 are out of scope. |

### Build & Tests
- Tests: `python3 -B -m unittest discover` exited 0. Ran 127 tests, OK (111 earlier, plus 1 reconcile, 1 locator and 14 tick scenarios).
- Build: `python3 -B -m compileall -q src tests` exited 0 with empty output.
- Coverage: skipped because no coverage tool is installed.

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Strict Claude resolution | Same repo, two sessions | `test_tick > test_two_sessions_in_two_panes_have_independent_totals` | COMPLIANT (M13 cross-attribution killed) |
| Strict Claude resolution | Subagents included | `test_claude_locator > test_subagents_are_included_and_other_sessions_are_not`, `test_subagents_are_read_next_to_the_resolved_main` | COMPLIANT at resolution level. The tick-level aggregation has no test (W2, M5 and M9 survived); probe P1 confirmed the behavior. |
| No reliable session, no figure | Missing file | `test_tick > test_empty_or_missing_session_shows_nothing` | COMPLIANT (M12 killed). The diagnostic `locate_failed` is emitted (probe) but not asserted. |
| Codex panes unmapped | Codex pane | `test_tick > test_codex_unmapped_and_malformed_panes_publish_nothing` | COMPLIANT |
| Session change and resume | New session in same pane | `test_tick > test_session_change_in_same_pane_starts_from_new_usage`; `test_reconcile` session change tests | COMPLIANT. Probe P5: A then a B with no transcript gives `clear`. |
| Session change and resume | Resume after restart | `test_tick > test_resume_after_restart_does_not_double_count` | COMPLIANT on the observable total. The test does not prove the persisted counter is used (M10 survived; W2). |
| Publish and clear | Unchanged value | `test_tick > test_unchanged_value_refreshes_only_after_20s_with_ttl`, `test_reconcile > test_negative_age_counts_as_stale_and_refreshes` | COMPLIANT (M8 wrong TTL and M20 killed) |
| Publish and clear | Pane closed | `test_tick > test_closed_pane_is_forgotten_and_other_is_unaffected` | COMPLIANT (this also closes 4a S4) |
| Publish and clear | Herdr unreachable | `test_tick > test_herdr_unreachable_changes_nothing`, `test_failed_publish_is_not_recorded_and_is_retried`, `test_failed_clear_keeps_record_for_retry`; CLI fallback in `test_herdr_fallback` (slice 3) | COMPLIANT (M2, M3 and M11 killed) |
| Fault isolation | Corrupt transcript | `test_tick > test_corrupt_session_is_skipped_and_other_is_published` | COMPLIANT for a raising adapter (M1 killed). The real `JsonlTail` never raises on an unreadable file (W1). |
| Least privilege and safe logging | Content never stored | `test_tick > test_content_and_paths_never_reach_state_or_logs` | COMPLIANT. Probe P6 also scanned for the temp root path and the project slug and found no hits. |
| Incremental tail | Growing file | `test_tick > test_total_grows_after_new_lines`; tailer tests (slice 2) | COMPLIANT on the total. Reading only new bytes is not pinned at tick level (M15 survived; W2). Probe P2: an idle tick reads 0 bytes, and a growth tick reads only the 147 new bytes. |

**Compliance summary**: 12/12 scenarios have a passing covering test. 4 of them have tick-level gaps, reported as W2.

### Correctness (Static + Probe Evidence)
| Area | Status | Notes |
|---|---|---|
| Pane-to-session mapping each tick | OK | `tick.py:28-30` rebuilds the map from `list_panes` on every tick. It uses `claude_session_id` only, and cwd is never read. |
| Shared session across two panes | OK | `tick.py:31` computes each distinct session once. Probe P1: two panes on A both get `1.5k tokens`, from 2 reads (main plus 1 subagent). B's subagent is excluded. |
| Never show 0 | OK | A total of 0 still reaches `desired`, and `reconcile.py:39` turns `<= 0` into Clear or nothing. M12 was killed. |
| Herdr unreachable | OK | `tick.py:22-26` returns before any state read or write. M11 was killed. |
| Failed action not persisted | OK | `tick.py:44-49` restores the old record or drops a new one. A failed refresh keeps the old `at`, so it is still stale and is retried. A failed session change keeps the old session, so it is retried. seq still advances, which is harmless. |
| Per-session isolation | OK | `tick.py:53-59` catches per session and logs the exception type and an 8-character session prefix. |
| seq | OK | `tick.py:36` passes `int(now*1000)`, and the last seq is reloaded from `published.json`. Probe P4: seqs 1016002, 1016003, 1016004 with a constant clock, and the third came after a restart with the clock moved back 1 h. |
| File keys | OK | `main` and `subagents/agent-*.jsonl` (`tick.py:70-71`). The store rejects absolute keys (`state_store.py:15-19`), which is why M4 was killed. Probe P1 state keys: `main`, `subagents/agent-x.jsonl`. |
| Truncation and rotation | OK | Probe P3: a truncate and rewrite with known ids publishes nothing, and a rotation to a new inode with copied history plus 1 new id gives `2.0k` (the new id only). |
| Unreadable transcript | Deviation | Probe P7: after `chmod 000` on A's main, which had persisted state, the tick keeps publishing `1.2k tokens` and logs no diagnostic. `JsonlTail.read` swallows `OSError` (`jsonl_tail.py:26-30`), and `_read_session` returns the persisted ledger total (`tick.py:86`). (W1) |
| Logging | OK | Events: `tick`, `session_failed`, `apply_failed`, `herdr_unreachable`, `locate_failed`. They carry the exception type, counts and an 8-character prefix only. `locate_failed` repeats every tick (S1). |
| Large first scan | Note | Probe P8: a 10.3 MiB transcript publishes `116.5k`, then `232.7k`, then `300.0k` over 3 ticks, because of the 4 MiB per-tick bound. Interim undercounts are visible for a few ticks (S4). |

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| Data Flow: list fails, skip tick, no clears | Yes | |
| Data Flow order: report/clear, then published.json, then save dirty sessions | Deviation (benign) | Sessions are saved inside `_read_session` (`tick.py:81-85`), before reconcile and apply. This is safe because totals are recomputed from the ledger. |
| State Schema v1 sessions | Drift | `aliases` is added (`tick.py:84`) and `last_seen` is a float. Neither is in design.md:63-64 (W3). |
| last_seen and 30-day prune | Partial | `last_seen` updates only when the session is dirty. An open but idle session can be pruned and then rescanned (S5). |
| File keys relative, no absolute paths | Yes | |
| Logs: type, counts, pane id, 8-character prefix | Yes | |
| Tailer per-file `{inode, dev, size, offset}` | Yes | `skip` is an extra internal flag from slice 2. |
| TTL 60 s, refresh at 20 s | Yes | `TTL_MS` is passed through (`tick.py:43`) |

### TDD Compliance
| Check | Result | Details |
|---|---|---|
| TDD evidence reported | Yes | Engram #159, slice 4b table |
| RED confirmed | Replayed, but after the fact | The no-op stub over the 14 tick tests gives `FAILED (failures=11)`, which matches the report. Of the 3 that pass under the stub, `herdr_unreachable` and `empty_or_missing` assert only the absence of actions, and `content_never_stored` scans files that do not exist yet. They are guarded by companion non-empty tests. W1 RED replayed: the 4a `reconcile.py` fails the new test (1 failure). |
| Test-first order | Not followed for 4.3/4.4 | Apply admitted `tick.py` was written before the tests. Both are in one commit (`620e97b`). RED was reconstructed against a stub (W4). |
| GREEN confirmed | Yes | 127/127 |
| Triangulation | Partial | 14 scenarios with distinct expected values. Subagent, alias and persistence paths are not exercised at tick level (W2). |
| Safety net | Yes | reconcile and locator tests were kept, and the tick files are new |

### Test Layer Distribution
| Layer | Tests | Files |
|---|---|---|
| Unit | 1 added | `tests/unit/test_reconcile.py` |
| Adapter (tempdir) | 1 added | `tests/adapters/test_claude_locator.py` |
| Scenario (real adapters plus fake Herdr and clock) | 14 | `tests/scenarios/test_tick.py` |

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|---|---|---|---|---|
| `tests/scenarios/test_tick.py` | 123 | `assertEqual(self.take(), [])` after a restart | Passes even if session state is never persisted (M10), because the transcript is fully re-read | WARNING (W2) |
| `tests/scenarios/test_tick.py` | 245 | Loop over state and log files | Not a ghost loop: the files exist after the tick (published.json, the session file and the log) | OK |

### Mutation Summary (scratch copy, full suite, `python3 -B`)
Killed (11): M1 drop the per-session try, M2 persist failed actions, M3 drop the old record on a failed clear, M4 absolute main key, M8 TTL 20000, M11 continue after a list failure, M12 publish a 0 total, M13 cross-session total, M14 no ledger restore, M19 no save_published, M20 trust a negative age.
Survived (9): M5 absolute subagent keys, M9 skip subagents, M6 do not persist aliases, M7 do not load aliases, M10 never save the session, M15 ignore stored positions (re-read the whole file every tick), M16 drop `last_seen` (the session would then never be pruned, because `state_store.py:75` defaults to `now`), M17 ignore the persisted seq, M18 log the full session id.

### Issues Found
**CRITICAL**: None

**WARNING**:
1. (W1) An unreadable transcript keeps showing its last persisted total, and no diagnostic is logged. spec session-mapping "No reliable session, no figure" says that when the file is inaccessible the pane MUST show nothing and log a diagnostic. `jsonl_tail.py:26-30` returns an empty result on `OSError`, and `tick.py:74-86` then returns the persisted ledger total. Probe P7 (`chmod 000` after the first tick) keeps refreshing `1.2k tokens`. It is the session's own value, so nothing is misattributed. The Corrupt transcript test passes only through a raising fake tailer (`test_tick.py:59-67`). Fix: have the tailer signal an unreadable file (raise, or set a flag), let `_session_total` return None and log `session_failed`, and add a test with a real `chmod 000` file.
2. (W2) The tick-level wiring for subagents, aliases, session persistence, stored positions, seq and `last_seen` is not pinned by tests. M5, M6, M7, M9, M10, M15, M16 and M17 all survive. Probes P1-P4 show the current behavior is correct, but a regression would pass CI. In particular, Resume after restart (`test_tick.py:115-126`) passes even with no session persistence at all. Add tick tests for: a subagent counted under its parent with a relative key; a requestId-only line after a restart; no re-read across ticks (a counting tailer, or the persisted offset); seq strictly greater after a restart with the clock moved back; `last_seen` present.
3. (W3) Design doc drift: the session state adds `aliases` (requestId mapped to message id, `tick.py:84`), which is needed for idempotence across restarts, and `last_seen` is a float. Neither appears in the State Schema (design.md:62-64). The save order also differs from the Data Flow diagram. Update design.md, in slice 6 at the latest.
4. (W4) Strict TDD order was not followed for 4.3/4.4. The implementation was written before the tests, in a single commit, and RED was reconstructed afterwards against a stub. The replay matches the report (11 failures), so the evidence is honest, but it was not test-first.

**SUGGESTION**:
1. (S1) `locate_failed` is logged on every tick for each missing or ambiguous session (`claude_locator.py:41`). At a 4 s interval that is about 21,600 lines per day, which pushes older diagnostics out of the 512 KiB log budget. Log on state transitions only.
2. (S2) Performance: every tick re-runs the locator (an `iterdir` over all project dirs, `claude_locator.py:33`), and reloads and parses the full session JSON and ledger (`tick.py:65-69`). Cache per session in memory and reload from the store only at startup.
3. (S3) An exception from `save_published` propagates out of `tick()` (`tick.py:50`), so the slice 5 loop must catch it. A failing `save_session` turns into `session_failed` and clears a figure that is known. Consider keeping the total and only logging.
4. (S4) The first scan of a transcript over 4 MiB publishes growing undercounts for a few ticks (P8). Consider withholding the publish until `offset == size`, or draining within a per-tick byte budget.
5. (S5) `last_seen` changes only on dirty ticks, so a pane that stays open and idle for more than 30 days is pruned and rescanned. Bump `last_seen` at most once a day while the session is mapped, or document the behavior.
6. (S6) Session state with `v: 1` but the wrong shape (for example `ledger` as a list) fails every tick, because `tick.py:66-69` never rewrites it. Treat shape errors as a rebuild.

### Prior Findings Addressed
| Finding | Status |
|---|---|
| 4a W1: a negative age suppressed the refresh | RESOLVED by 2468845 (`reconcile.py:46`; the test fails on the 4a code) |
| 4a W2: the resolved-main subagent dir was untested | RESOLVED by f65e9e9 (`test_claude_locator.py:48-56`) |
| 4a S2: task 4.1 wording | RESOLVED (tasks.md) |
| 4a S3: persist only applied actions, skip when Herdr is unreachable | RESOLVED (`tick.py:22-26`, `:44-49`; M2, M3 and M11 killed) |
| 4a S4: explicit Pane closed test | RESOLVED (`test_tick.py:214-223`) |
| 4a S1 (reconcile previous mutation on the publish path), slice 2 S8 (oversized-line peak memory) | Still open |

### Verdict
PASS WITH WARNINGS
127/127 tests pass and the build is clean. All 3 slice 4b tasks are done, and all 12 in-scope scenarios have passing tests. Attribution is safe: the map is rebuilt per tick, each session is read once, and other sessions' subagents are excluded. A 0 is never shown, Herdr failures change nothing, and failed actions are retried. Four warnings remain: an inaccessible transcript still shows its stale total, the tick wiring has test gaps (9 mutations survived), the session schema has drifted from the design, and the test-first order was not followed.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:cb5b74a13fb93ddc9e6d9a1445642b9db452fb1534005d71b79379d91a528d14
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 8/8
scenarios: 12/12
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:807b4ed23553f57f8409a2b497588ae2a9a74e043cb935621ae52e20bd7b020d
build_command: python3 -B -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Slice 4b Re-verification (bounded correction 43cf743)

**Change**: agent-token-usage-mvp
**Mode**: Strict TDD
**Candidate**: branch `slice-4b-tick`, HEAD `43cf743` (tree `2f7262c`), on `96bd1c1`. Diff `git diff 96bd1c1 43cf743`: 6 files, +133/-7 (`claude_locator.py`, `jsonl_tail.py`, `app/tick.py`, `ports.py`, `test_claude_locator.py`, `test_tick.py`).
**Scope**: Confirms the in-scope slice 4b findings (W1, W2, S1, S3) and looks only for regressions introduced by the correction. W3 (design doc drift, moved to slice 6) and W4 (TDD order, historical) are not part of this correction and stay open. Under the single-correction rule, new non-critical observations are carry-overs. Envelope counts are unchanged from the slice 4b section: 8 requirements and 12 scenarios.
**Evidence revision**: sha256 over `tree:2f7262c5c9b4d37c631f81a156c49e53e274a2f1\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`. The test output contains a wall-clock duration, so its hash is specific to this run.
**Safety**: herdr, real sockets, real `~/.claude` and the network were never used. Tests, `compileall`, mutations and probes ran only in a `git archive 43cf743` copy in the scratchpad, with `python3 -B`. The repository was not modified (`git status --porcelain` is empty).

### Build & Tests
- Tests: `python3 -B -m unittest discover` exited 0. It ran 131 tests, all OK (127 earlier plus 3 tick scenarios and 1 locator test).
- Build: `python3 -B -m compileall -q src tests` exited 0 with empty output (scratch copy only).
- Coverage: skipped because no coverage tool is installed.
- Tasks: Slice 4b tasks 4.3, 4.4 and 4.5 remain `[x]` in `tasks.md:70-72`. The correction adds no task.

### Prior Findings
| Finding | Status | Evidence |
|---|---|---|
| W1: unreadable transcript kept its stale total, with no diagnostic | RESOLVED | `jsonl_tail.py:18,31` sets `TailResult.failed=True` when stat or open raises `OSError`, and leaves the position unchanged. `ports.py:23` declares `failed`. `tick.py:78-80` returns None for the whole session when any file (main or subagent) fails, and logs `transcript_unreadable session=<8 chars>`. Test `test_tick.py:190` uses the real `JsonlTail` and `chmod 0` on the main and then on a subagent. It asserts a `clear`, an empty published state, recovery to `1.5k tokens`, 2 diagnostic lines, and no full id or project slug in the log. Independent probe with the real tailer: chmod 0 on the main gives `clear p1` while B keeps publishing. It stays blank 30 s later. After restore plus growth it gives `3.0k` with no double count. chmod 0 on 1 of 2 subagents gives `clear p1`, and restore gives `3.0k`. A session unreadable from its first tick publishes nothing. The log has no full ids and no paths. Mutations N1-N5 and N13 (flag ignored, main only, subagents only, tailer never flags, log removed, `break` that keeps the persisted total) are all KILLED. |
| W2: tick wiring mutations survived | RESOLVED | Re-run on 43cf743 with the full suite. M5 (absolute subagent key), M9 (skip subagents), M6 (aliases not persisted), M7 (aliases not loaded), M10 (session never saved), M15 (stored positions ignored), M16 (`last_seen` dropped), M17 (persisted seq ignored) are KILLED by `test_session_state_wiring_survives_restart` (`test_tick.py:222`). M18 (full session id in logs) is KILLED in both places: `session_failed` by `test_tick.py:186` and `transcript_unreadable` by `test_tick.py:190`. 9/9 killed. |
| S1: `locate_failed` logged every tick | RESOLVED | `claude_locator.py:22,42-47` logs only when the reason for that session changes, and success clears the entry. Test `test_claude_locator.py:75` checks 3 calls give 1 line, and missing, found, then missing again gives 2 lines. N10 (always log) and N11 (no reset on success) are KILLED. |
| S3: save exceptions escaped `tick()` | RESOLVED | `tick.py:50-53` catches the `save_published` failure and logs `save_published_failed`. `tick.py:87-94` catches the `save_session` failure, logs `save_session_failed`, and still returns the total. Test `test_tick.py:212` checks that both failures still publish and log the error type. N6-N9 (narrowed `except`, log removed) are KILLED. |

### Mutation Summary (scratch copy, full suite, `python3 -B`)
Killed (22): M5, M6, M7, M9, M10, M15, M16, M17, M18a, M18b, N1-N11, N13.
Survived (1): N12, which logs only the first failure reason per session (`if session_id not in self._last_failure`). A change from missing to ambiguous without a success in between is not tested (S3 below).

### Issues Found
**CRITICAL**: None

**WARNING**: None new. W1 and W2 are resolved. W3 (design doc drift, `design.md:62-64`, planned for slice 6) and W4 (test-first order for 4.3/4.4, historical) are still open from the slice 4b section and were not in this correction's scope.

**SUGGESTION** (new, from the correction; carry-over under the single-correction rule):
1. (S1) `transcript_unreadable` is logged on every tick while a file stays unreadable (`tick.py:79`). Probe: one line per tick, the same pattern the locator fix removed. Apply the same "log on change" approach as in the locator.
2. (S2) `ClaudeLocator._last_failure` (`claude_locator.py:22`) only shrinks when a session is found again. Ids that never resolve stay forever. Probe: 10,000 distinct failing UUIDs use about 958 KiB (about 96 B each). Keys are validated UUIDs (`claude_locator.py:29`), so each entry is bounded, and the realistic growth is a few failing sessions per day. That is negligible, but there are two side effects: the map is unbounded over the daemon lifetime, and a session that closes and later returns still missing is not logged again. Consider removing entries for sessions that are not in the current tick, or capping the map.
3. (S3) No test covers a change of reason from missing to ambiguous (N12 survived). Add an assertion for it to `test_claude_locator.py:75`.
4. (S4) The W1 test is skipped when running as root (`test_tick.py:189`, `skipIf(os.geteuid() == 0)`). In a root CI container the tailer `failed` flag (N4) would lose its only killing test. Add a root-safe variant, for example a directory at the transcript path (`IsADirectoryError`) or a file deleted between locate and read.
5. (S5) Persistent save failures log on every tick, and with `save_session` failing the stored offsets never advance. Each tick then re-reads all bytes since the last good save. This is idempotent, because the ledger deduplicates, but the cost grows. A file that vanishes between locate and read now blanks the whole session for one tick. That matches the spec ("inaccessible, show nothing") but can flicker on rotation.

### Regressions Introduced by the Correction
None that block. The early `return None` discards that tick's parsed objects and does not save positions, so the next readable tick re-reads from the last saved offsets with no loss or double count (probe P4: `3.0k`). The `failed` field defaults to `False`, so other `TailResult` producers keep their behavior. A read error after `open` (`fh.read` `OSError`) still propagates to `session_failed` (`tick.py:61`), which is also None. When `save_session` fails, the total is still returned. Before the correction it became `session_failed` and was cleared. This is the intended S3 change.

### Verdict
PASS WITH WARNINGS
131/131 tests pass and the build is clean. W1, W2, S1 and S3 are resolved with runtime, probe and mutation evidence (22 of 23 mutations killed, all in-scope ones included). There are no CRITICAL issues and no new warnings. The out-of-scope slice 4b warnings W3 and W4 remain open, and five new suggestions are carried over.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:924e0e047d4145928781c86df46035387333688ab07d90a5e21ec64b340cb911
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 2/2
scenarios: 4/4
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:d0d002bc605c8f26b22ba5f5e5c48f3753825ba6c09dd37159cc60c026d1e23e
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 5 (lifecycle, tasks 5.1-5.3)

**Change**: agent-token-usage-mvp
**Candidate**: branch `slice-5-lifecycle`, HEAD `d191cf1` (tree `03f6891`), diff `git diff slice-4b-tick slice-5-lifecycle`: 12 files, +599/-6 (over the 400-line budget; overage accepted by the user). Commits 35e7177 (daemon + main), 3740c5b (manifest), d191cf1 (tick carry-overs).
**Mode**: Strict TDD
**Scope**: plugin-lifecycle requirements delivered by this slice: "Single detached poller" (3 scenarios) and "Stop and status actions" (1 scenario) = 2 requirements / 4 scenarios. "Fault isolation" and "Least privilege" were verified in slices 2-4b; "Uninstall and documentation" belongs to slice 6. The full change has 17 requirements / 26 scenarios.
**Evidence revision**: sha256 over `tree:03f689184e41c161706f684faab8af5aa92c56a1\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`. Tests and build ran in git-archive copies under the scratchpad (repo untouched; no compileall in repo).

### Completeness
| Metric | Value |
|--------|-------|
| Slice 5 tasks total | 4 (5.1, 5.2, 5.3, 5.3a) |
| Tasks complete | 3 |
| Tasks incomplete | 1: 5.3a [APPROVAL] `herdr plugin link/enable` (user-owned, intentionally not run) |

### Build & Tests Execution
**Build**: Passed. `python3 -m compileall -q src tests` (archive copy), exit 0, empty output.
**Tests**: 151 passed, 0 failed, 0 skipped. `python3 -B -m unittest discover` (archive copy), exit 0, Python 3.14.8. `pgrep -fl "src/main.py"` empty after the suite.
**Coverage**: Not available (no coverage tool).

### Spec Compliance Matrix (slice 5 scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Single detached poller | Handoff re-run | `test_daemon.py > TestRun.test_second_run_exits_zero_without_ticking`, `TestStart.test_live_same_socket_is_noop` | COMPLIANT |
| Single detached poller | Stale pidfile | `TestRun.test_stale_pidfile_replaced`, `TestStart.test_stale_pidfile_spawns` | COMPLIANT |
| Single detached poller | No connectivity (C13) | `TestRealSpawn.test_start_status_stop_and_missing_env` (real offline daemon, nonexistent socket, fake bin, ticks) + slice 4b `test_tick.py` publishing scenarios | COMPLIANT (composite; no single e2e publishes through the real daemon) |
| Stop and status actions | Stop | `TestRun.test_stop_clears_published_persists_and_removes_pidfile` + `TestRealSpawn` (real SIGTERM, exit, pidfile removed) | COMPLIANT (see W1: "only the pidfile process" holds only outside a race window) |

**Compliance summary**: 4/4 scenarios compliant.

### Correctness (Static + runtime evidence)
| Area | Status | Notes |
|------|--------|-------|
| flock held for life | OK | `daemon.py:84-92` lock fd kept until `finally`; mutation M16 (drop lock) killed. fd is non-inheritable (PEP 446) and Popen uses `close_fds=True`, so neither herdr CLI children nor the spawned daemon inherit it. |
| Two concurrent `start`s | OK | Both may spawn; the loser's `run` fails `LOCK_NB` and exits 0. |
| Probe lock race | Risk | `is_running` (`daemon.py:39-44`) briefly takes the same exclusive lock; a daemon whose `run` hits that window exits 0 silently (W5). |
| Handoff socket compare | OK | `daemon.py:163-168`; M6 killed. |
| SIGTERM target verification | Risk | `_terminate` (`daemon.py:149-156`) signals the pidfile pid whenever *anyone* holds the lock; no check that the holder is that pid (W1, reproduced). |
| Spawn | OK | `[sys.executable, main.py, "run"]`, no shell, `start_new_session`, `close_fds`, DEVNULL stdio (`daemon.py:169-170`); M10 killed. |
| Signals/shutdown | OK | SIGTERM/SIGINT set an Event that also wakes the sleep; cleanup clears (best effort), persists, removes pidfile; SIGHUP ignored (`daemon.py:78-81, 126-137`). SIGHUP and SIGINT untested (M3, M15 survived). |
| Loop resilience | OK | tick/prune/pidfile failures contained (`daemon.py:105-121`). |
| Orphan guard 5 min | OK | `ORPHAN_S = 300`; M8/M9 killed. |
| Prune at startup + hourly | Implemented, untested | `daemon.py:102-103`; M1/M2 survived (W3). |
| status privacy | OK | pid, HH:MM:SSZ, pane count only; M18 killed. |
| main.py env validation | Partial | Missing env -> exit 2, no traceback (tested). Invalid/unwritable state dir and Python < 3.10 still produce tracebacks with absolute paths (W4). |
| Manifest | OK vs explore.md | id/name/version/min_herdr_version, `[[startup]]`, `[[actions]]`, argv lists, no `build`. `python3` PATH resolution, cwd = plugin root, and the `[[actions]]` `id`/`title` keys are unverified (W2). |
| tick() bool deviation | Accepted | `tick.py:22` returns False only when `list_panes` fails; daemon treats `None` as reachable (`is not False`). Tested (M14 killed). Design text still describes `tick()` without a return value. |
| Locator cap | OK | Evicts oldest insertion at 1024 (`claude_locator.py:47-48`); M13 killed. Test reads private `_last_failure`. |
| Log/state privacy | OK | Daemon logs event names and exception types only; pidfile stores `socket_path` as designed. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Duplicate guard (flock for life, pidfile informational) | Partly | Lock is correct, but stop/handoff trust the informational pidfile as kill target, so the "immune to PID reuse" claim does not fully hold (W1). |
| Handoff (compare socket_path, SIGTERM, wait <=5 s, respawn) | Yes | Wait is bounded but can be shorter than the old daemon's cleanup (W6). |
| Spawn | Yes | Exactly as designed. |
| Lifecycle (stop flag, clear, persist, rm pidfile, SIGHUP ignored, orphan 5 min, status) | Yes | |
| Security boundaries (argv only, writes only in state dir) | Yes, minor | Interpreter writes `__pycache__` under the plugin `src/` (S1). |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Yes | apply-progress #159, compact RED/GREEN table |
| All tasks have tests | Yes | 5.1/5.2 test_daemon.py (14), 5.3 test_manifest.py (3), carry-overs in test_tick.py / test_claude_locator.py |
| RED confirmed | Partial | RED reasons recorded; tick bool RED not isolated (self-reported) |
| GREEN confirmed | Yes | All listed tests pass now |
| Triangulation | Adequate | Orphan guard (threshold + reset), start (started/running/restarted/failed) |
| Safety net for modified files | Not reported | Table lacks SAFETY NET/TRIANGULATE columns (W7) |

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit/adapter | 16 new/changed lifecycle + 3 carry-over | 4 | unittest |
| Integration (real subprocess daemon) | 1 | test_daemon.py | unittest + subprocess |
| E2E | 0 | - | not installed |

### Mutation Testing (20 mutants, archive copy)
Killed (13): M4 SIGTERM handler removed, M6 handoff compare, M7 pidfile unlink, M8 orphan `>`, M9 orphan reset, M10 start_new_session, M11 stop without terminate, M12 unreadable discard, M13 locator cap, M14 tick always True, M16 lock not held, M18 status leaks socket, M19 wait 0 s.
Survived (7): M1 no prune, M2 prune only at startup, M3 SIGHUP not ignored, M5 `pid > 1` guard removed (a pidfile with pid 0/-1 would signal the process group/all processes), M15 SIGINT not handled, M17 `start` without HERDR_BIN_PATH check, M20 `run` build exceptions unguarded.

### Runtime Experiments (scratch, temp HOME/state, fake HERDR_BIN_PATH, nonexistent sockets; all processes killed)
- E1 (W1): stale pidfile with the pid of an unrelated `sleep 60` process, lock held by another fd (simulating a concurrent `status`/`start` probe or a new daemon before it writes its pidfile). `daemon.stop()` sent SIGTERM to the unrelated process (returncode -15).
- E2 (W6): real daemon, 4 published panes, fake herdr taking 1.9 s per call. Handoff `start` with a new socket returned `failed` (rc 1) after 5.1 s; once the old daemon finished cleanup, `status` reported `stopped`: no poller runs after the handoff.
- E3 (W4): `HERDR_PLUGIN_STATE_DIR=/nonexistent_root_dir/x main.py status` -> traceback (`OSError: [Errno 30] Read-only file system`).
- E4 (W2/W4): `/usr/bin/python3` is 3.9.6 on this machine; `main.py` under it dies at import with a traceback (`dict[str, str] | None`). With cwd `/`, `python3 src/main.py` cannot open the script.

### Issues Found
**CRITICAL**: None.

**WARNING**:
- W1 `src/token_usage/lifecycle/daemon.py:149-156` (`_terminate`, used by `stop` and handoff): SIGTERM goes to the pidfile pid whenever the lock is held by anyone. A stale pidfile (daemon SIGKILLed/crashed) combined with a lock held by a probe (`is_running` from a concurrent `status`/`start`) or by a fresh daemon before `_write_pidfile` (`daemon.py:84-89`) signals an unrelated, possibly PID-reused process. Reproduced (E1). Narrow window, but it contradicts the design rationale "immune to stale pids and PID reuse" and the focus "SIGTERM only to our verified daemon". Options: verify the holder (e.g. POSIX `lockf`/F_GETLK holder pid, or record pid inside the lock file and have probes use a separate lock), or verify `started_at` vs the process start time before signalling.
- W2 `herdr-plugin.toml:11,16,21,26`: commands rely on `python3` from Herdr's PATH and cwd = plugin root; neither is verified (`herdr plugin --help` does not document it; explore.md shows only the reference `["python3", "src/main.py"]`). `/usr/bin/python3` here is 3.9.6, which fails at import (E4). `[[actions]]` `id`/`title` keys are not documented in explore.md. Confirm at 5.3a (user-owned link/enable) via `herdr plugin log`.
- W3 Prune at startup + hourly (`daemon.py:102-103`) has no test (M1, M2 survived). SIGHUP-ignore and SIGINT (`daemon.py:80-81`, M3, M15) and the `pid > 1` safety guard (`daemon.py:151`, M5) are also untested.
- W4 `src/main.py:52-67`: env validation covers only missing variables. Invalid/unwritable state dir (E3), Python < 3.10 (E4) and any exception inside `start`/`stop`/`status` print a traceback with absolute paths to the plugin log. `start` with a non-absolute/non-executable HERDR_BIN_PATH reports `started` while the spawned daemon dies silently (DEVNULL stderr). M17 and M20 survived.
- W5 `daemon.py:39-44`: `is_running` probes with the same exclusive lock; a new daemon whose `run` collides with a probe (status action, concurrent start, handoff wait loop) exits 0 silently, leaving no poller.
- W6 `daemon.py:24,140-147`: the 5 s handoff wait is shorter than a worst-case old-daemon cleanup (N panes x up to 2 s socket + 2 s CLI timeout, precisely when the old socket is dead). Reproduced (E2): handoff returns `failed` and no poller runs afterwards until a manual start.
- W7 Strict TDD evidence: apply-progress TDD table lacks TRIANGULATE/SAFETY NET columns; tick bool RED was not isolated.
- W8 `tests/lifecycle/test_daemon.py:205,220`: `addCleanup(killpid)` runs after the `with TemporaryDirectory()` block has already deleted the pidfile, so a failing assertion leaks the real daemon (observed during mutation runs; killed manually; it would self-exit via the orphan guard after ~5 min). Register cleanup with the temp dir via `addCleanup` instead of `with`, or kill in a `finally` inside the block.
- W9 Task 5.3a [APPROVAL] unchecked (user-owned link/enable); slice cannot be considered live-validated until then.

**SUGGESTION**:
- S1 Spawn and manifest commands without `-B` (or `PYTHONDONTWRITEBYTECODE=1`) write `__pycache__` under the plugin `src/`, outside `HERDR_PLUGIN_STATE_DIR` (spec S2-S8 wording "write only to HERDR_PLUGIN_STATE_DIR").
- S2 `tick.py:20` `_unreadable` grows without bound for sessions that stay unreadable and then disappear; apply the same 1024 cap as the locator.
- S3 `test_daemon.py:63` cleanup closes fd number `fd` if `/dev/fd/{fd}` exists, which can close a reused, unrelated fd; track closure explicitly.
- S4 `test_claude_locator.py` cap test asserts on private `_last_failure`; prefer asserting log behaviour.
- S5 Add one e2e daemon test with a fake herdr returning a Claude pane and a temp-HOME transcript to prove C13 "publishes locally" through the real process; pin `INTERVAL_S` within 3-5 s.
- S6 Update design.md to record `tick() -> bool` (False = Herdr unreachable) as the orphan-guard contract.

### Verdict
PASS WITH WARNINGS
All 151 tests pass and the 4 slice scenarios are covered; the lifecycle core (flock, spawn, signals, orphan guard, status privacy) is correct, but the kill target is not verified against the lock holder (reproduced SIGTERM to an unrelated process in a race window), the handoff wait can strand the plugin without a poller, and manifest runtime assumptions (python3 on PATH >= 3.10, cwd) remain unverified.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:8139aedc694850a46983abf6dd4b7b33aedd0d4544c5c819fef1fb4fed14d217
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 2/2
scenarios: 4/4
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:6ec061f172fe8b92526950aa3aa10ae89e06d3309267099eb65d47ac3e46e6a4
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 5 re-verification after the correction

**Change**: agent-token-usage-mvp
**Candidate**: branch `slice-5-lifecycle`, HEAD `fb36d9a` (tree `b164534`). The scope is `git diff e1a989b fb36d9a`: 6 files, +262/-56. The overage was accepted by the user. Commits: e7b435f (lifecycle identity and handoff) and fb36d9a (main guards and `-B`).
**Mode**: Strict TDD (`openspec/config.yaml:9`).
**Scope**: The same slice 5 scope as before, from plugin-lifecycle: "Single detached poller" (3 scenarios) and "Stop and status actions" (1 scenario). That is 2 requirements and 4 scenarios. The full change has 17 requirements and 26 scenarios.
**Evidence revision**: sha256 over `tree:b164534cd9d1402b3c5ab1c94576016ae7b56c6d\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`.
**Method**: Tests, build, mutations and experiments ran in git-archive copies under the scratchpad with `python3 -B`. The repository was not touched. There was no real herdr, no real socket, and no `herdr plugin link/enable`. Every daemon used a temporary HOME and state directory, a fake bin and a nonexistent socket. After all runs, `pgrep -fl "src/main.py"` printed nothing (exit 1).

### Completeness
| Metric | Value |
|--------|-------|
| Slice 5 tasks total | 4 (5.1, 5.2, 5.3, 5.3a) |
| Tasks complete | 3 |
| Tasks incomplete | 1: 5.3a [APPROVAL] `herdr plugin link/enable`. It is user-owned and intentionally not run (W9). |

### Build & Tests Execution
**Build**: Passed. `python3 -m compileall -q src tests` ran in a fresh archive copy, with exit 0 and empty output.
**Tests**: 164 passed, 0 failed, 0 skipped. `python3 -B -m unittest discover` ran with exit 0 on Python 3.14.8. Within that run, 30 lifecycle tests passed in verbose mode (test_daemon, test_main, test_manifest).
**Coverage**: Not available, because no coverage tool is installed.

### Spec Compliance Matrix (slice 5 scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Single detached poller | Handoff re-run | `test_daemon.py > TestRun.test_second_run_exits_zero_without_ticking`, `TestStart.test_live_same_socket_is_noop`, `TestStart.test_changed_socket_terminates_then_respawns` | COMPLIANT |
| Single detached poller | Stale pidfile | `TestRun.test_stale_pidfile_replaced`, `TestStart.test_stale_pidfile_spawns`, `TestStart.test_probe_clears_stale_lock_file_pid` | COMPLIANT |
| Single detached poller | No connectivity | `TestRealSpawn.test_start_status_stop_and_missing_env` (real offline daemon) plus the slice 4b tick publishing tests | COMPLIANT (composite) |
| Stop and status actions | Stop | `TestRun.test_stop_clears_published_persists_and_removes_pidfile`, `TestRealSpawn`, `TestStart.test_unverified_pid_is_never_signaled`, `test_lock_file_pid_mismatch_is_not_signaled`, `test_unsafe_pids_are_never_signaled` | COMPLIANT |

**Compliance summary**: 4/4 scenarios compliant.

### Prior Findings (slice 5)
| Finding | Status | Evidence |
|---|---|---|
| W1: SIGTERM sent to an unverified pid | RESOLVED (a microsecond residual remains, see S-R1) | `daemon.py:184` now signals only when the pidfile pid equals the lock-file pid, the pid is > 1, and it is not the caller's own pid. The poller writes its pid into `poller.lock` right after it gets the flock (`daemon.py:113-114`) and truncates the file before it closes the fd (`daemon.py:121`). A probe truncates the file only while it holds the lock (`daemon.py:54`). **E1 re-run**: the pidfile holds the pid of an unrelated `sleep 60` and a probe holds the lock (empty lock file). `stop()` returned `failed` and the handoff `start()` returned `failed`; the victim was not signaled (`poll()` None) in either case. The tests `test_unverified_pid_is_never_signaled`, `test_lock_file_pid_mismatch_is_not_signaled` and `test_unsafe_pids_are_never_signaled` pass. Mutations N2 (lock-pid check removed) and N8 (own pid allowed) are KILLED. |
| W3: prune, SIGHUP, SIGINT and `pid > 1` untested | RESOLVED | M1 (no prune) and M2 (prune only at startup) are KILLED by `test_prune_at_startup_and_hourly`. M3 (SIGHUP not ignored) is KILLED by `test_signal_handlers`. M15 (SIGINT unhandled) is KILLED: the handler call raises KeyboardInterrupt and aborts the run. M5 (`pid > 1` removed) is KILLED by `test_unsafe_pids_are_never_signaled`. |
| W4: input checks in main.py | RESOLVED (two branches remain untested, see S-R3) | `main.py:5-7` checks the version before any PEP 604 import. Under the real `/usr/bin/python3` (3.9.6), `status` exits 2 with "Python 3.10 or newer is required" and no traceback. A state directory under `/nonexistent_root_dir/x` exits 1 with "state directory is not usable" and no traceback (`main.py:60-64`). For `start`, a relative bin, a missing bin and a non-executable bin (`/etc/hosts`) each exit 2 with a short message and no spawn (`main.py:56-58`). `run` with a bad bin exits 1 with `cannot start (HerdrError)`. Mutations M17b (bin check removed), N9 (OSError not caught) and N10 (no version guard) are KILLED. M17 and M20 still survive (S-R3). |
| W5: probe race | RESOLVED | `daemon.py:105-112`: `run()` retries the lock 10 times, 0.1 s apart. Tests `test_run_retries_lock_so_a_probe_collision_leaves_a_poller` and `test_run_gives_up_after_bounded_retries` pass. N5 (`LOCK_TRIES = 0`) is KILLED. Stress run: 15 real `start`s, each under 6 concurrent `status` loops, lost no poller (0 lost). |
| W6: handoff wait shorter than cleanup | RESOLVED for the reproduced scenario (a residual remains, see W-R1) | `CLEANUP_S = 3` is checked before each clear (`daemon.py:160-164`), and `WAIT_S = 8` (`daemon.py:35`). A failed handoff now exits 1 and logs `handoff_failed` (`main.py:84-95`). **E2 re-run** (real daemon, 4 published panes, fake herdr at 1.9 s per call, steady state): the handoff `start` returned `restarted` with rc 0 in 5.2 s. The old daemon logged `cleanup_deadline` and exited, and the new daemon is `running ... panes=4`. N6 (no deadline) and N7 (`WAIT_S = 5`) are KILLED. |
| W8: test cleanup order | RESOLVED | `test_daemon.py` now registers `tmp.cleanup` first, so it runs last (LIFO), and `killpid` runs before it. Mutation N3 makes `TestRealSpawn` fail while its daemon is still alive, and the mutation runner's `pgrep -f <copy>` check found no leaked daemon. |
| S1: `-B` | RESOLVED | The spawn argv (`daemon.py:202`) and all 4 manifest commands (`herdr-plugin.toml:11,16,21,26`) pass `-B`. No `__pycache__` directory appeared under the copy's `src/` after several real daemons ran from it. N11 is KILLED by `test_spawn_argv_and_kwargs`. |
| W2: manifest runtime assumptions | OPEN (needs the user's live step) | The manifest still relies on `python3` from PATH and a cwd equal to the plugin root. With Python < 3.10 the plugin now fails cleanly (exit 2) instead of with a traceback, but it still does not run. Confirm during 5.3a. |
| W9: live link/enable | OPEN | 5.3a is unchecked and user-owned. |
| W7: Strict TDD table columns | OPEN (not in correction scope) | The apply-progress table (#159) has RED and GREEN columns only, with no TRIANGULATE or SAFETY NET columns. |

### Lock-file pid protocol analysis
- **Can a probe that truncates race with a daemon writing its pid?** No. The probe truncates only after `flock(LOCK_EX|LOCK_NB)` succeeds (`daemon.py:43,54`). The daemon writes only while it holds the same exclusive flock (`daemon.py:105-114`), and it keeps the flock until after its final truncate (`daemon.py:121-122`). Each caller opens the file separately, so these are separate open file descriptions and the BSD flock excludes them from each other. Stress run: 200 `status` probes (16 in parallel) against a live daemon. In every one the lock file still held the daemon pid, the daemon stayed alive, and there were 0 mismatches.
- **A SIGKILL leaves the pid in the lock file**: confirmed. After a real SIGKILL, both the lock file and the pidfile still hold the old pid. The next probe (`status`) reported `stopped` and truncated the lock file to `''`. After that, `stop` returned `stopped` without signaling anything, and a fresh `start` recorded the new pid in both files. Note that `start`, `stop` and `status` all probe before they read anything.
- **Is there a path where a reused pid gets signaled?** Yes, but only in a microsecond window (S-R1). Conditions:
  1. A daemon P was SIGKILLed, and no probe has run since.
  2. Process X takes the flock for its first probe, or a new poller does so in `run()`. X is between `flock` (`daemon.py:43`) and its `ftruncate` (`daemon.py:54` or `:113`).
  3. At that moment, process Y's `is_running` returns True, and Y reads the pidfile and the lock file and finds P in both.
  4. P has already been reused.

  A deterministic simulation holds the flock without truncating, with P (a `sleep` victim) in both files. In that state `stop()` sent SIGTERM to the victim (rc -15). A similar window exists when a daemon is SIGKILLed between Y's `is_running` and Y's `_terminate`. Both windows are orders of magnitude narrower than the original W1, which needed only a stale pidfile and any lock holder. The docstring claim at `daemon.py:7-8` ("never mistaken") is therefore slightly overstated.

### Mutation Summary (archive copies, full suite, `python3 -B`)
Killed (16): M1, M2, M3, M5, M15, M17b, N1 (probe does not truncate), N2, N3 (run does not write the pid; `TestRealSpawn` stop fails), N5, N6, N7, N8, N9, N10, N11.
Survived (5):
- M17: `start` with the state directory set but no bin. The real code rejects it at `main.py:53`. In the mutant, `isabs(None)` raises a traceback.
- M20: `_build_poller` exceptions not guarded.
- N4: the `finally` block does not truncate. This is benign, because the next probe truncates.
- N12: the `handoff_failed` log is removed.
- N13: the `cleanup_deadline` log is removed.

No daemon leaked from any mutant run.

### Runtime Experiments
- **E1**: see W1 above.
- **E1-residual**: see the lock-file analysis above.
- **E2 (steady state)**: see W6 above.
- **E2-grow**: the same setup, but every transcript grows just before the handoff, so the old daemon's in-flight tick is reporting 4 panes at 1.9 s each. The handoff `start` returned `failed` with rc 1 in 8.2 s. The log shows `handoff_failed cmd=?` and then `cleanup_deadline`. The old daemon exited later, and `status` is `stopped`: no poller runs afterwards (W-R1).
- **E3, E4, bad bin**: see W4 above.
- **W5 stress**: see W5 above.

### Correctness and Coherence
| Area | Status | Notes |
|------|--------|-------|
| Kill-target identity | OK (one narrow residual) | Pidfile pid = lock-file pid, plus the `> 1` and not-own-pid guards. The design rationale "immune to stale pids and PID reuse" now holds, except for the window in S-R1. |
| Probe vs. daemon writes | OK | Both sides are serialized by the exclusive flock (see the analysis above). |
| Run lock retry | OK | It is bounded at about 1 s. A real duplicate poller now waits about 1 s before it exits 0, which is harmless. |
| Cleanup deadline | OK | The deadline is checked before each clear, so the worst case is 3 s plus one CLI clear (2 s timeout). Clears go through the CLI only, so the 4 s socket-plus-CLI assumption in `daemon.py:35` is conservative. |
| Handoff wait | Partial | It covers cleanup, but not an in-flight tick that has several slow publish calls (W-R1). |
| main.py error surface | OK | Version, environment, bin and OSError paths give short messages with no absolute paths. These are asserted in `test_main.py:27-31`. |
| `-B` and the manifest | OK | Writes stay within the state directory. |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Yes | Apply-progress #159 has a RED/GREEN table for every fix. |
| All fixes have tests | Yes | W1, W3, W4, W5, W6, W8 and S1 each have tests: 13 new tests, 3 updated. |
| RED confirmed | Yes (self-reported) | The RED reasons are recorded and match the mutation results above. |
| GREEN confirmed | Yes | 164/164 pass. |
| Triangulation | Adequate | Kill-target: mismatch, unverified, unsafe pids and the positive respawn case. Lock retry: success after a collision and a bounded give-up. |
| Safety net for modified files | Not reported | W7 is still open. |

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit/adapter | 26 lifecycle | 2 | unittest |
| Integration (real subprocess) | 4 (TestRealSpawn plus 3 in test_main) | 2 | unittest + subprocess |
| E2E | 0 | - | not installed |

### Changed File Coverage
Skipped, because no coverage tool was detected.

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| `tests/lifecycle/test_daemon.py` | 175 | `assertGreaterEqual(daemon.WAIT_S, daemon.CLEANUP_S + 4.0 + 1.0)` | It checks a relation between constants and exercises no behavior. Its model of the worst case leaves out the in-flight tick, which E2-grow shows can exceed `WAIT_S`. It does kill N7. | SUGGESTION (folded into W-R1) |
| `tests/lifecycle/test_daemon.py` | 170 | `assertLess(len(cleared), 10)` | A weak bound: the test passes with any count from 0 to 9. A companion assertion confirms that cleanup completed. | SUGGESTION |

**Assertion quality**: 0 CRITICAL, 0 WARNING. There are no tautologies and no ghost loops: the loops iterate over fixed tuples.

### Quality Metrics
**Linter**: Not available. **Type Checker**: Not available.

### Issues Found
**CRITICAL**: None.

**WARNING**:
- W-R1: residual of W6, pre-existing and narrowed by the correction, carried over. `daemon.py:125-147` and `daemon.py:35`: the handoff wait does not bound a tick that is already running. A SIGTERM that arrives while a tick publishes N changed panes on a slow herdr waits up to about N x 2 s before cleanup starts. Reproduced in E2-grow: `start` returned `failed` after 8.2 s and no poller runs afterwards. The difference from before is that this is now logged as `handoff_failed` and returns exit 1 instead of failing silently. Options:
  - Check `_stop` between tick actions.
  - On a wait timeout, spawn anyway and let the new `run()` wait on the lock for longer than `LOCK_TRIES` x 0.1 s.
- W2: still open. The `python3` on PATH and the cwd assumptions need the user's live 5.3a step.
- W7: still open and not in correction scope. The Strict TDD table has no TRIANGULATE or SAFETY NET columns.
- W9: still open. 5.3a [APPROVAL] is unchecked and user-owned.

**SUGGESTION** (new or residual after the correction; carried over under the single-correction rule):
- S-R1: residual of W1. A microsecond window can still signal a reused pid (`daemon.py:43-54`, `105-113`, `184`); see the lock-file analysis above. The window needs a SIGKILLed daemon, no probe since the kill, a racing first probe or new poller, and a reused pid. One way to close it is to record the start time with the pid in the lock file and compare it with the process start time. Another is to read the lock-file pid only while you hold a shared lock that probes do not take. Also soften the docstring at `daemon.py:7-8`.
- S-R2: `main.py:94` logs `cmd="start/stop"`, but the log sanitizer turns it into `cmd=?` (seen in E2-grow), so the field carries no information. Pass the real command, for example `cmd=start`.
- S-R3: M17 survives because no test runs `start` with the state directory set and HERDR_BIN_PATH missing. In the mutant this would raise a `TypeError` traceback at `main.py:56`. M20 survives because `run` with an invalid bin is not tested; manually it exits 1 cleanly. Add both cases to `test_main.py`.
- S-R4: N12, N13 and N4 survive. The `handoff_failed` and `cleanup_deadline` log events and the truncate in the `finally` block have no assertions.
- S-R5: `test_daemon.py:175` checks only the relation between the constants. A behavioral handoff test with a slow fake would catch W-R1.
- Note: a daemon from before the correction writes no pid into the lock file, so the new `stop` and handoff code would return `failed` against it. The plugin was never linked (5.3a), so no such daemon exists in the field and nothing needs to be done.
- The earlier slice 5 suggestions S2 to S6 are unchanged and stay open.

### Regressions Introduced by the Correction
None that block.
- `is_running` now writes to the lock file. That is safe, because it does so only while it holds the exclusive lock.
- A duplicate `run` now exits after about 1 s instead of immediately.
- `_log_failed_handoff` can raise OSError on an unusable state directory. It is caught by `main.py:62`, which then prints a second message.

The new non-critical observations are S-R1 to S-R5 above, carried over.

### Verdict
PASS WITH WARNINGS

164/164 tests pass and the build is clean. W1, W3, W4, W5, W6, W8 and S1 are resolved, with runtime, stress and mutation evidence: 16 of 21 mutants were killed, including every in-scope mutant except M17 and M20 (see S-R3). E1 and E2 no longer reproduce. Two narrow residuals remain and are carried over: an in-flight tick can still exceed the handoff wait (W-R1), and a microsecond pid-reuse window remains (S-R1). W2 and W9 wait on the user's live link/enable step, and W7 is still open.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:e95838ca051232b314d4f2100f2a90b25ab67363263f41d53e872ff8a8d7e16c
verdict: fail
blockers: 1
critical_findings: 1
requirements: 1/2
scenarios: 1/2
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:bf510386786bc9d7435868537b0da32fc165463fd00163671b213143561c3c1f
build_command: python3 -B -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 6a (sidebar patch, README, SECURITY, design sync)

**Change**: agent-token-usage-mvp
**Candidate**: `git diff slice-5-lifecycle slice-6-docs` (HEAD 1da71b4, tree f87abf3). Commits 5fc066c, 8671e9d, 4c20056, 1da71b4. 7 files, +421/-15 (overage accepted by the user).
**Mode**: Strict TDD (`openspec/config.yaml:9`).
**Scope**: sidebar-metadata "Approval-gated config patch" (1 scenario: Custom sidebar) and plugin-lifecycle "Uninstall and documentation" (1 scenario: Uninstall). 2 requirements, 2 scenarios. Full change: 17 requirements, 26 scenarios.
**Evidence revision**: sha256 over `tree:<tree>\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`.
**Method**: All execution in a git-archive copy under the scratchpad with `python3 -B`. Repo untouched (`git status` clean). No `~/.config/herdr` read or written; every `--apply` used temp dirs, and CLI runs used a temp HOME. Herdr was used only for read-only `--help` (plus reading the Homebrew-installed README/CHANGELOG files). `herdr --default-config` was NOT run (outside the allowed `--help` boundary).

### Completeness
| Metric | Value |
|--------|-------|
| Slice 6a tasks | 3 (6.1, 6.2, 6.3) |
| Complete | 3 |
| Incomplete in 6a scope | 0 (6.4 [APPROVAL] manual validation and 5.3a link/enable remain user-owned and unchecked) |

### Build & Tests Execution
**Build**: Passed. `python3 -B -m compileall -q src tests`, exit 0, empty output.
**Tests**: 177 passed, 0 failed, 0 skipped (`Ran 177 tests`, OK) on Python 3.14.8. Stdout noise from `apply()` prints ("created", "patched ...") is harmless.
**Coverage**: Not available.

### Spec Compliance Matrix (slice 6a scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Approval-gated config patch | Custom sidebar | `test_sidebar_patch.py > TestPlan.test_custom_claude_row_only_adds_tokens`, `test_plan_writes_nothing`, `TestCli.test_print_and_apply_via_main`, `TestApply.test_backup_then_atomic_replace` | COMPLIANT (scenario as written). Requirement still fails, see C1 and W1. |
| Uninstall and documentation | Uninstall | `TestApply.test_backup_then_atomic_replace` (backup bytes == original) only | PARTIAL: the rollback is documented but not exercised; it does not cover the no-backup "created" path, and Herdr unlink/uninstall behavior is not verified (W3). |

**Compliance summary**: 1/2 scenarios compliant, 1 partial.

### Sidebar patch safety analysis (runtime experiments in temp dirs)
| Check | Result | Evidence |
|---|---|---|
| Text-minimal edit, comment preserved | OK (LF files) | CUSTOM fixture keeps `# keep me`. E5 commented trailing row, E6 `]`/escaped quotes inside strings, E9 array-of-tables after the section: all patched correctly. |
| tomllib re-parse equality | OK, load-bearing, untested | E4: a fake `[ui.sidebar.agents]` header inside a multiline string is misattributed by the line scanner and caught only by `parsed != expect` (`sidebar_patch.py:126`) -> refuse. Mutation M1 (remove the comparison) SURVIVES. |
| Refusal paths | OK | No rows, inline table, invalid TOML, empty rows, multiline strings, quoted header (E7), dotted keys (E11), codex-only override (E14): all refuse, exit 1, stderr. |
| `--print` writes nothing | OK | `test_plan_writes_nothing`, CLI test; M5 KILLED. |
| `--apply` backup before atomic replace, mode kept | OK for regular files | `sidebar_patch.py:146-158`; M3, M4, M17 KILLED. Backup is created with the default umask (E1: config 0600 -> backup 0644). |
| Symlinked config | DEFECT (W2) | E1: `config.toml` symlinked to a dotfiles target. After `--apply`: `still_symlink=False`, `target_patched=False`. `os.replace` (`:158`) converts the symlink into a regular file; the dotfiles source is silently left behind. |
| CRLF config | Not text-minimal (S3) | E12: `read_text` (`:92`) normalizes `\r\n`, so every line is rewritten with LF; the `--print` diff does not show it. |
| Non-UTF-8 file / directory path | Traceback (S2) | E2 `UnicodeDecodeError`, E3 `IsADirectoryError`: `read_text` at `:92` is outside the `try`, so the `UnicodeDecodeError` catch at `:95` is dead code. |
| Concurrent edit | Lost update, recoverable (S4) | race.py: an edit that lands between `plan()` and `os.replace` is overwritten; the backup holds the edited bytes, so it is recoverable. |
| Never invoked by startup | OK | Manifest and daemon/tick contain no `sidebar_patch`; lazy import only in `main.py:47-49`; M21 KILLED. |
| Python 3.9 | OK | `/usr/bin/python3` (3.9.6) `sidebar-patch --print` -> "Python 3.10 or newer is required", rc 2. |
| Python 3.10 | DEFECT (W4) | `tomllib` exists only in 3.11+ (PEP 680); `sidebar_patch.py:15` and the test module import it unguarded. 3.10 was not available locally, so this is static evidence only. |

### Product risk: missing `[ui.sidebar.agents]` (C1)
- `sidebar_patch.py:20,101-103`: with no `[ui.sidebar.agents]` (or no file), the patch appends `rows = [["agent", "$tokens"]]`.
- explore.md:25-26 says that `rows` (and `rows_by_agent`) replace the layout entirely, and that `~/.config/herdr/config.toml` does not exist on the user's machine today. So the default path IS the user's path.
- The source spec `HERDR_PLUGIN_TOKEN_USAGE_SPEC.md:77-89` shows an initial layout of `[["state_icon","workspace","tab"],["agent","$tokens"]]` and says to adapt to the existing config "without destroying it". The minimal section drops the state icon/workspace/tab row and replaces Herdr's built-in default layout with a guessed single row.
- The `--print` diff shows only `+` lines, so a reviewer cannot see that the defaults are dropped. README.md:31 presents this as a safe "minimal section".
- This breaks the requirement's intent ("adding `$tokens` to `rows` ... without ... dropping custom rows", sidebar-metadata spec) and the user's stated goal of adding `$tokens` without breaking the sidebar.
- Recommended safe behavior: when no `[ui.sidebar.agents]` exists, REFUSE (exit 1) and print manual instructions. Tell the user to copy Herdr's default `rows` from `herdr --default-config` into `config.toml` and append `"$tokens"` to the agent row, then re-run `--print` (which will then take the safe "extend last row" path). Alternative (heavier): read the defaults from `herdr --default-config` via `HERDR_BIN_PATH` and seed the section with them plus `$tokens`; that needs the user to approve running Herdr and adds a subprocess. Update README.md:31, design.md:82, tasks 6.2, and the tests (`test_missing_file_and_missing_section_add_minimal_section`, `test_apply_noop_and_missing_file`, `test_default_config_is_under_home...`) accordingly.

### Mutation Summary (archive copies, full suite)
- Killed (11): M2 (no triple-quote refusal), M3 (no backup), M4 (no chmod), M5 (`--print` applies), M6 (glue always comma), M7 (no noop), M17 (fixed mode), M19 (refuse exit 0), M20 (refuse to stdout), M21 (eager import in main), M23 (refuse when file is missing).
- Survived (7):
  - M1: the `parsed != expect` safety net is removed (the key safety check).
  - M8: comment skipping is removed (no comment containing brackets or quotes in the fixtures).
  - M12: backup opened `wb` instead of `xb`.
  - M13: `os.replace` replaced by an in-place write (atomicity untested).
  - M14: default config path changed to `/nonexistent_dir_x/...` (`test_default_config_is_under_home...` cannot tell; it only sees `/dev/null`).
  - M18: escape skipping is removed.
  - M22: separator newline before the appended section is removed.

### Docs accuracy
| Claim | Status | Evidence |
|---|---|---|
| `herdr plugin link/enable/disable/unlink/uninstall`, `log list` names and arity | OK | `herdr plugin <cmd> --help`; id `local.token-usage` matches `herdr-plugin.toml:4`. |
| Total definition, Claude-only, never `0` | OK | Consistent with design and earlier verified slices. |
| Inspected dirs (`~/.claude/projects`, subagents) | OK | `main.py:39`, `claude_locator.py:56-60`. |
| Log location `<state dir>/token-usage.log` | OK | `adapters/log.py:17`. |
| Python >= 3.10 | Partly wrong | The poller needs 3.10; `sidebar-patch` and the tests need 3.11 (W4). |
| "Disable: ... (the poller clears its tokens on stop)" | Overclaim | README.md:36. The poller is self-detached (`start_new_session=True`, `daemon.py:202`). Nothing shows that `herdr plugin disable` runs the `stop` action, and the orphan guard fires only when Herdr is unreachable. The rollback in proposal.md:70 says "Run the stop action, then disable/uninstall" (W3). |
| "unlink ... or uninstall removes only plugin files and state" | Unverified | README.md:37. It is not shown that Herdr deletes `HERDR_PLUGIN_STATE_DIR` on unlink. A running poller keeps publishing after unlink or uninstall unless it is stopped first (W3). |
| "Revert the sidebar patch by restoring its `.bak-*`" | Incomplete | No backup exists on the created-file path (`sidebar_patch.py:150`), which is the user's case. Restoring an old backup also drops later user edits (W3). |
| SECURITY.md:21 "handoff may wait up to WAIT_S (8 s) ... before respawning" | Understated | The prior verify (W-R1, E2-grow) showed that a slow in-flight tick makes the handoff return `failed` (rc 1), and then no poller runs. The doc implies it always respawns (W5). |
| SECURITY.md:20 pid-reuse microsecond window; :19 symlink/hardlink same-user residual | OK | Matches S-R1. It omits the sidebar-patch symlink clobber (W2). |

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| sidebar_patch bullet (design.md:82) | Code matches | The design itself encodes C1 and diverges from the spec text "add `$tokens` to `rows` and any `rows_by_agent` overrides" (E8: with a claude override present, `rows` is not patched) (W1). |
| Python >= 3.10 (design.md:5) | Partial | tomllib needs 3.11 (W4). |
| State schema (design.md:62-64) | Mostly | `skip` is stored as `1` or absent (`jsonl_tail.py:68,78`), not `false` (S5). |
| Duplicate guard rationale (design.md:30) "immune to ... PID reuse" | Overclaim | It contradicts the S-R1 residual that SECURITY.md:20 admits (S5). |
| Handoff `WAIT_S` 8 s, `CLEANUP_S` 3 s, `tick() -> bool`, `-B` spawn | Yes | `daemon.py:33,35,202`, `tick.py:22`. |

### TDD Compliance
| Check | Result |
|---|---|
| TDD evidence reported | Yes (apply-progress #159: RED = ImportError before src, GREEN 177) |
| All tasks have tests | Yes for 6.1/6.2 (13 new tests); 6.3 is docs |
| Triangulation | Adequate for refusal shapes (5 subtests) and glue variants; weak for the scanner (M8, M18) and the safety net (M1) |
| Safety net / triangulate columns | Not reported (W7 carried) |

**Assertion quality**: no tautologies. `test_default_config_is_under_home_and_never_used_by_startup` does not assert the default path (M14 survives), so its name overclaims (S1).

### Issues Found
**CRITICAL**:
- C1: `sidebar_patch.py:20,101-103` (with README.md:31, design.md:82, tasks 6.2). When `[ui.sidebar.agents]` is missing, which is the user's actual state (explore.md:26), `--apply` writes `rows = [["agent", "$tokens"]]`. That replaces Herdr's default sidebar layout and drops the state_icon/workspace/tab row the source spec shows (`HERDR_PLUGIN_TOKEN_USAGE_SPEC.md:81-84`). The `--print` diff hides this. Fix: refuse and print manual instructions (copy the defaults from `herdr --default-config`, then append `"$tokens"`), and update the docs and tests.

**WARNING**:
- W1: The spec/design contract drifted during apply. The sidebar-metadata spec says "adding `$tokens` to `rows` and any `rows_by_agent` overrides". The code (and the rewritten design.md:82 and tasks 6.1/6.2) patches only the effective Claude row; E8 shows `rows` left untouched when a claude override exists. Patching only the Claude row is defensible because Codex shows nothing, but the spec needs a matching delta, or the code must follow the spec.
- W2: A symlinked config is clobbered (`sidebar_patch.py:158`). E1: the symlink becomes a regular file and the dotfiles target is not patched. The backup is also created with umask mode (0644 for a 0600 config, `:146`). Fix: resolve with `os.path.realpath` and write next to the target, or refuse on symlinks; copy the mode to the backup.
- W3: Uninstall and disable docs (README.md:36-37) overclaim and are incomplete. They do not say to run `stop` before disable, unlink or uninstall (the detached poller keeps publishing). They do not show that state is removed on unlink. They give no rollback for the created-file path (no `.bak-*` exists there). This leaves the Uninstall scenario PARTIAL.
- W4: The Python version claim is wrong for `sidebar-patch` and the tests. `tomllib` needs 3.11 (`sidebar_patch.py:15`). On 3.10 the main.py guard passes and an ImportError traceback follows. Either say ">= 3.11 for sidebar-patch" or guard the import with a clean message.
- W5: SECURITY.md:21 understates the handoff residual. Per W-R1, the handoff can fail and leave no poller running; it does not just wait and then respawn.
- W6: The tomllib equality safety net is untested (M1 survives) even though E4 proves it is load-bearing. Add the E4 fixture (a fake header inside a multiline string) as a refusal test.
- W7 (carried): the Strict TDD table has no TRIANGULATE or SAFETY NET columns.
- W9/W2-old (carried): 5.3a and 6.4 [APPROVAL] are unchecked and user-owned; W-R1 is still open.

**SUGGESTION**:
- S1: M8, M12, M13, M14, M18 and M22 survive. Add fixtures for a comment containing `]`/`"` and for an escaped quote; assert the default path (for example, the CLI `--print` diff names `config.toml` under the temp HOME); assert the backup is never overwritten.
- S2: Move `read_text` into the `try` (`:92`) and catch `OSError` and `UnicodeDecodeError`, so you refuse cleanly instead of printing a traceback that contains an absolute path (E2, E3).
- S3: Preserve line endings. Read and write with `newline=""` so CRLF files stay text-minimal (E12).
- S4: Narrow the TOCTOU window. Re-read the file in `apply()` and abort if it differs from the planned text (race.py shows a lost update, recoverable from the backup).
- S5: design.md:30 "immune to ... PID reuse" and design.md:64 `"skip":false` are slightly inaccurate. `MANUAL` (`sidebar_patch.py:22`) hardcodes `~/.config/herdr/config.toml` even when `--config` is given.
- S6: Tests print to stdout during the run. Capture with `contextlib.redirect_stdout`.

### Verdict
FAIL

The suite passes (177/177) and the build is clean, and the patch is careful on files that already have a sidebar layout: it makes minimal edits, preserves comments, verifies with tomllib, refuses unsafe shapes, writes nothing on `--print`, and backs up before an atomic replace. It still fails on C1. On the user's real starting state (no `[ui.sidebar.agents]`), `--apply` silently replaces Herdr's default sidebar with a single guessed row, which defeats the purpose of the patch. Fix C1 (refuse with manual instructions) and W2/W3/W4 before archive.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d772f4a09966e67300e040fb9bb21b74d064cb6ce2a8af41b78c3f174728cfc4
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 2/2
scenarios: 2/2
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:b8615edcb22988fae82382e6b5cbbb8927c92579dc6a557dfacbe51897c239d6
build_command: python3 -B -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report: Slice 6a re-verification after the correction

**Change**: agent-token-usage-mvp
**Candidate**: `git diff 918a1de 0b7f85b` on `slice-6-docs` (HEAD 0b7f85b, tree 21ca81d). Commits 8c585ba (sidebar fixes) and 0b7f85b (docs). 8 files, +154/-80 (overage accepted by the user).
**Mode**: Strict TDD.
**Scope**: sidebar-metadata "Approval-gated config patch" (scenario: Custom sidebar) and plugin-lifecycle "Uninstall and documentation" (scenario: Uninstall). 2 requirements, 2 scenarios.
**Evidence revision**: sha256 over `tree:<tree>\ntest:sha256:<test hash>\nbuild:sha256:<build hash>\n`.
**Method**: All execution ran in a git-archive copy under the scratchpad with `python3 -B`. The repo was not touched (`git status` clean). No `~/.config/herdr` was read or written: all experiments used temp dirs, and CLI runs used `env -i` with a temp HOME. Herdr was used only for read-only `--help`, plus a read-only string search of the installed binary for the embedded default config text. `herdr --default-config` was not run.

### Completeness
| Metric | Value |
|--------|-------|
| Slice 6a tasks | 3 (6.1, 6.2, 6.3), all checked; 6.2 text updated to the new rule (`tasks.md:84`) |
| Incomplete in 6a scope | 0. 6.4 [APPROVAL] and 5.3a are user-owned and remain unchecked (carried). |

### Build & Tests Execution
**Build**: Passed. `python3 -B -m compileall -q src tests`, exit 0, empty output.
**Tests**: Passed. `Ran 183 tests ... OK` (Python 3.14.8), exit 0. This matches the expected 183.
**Coverage**: Not available.

### Spec Compliance Matrix (slice 6a scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Approval-gated config patch | Custom sidebar | `test_sidebar_patch.py > TestPlan.test_custom_claude_row_only_adds_tokens`, `test_rows_and_claude_override_both_get_tokens_idempotent_per_row`, `test_plan_writes_nothing`, `TestCli.test_print_and_apply_via_main` | COMPLIANT |
| Uninstall and documentation | Uninstall | `TestApply.test_backup_then_atomic_replace` (backup bytes == original), `test_apply_missing_file_refuses_and_second_run_is_noop` (no-backup path is now impossible); runtime rollback `cp .bak-* config.toml` gave a byte-identical original | COMPLIANT (the docs residuals are in W3-R) |

**Compliance summary**: 2/2 scenarios compliant.

### Prior Findings (slice 6a)
| ID | Status | Evidence |
|---|---|---|
| C1 default-layout replacement | RESOLVED | `sidebar_patch.py:99-116` refuses on a missing file, no `[ui.sidebar.agents]`, or no rows. `MINIMAL` was removed, and the only text change is a token insertion (`:123-125`). Runtime check over 16 shapes found no path that creates a `rows` or `rows_by_agent` section. Missing, empty, `[ui]` only, sidebar only, agents with no rows, commented defaults, codex-only override, empty rows, and inline `rows_by_agent` all refuse with `apply` rc 1 and no new files. Mutant Mh (append a rows section when the section is missing) was KILLED. |
| W1 spec rows + claude override | PARTIAL | `rows` and `rows_by_agent.claude` are both patched (`:110-129`), including when the claude override comes first and the edits are applied in descending order (mutants Md and Me KILLED). Other overrides (for example `codex`) are deliberately left alone (`test_sidebar_patch.py` asserts this), but the spec still says "any `rows_by_agent` overrides" (`specs/sidebar-metadata/spec.md:35`) and has no delta. See W1-R. |
| W2 symlink + backup mode | RESOLVED | E1 re-run: link kept, target patched, target mode 0600, backup mode 0600, backup == original, nothing extra next to the link. Relative link OK; dangling link refuses (rc 1). `:153-166`. Mutants Mb and Mc KILLED. |
| W3 uninstall docs | PARTIAL | README.md:37-38 now says to stop first, hedges state-dir removal, and the revert claim is accurate (a config is never created). README.md:36 (Disable) is unchanged, and the shell fallback in :37 fails. See W3-R. |
| W4 Python 3.11 | RESOLVED | `main.py:5-7` guard checks 3.11; README.md:11 and design.md:5 match; `test_main.py:33-38` simulates 3.10.9. Runtime: `/usr/bin/python3` (3.9.6) gives a clean "3.11 or newer" message with rc 2 for `sidebar-patch` and `stop`. No other 3.10 references remain in src, tests or specs. Side effect, consistent with the docs: the poller now also needs 3.11. Real 3.10 and 3.11 interpreters are not installed, so the 3.10 case is covered only by simulation. |
| W5 SECURITY handoff wording | RESOLVED | SECURITY.md:21 now names `handoff_failed`, exit 1, and recovery via `start`. This matches `main.py:87-98`. |
| W6 re-parse check untested (M1) | RESOLVED | `test_fake_header_in_multiline_string_is_refused_by_reparse`. The E4 re-run refuses with "Patched config failed validation." Mutant M1 KILLED. |
| S2 read inside try | RESOLVED | `:96-104`. A directory or non-UTF-8 file gives a short refusal; the CLI test passes a directory and gets rc 1 with no traceback. Mutant Mi KILLED. |
| S5 nits | RESOLVED | design.md:30 now admits the PID-reuse window; design.md:64-70 says `skip` is absent unless set; the manual message names the `--config` path (`:24-30`, mutant Mg KILLED). |
| W7, 5.3a, 6.4, W-R1 | OPEN (carried, out of scope) | |

### `herdr --default-config` advice
- `herdr --help` (0.8.2) lists `--default-config  Print default configuration and exit`, so the flag exists. It also lists `HERDR_CONFIG_PATH overrides config file path` and `herdr config check`.
- The default config text embedded in the binary has the sidebar section commented out: `# [ui.sidebar.agents]`, `# rows = [["state_icon", "workspace", "tab"], ["agent"]]`, and `# claude = [...]` under `# [ui.sidebar.agents.rows_by_agent]`. The advice is accurate, but a user who pastes these lines must also uncomment them; the steps do not say so (S-R2). After the paste, a single-line `rows` is patched correctly, and if `$tokens` was already added, re-running `--print` reports a no-op.

### Mutation Summary (archive copies, full suite)
- KILLED (8): M1, Mb, Mc, Md, Me, Mg, Mh, Mi.
- SURVIVED (2):
  - Mf: per-row versus any-row idempotence. The behavior is untested; see R1.
  - M14: default path (S1 carried).

### Regressions Introduced by the Correction
- R1 (WARNING, new, carried over): the idempotence rule changed from "any row has `$tokens`" (918a1de, verified noop) to "the last row has `$tokens`" (`sidebar_patch.py:117`). For a config with `$tokens` in a non-last row, for example `rows = [["agent", "$tokens"], ["cwd"]]`, `--apply` now adds a second `"$tokens"` to the last row, and Herdr would show the total twice. The diff makes this visible before approval, and no test pins either behavior (Mf survives). README.md:31 claims "re-runs are no-ops", which holds only for the patch's own output.
- No other regressions were found. CRLF files still normalize (S3, pre-existing). Non-table `agents` (`[ui.sidebar]\nagents = 1`) still raise an `AttributeError` traceback at `:109`; this is pre-existing and was verified on 918a1de (S-R1).

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| design.md:82 sidebar_patch bullet | Yes | Code matches the rewritten bullet: rows plus the claude override, never creates a section, symlink target patched, same-mode backup, refusals. |
| design.md:5 Python >= 3.11 | Yes | |
| design.md:30, :64-70 | Yes | Nits fixed. |

### TDD Compliance
RED (10 failures, 1 error) and then GREEN (183) are recorded in apply-progress #159. There are 6 new tests, and the old tests were updated to the new rule. The safety-net and triangulate columns are still not reported (W7 carried).

### Issues Found
**CRITICAL**: None.

**WARNING**:
- W1-R: `specs/sidebar-metadata/spec.md:35` says "any `rows_by_agent` overrides". The code patches only `rows` and `claude` (`sidebar_patch.py:110-112`). This is harmless, because Codex panes never show `$tokens`, but the spec needs a delta ("`rows` and the claude override") before archive, or a note in the archive.
- W3-R: README.md:36 still says "Disable: ... (the poller clears its tokens on stop)" and does not tell the user to run `stop` first. Nothing shows that `herdr plugin disable` runs `stop`; `herdr plugin disable --help` says only "Disable a plugin". At README.md:37, the shell fallback `python3 -B src/main.py stop` exits 2 ("HERDR_PLUGIN_STATE_DIR and HERDR_BIN_PATH must be set") unless `HERDR_PLUGIN_STATE_DIR` is exported (verified with `env -i`). "Herdr removes the plugin files" is also unverified for `unlink` of a linked repo.
- R1 (new, see Regressions): `$tokens` in a non-last row is duplicated on re-apply (`sidebar_patch.py:117`), and the behavior is untested (Mf survives).
- Carried: W7 (Strict TDD table columns); 5.3a and 6.4 [APPROVAL] unchecked and user-owned; W-R1 open.

**SUGGESTION**:
- S-R1: Guard `agents` and `by_agent` with `isinstance(..., dict)` at `:109`, so a non-table `agents` value refuses instead of raising a traceback (pre-existing).
- S-R2: In `_manual` (`:26-29`) and README.md:31, say that `herdr --default-config` prints the sidebar lines commented out, so the user must uncomment them. Mention `herdr config check` and `herdr server reload-config` after editing.
- S-R3: The backup is created with umask mode and only then chmod'ed (`:156-158`), so a brief 0644 window exists for a 0600 config. Create it with `os.open(..., O_CREAT|O_EXCL|O_WRONLY, mode)`. For a symlinked config, the backup lands next to the target (possibly inside a dotfiles repo), while README.md:38 says "next to the config".
- S-R4: The default path ignores `HERDR_CONFIG_PATH`, which `herdr --help` documents as an override (pre-existing). Honor it, or document `--config`.
- Carried: S1 (M14, M8, M12, M13, M18, M22), S3 (CRLF), S4 (TOCTOU), S6 (test stdout noise).

### Verdict
PASS WITH WARNINGS

183/183 tests pass and the build is clean. C1, W2, W4, W5, W6, S2 and S5 are resolved, with runtime and mutation evidence (M1 is now killed, the E1 symlink case is fixed, and no path creates a rows section). W1 and W3 are partially resolved: the residuals are spec text drift and the disable/stop wording. One new non-critical regression (R1, duplicated `$tokens` when it sits in a non-last row) is carried over under the single-correction rule. The user-owned items 5.3a and 6.4, plus W7 and W-R1, remain open.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:2f892d545e5ccfc2d416498034e741c9792412cd73f95c6f018f272cc58410c8
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 7/7
scenarios: 8/8
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:112793f98858f96d82fe2299e0cb96e3c87d5d4d9e0e2cd2cdeba04b3e755d83
build_command: python3 -B -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report (slice 6b: hardening carry-overs)

**Change**: agent-token-usage-mvp
**Candidate**: `git diff slice-6-docs slice-6b-hardening` (1a30ca4..801fbd0; commits 8d66f0a, 5949146, 801fbd0; 14 files, +179/-20). `evidence_revision` is the SHA-256 of that diff.
**Mode**: Strict TDD (`openspec/config.yaml:9`).
**Method**: The tests, build, mutations and experiments ran in a `git archive slice-6b-hardening` copy under the session scratchpad with Homebrew Python 3.14.8 (`python3 -B`, no `__pycache__`). The repository was not modified (`git status --short` is empty). The real herdr binary ran only with `--help`, `config --help` and `server --help`; its embedded default config was read with `rg -a` on the binary. No real socket, no `~/.config/herdr`, no `~/.claude/projects`, no network, and no plugin link/enable were used. Every daemon used a temp HOME, a temp state directory, a fake herdr bin and a nonexistent socket. Final `pgrep -fl "src/main.py"`: no output (exit 1).
**Scope of counts**: 7 requirements and 8 scenarios touched by slice 6b. Sidebar-metadata: Approval-gated config patch (Custom sidebar). Plugin-lifecycle: Single detached poller (Handoff re-run); Stop and status (Stop); Least privilege (Content never stored); Uninstall and documentation (Uninstall). Usage-accounting: State and retention (Pruning); Incremental tail (Growing file, Truncation). The full change has 17 requirements and 26 scenarios; earlier slice reports verified the rest.

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total (tasks.md) | 42 |
| Tasks complete | 40 (including 6b.1 to 6b.7) |
| Tasks incomplete | 2, both user-owned [APPROVAL]: 5.3a (link/enable) and 6.4 (manual validation) |
| 6.2 | Checked. Its "[APPROVAL, user-owned, not run] against `~/.config/herdr`" note is still accurate. |

### Build and tests
- Tests: `python3 -B -m unittest discover` gives `Ran 195 tests ... OK` (exit 0).
- Build: `python3 -B -m compileall -q src tests` exits 0 with empty output (scratch copy only).
- RED reproduced: the slice-6b tests run against the slice-6-docs source give `FAILED (failures=19, errors=2)` from 195 tests. This matches the apply-progress claim (#159).
- Coverage: not available (stdlib only).

### Carry-over resolution
| Item | Status | Evidence |
|---|---|---|
| R1 (6a): any-row idempotence | RESOLVED | `sidebar_patch.py:119` is a no-op when any row of a target already has `$tokens`, and each target is evaluated separately (`test_tokens_in_any_row_is_noop`, `test_tokens_in_any_row_noop_is_independent_per_target`). Runtime check: `--apply` twice with `HERDR_CONFIG_PATH` on a config where the claude override already had `$tokens` in a non-last row. The first run patched only `rows` and left `codex` untouched; the second printed "$tokens is already present." and wrote one backup. Mutant M1 (back to last-row only) is KILLED. |
| W1-R (6a): spec delta | RESOLVED | `specs/sidebar-metadata/spec.md:35` now says `rows` and `rows_by_agent.claude` only, which matches `sidebar_patch.py:112-114`. |
| W3-R (6a): disable/uninstall docs | PARTIAL | README.md:36 (Disable) now runs `stop` first and gives a correct shell fallback with `HERDR_PLUGIN_STATE_DIR`. README.md:37 (Uninstall) still says `(or python3 -B src/main.py stop)` without that variable, and that command exits 2 under `env -i` ("HERDR_PLUGIN_STATE_DIR and HERDR_BIN_PATH must be set"). The unverified claim "Herdr removes the plugin files" was removed. See W-6b-2. |
| S-R1 (6a): non-table `agents` | RESOLVED | `sidebar_patch.py:109-110`. The CLI with `[ui.sidebar]\nagents = 1` exits 1, prints manual steps and no traceback. M2 is KILLED. A non-table `rows_by_agent` was already ignored (`:113-114`). |
| S-R2 (6a): manual-steps text | RESOLVED | `sidebar_patch.py:24-30` and README.md:31 now say to uncomment, run `herdr config check`, then `herdr server reload-config`. `herdr config --help` lists `check`, and `herdr server --help` lists `reload-config`. The binary ships `# [ui.sidebar.agents]`, `# rows = [["state_icon", "workspace", "tab"], ["agent"]]` and `# claude = [...]` commented out, so "uncomment" is accurate. M4 is KILLED. |
| S-R4 (6a): `HERDR_CONFIG_PATH` | RESOLVED | `sidebar_patch.py:182-183`. `herdr --help` line 62 says "Env: HERDR_CONFIG_PATH overrides config file path", and `herdr --help` with that variable set shows the overridden `Config:` path. An empty value falls back to the default, as verified. M3 is KILLED. |
| W-R1 (slice 5): handoff during an in-flight tick | RESOLVED | `tick.py:36-39` checks the stop flag per session and `tick.py:46-60` per action. `main.py:42-44` wires `poller.is_stopping` (`daemon.py:99-100`). I re-ran E2-grow with a real daemon, 4 panes, a fake herdr at 1.9 s per call, all transcripts grown, and a handoff 4.5 s later. Before the fix it returned `failed` with rc 1 after 8.2 s. Now it returns `restarted` with rc 0 after 6.1 s, the old tick stopped after p3, cleanup cleared p1 and p2 and then hit `cleanup_deadline`, and the new daemon is `running`. Mutants M6 and M15 are KILLED. |
| #161 S1: tmp sweep | RESOLVED | `state_store.py:96-102` removes `*.tmp` files older than 1 h in the state root and in `sessions/`. M10 and M11 are KILLED. On concurrency, see Regression checks. |
| #161 S2: parent-dir fsync | RESOLVED | `state_store.py:25-33,53`, best effort. M9 is KILLED. |
| #161 S3: file-key allowlist | RESOLVED, with a regression (W-6b-1) | `state_store.py:15,19-22` rejects `""`, `.`, `~`, absolute paths and nested paths (`test_file_key_allowlist`). M12 (old check) is KILLED. M13 (dropping `".." in key`) is equivalent, because the regex cannot match a `/` after `agent-`. |
| #161 S5: duplicate log handler | RESOLVED | `log.py:17-18`. M14 is KILLED. See S-6b-1 for the different-directory case. |

### Regression checks
- **File-key allowlist and existing writers.** `tick.py:85-86` builds keys as `subagents/{p.name}` for every file that `claude_locator.py:58` matches with `agent-*.jsonl`. That glob accepts characters the allowlist rejects: spaces, `+`, `@`, non-ASCII. I probed this in the scratch copy with fake herdr and temp dirs. With a subagent named `agent-a b.jsonl`, `save_session` raised `ValueError` on every tick, the session was never saved, every tick re-read all files from offset `None`, and `save_session_failed` was logged every tick. Loading old state that contains a now-disallowed key does not crash (`load_session` does not validate). However, `tick.py:84` carries every saved key forward, so the stale key makes the session permanently unsaveable even after its file is gone. When a transcript is larger than one tick's read cap, the total stays stuck: with `max_read=300` the display stayed at "250 tokens", against "1.1k tokens" for the same data with an allowed name. This is a real, candidate-caused regression. Known Claude subagent names (`agent-<hex>`) match the allowlist, so the risk is low. See W-6b-1.
- **`make_logger` with the same name and a different directory.** The probe confirms that it silently keeps logging to the first directory. The second directory is created but gets no log. Production calls it once per process with one state directory (`main.py:38`), and `_log_failed_handoff` closes the logger (`main.py:98-100`), so there is no live impact. See S-6b-1.
- **Tmp sweep and concurrent writers.** No realistic race. Every writer of `*.tmp` (`state_store.py:46`, `daemon.py:75`) is the single flock-holding poller, and prune runs sequentially in the same loop (`daemon.py:133-135`). `mkstemp` gives a fresh mtime and the file is replaced within milliseconds, so only a writer stalled for more than 1 h could lose its tmp file. Even then, `os.replace` would raise, the error is caught (`state_store.py:54-56`) and logged by the caller, and the next tick retries. `status`/`stop`/`start` do not write state tmp files. `sidebar_patch` tmp files live next to the config, not in the state dir.
- **`should_stop` and unapplied actions.** Correct. An interrupted action restores the old record or drops the new pane (`tick.py:57-60`), so `published.json` reflects only applied actions (`test_stop_between_publish_actions_keeps_unapplied_for_retry`, and M7 is KILLED). An abort during the session loop returns before `save_published`, so the previous published state stays intact. `_cleanup` then clears what was actually published: E2-grow showed p1 and p2 cleared. p3, published by the interrupted tick, was not cleared because the 3 s cleanup budget ran out first. That is the pre-existing cleanup-budget residual, and the 60 s TTL covers it.
- **Sidebar per-row-set idempotence and manual steps.** Correct and accurate, as covered above.

### Spec compliance matrix (slice scope)
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Approval-gated config patch | Custom sidebar | `test_sidebar_patch > test_custom_claude_row_only_adds_tokens`, `test_tokens_in_any_row_noop_is_independent_per_target`, `test_backup_then_atomic_replace` | COMPLIANT |
| Single detached poller | Handoff re-run | `test_daemon > test_second_run_exits_zero_without_ticking`, `test_stop_request_during_slow_tick_ends_run_within_bound`, plus the E2-grow runtime | COMPLIANT |
| Stop and status actions | Stop | `test_daemon > test_stop_clears_published_persists_and_removes_pidfile`, `test_tick > test_stop_between_publish_actions_keeps_unapplied_for_retry` | COMPLIANT |
| Least privilege and safe logging | Content never stored | `test_log > test_sentinel_never_reaches_state_or_logs`, `test_tick > test_content_and_paths_never_reach_state_or_logs`, `test_state_store > test_file_key_allowlist` | COMPLIANT |
| Uninstall and documentation | Uninstall | `test_sidebar_patch > test_backup_then_atomic_replace`, `test_apply_missing_file_refuses_and_second_run_is_noop` (the README.md:37 text residual is W-6b-2) | COMPLIANT |
| State and retention | Pruning | `test_state_store > test_prune_removes_sessions_older_than_30_days`, `test_prune_sweeps_only_old_orphan_tmp_files`; `test_daemon > test_prune_at_startup_and_hourly` | COMPLIANT |
| Incremental tail | Growing file | `test_tick > test_total_grows_after_new_lines` (the edge case with disallowed names is W-6b-1) | COMPLIANT |
| Incremental tail | Truncation | `test_tail_ledger_integration > test_truncation_rescan_does_not_double_count`, `test_jsonl_tail > test_truncate_rescans_from_start` | COMPLIANT |

**Compliance summary**: 8/8 scenarios compliant.

### Mutation summary (16 mutants, full suite)
- KILLED (12): M1 last-row idempotence, M2 no non-table guard, M3 ignore `HERDR_CONFIG_PATH`, M4 no "uncomment", M6 no per-action stop check, M7 interrupted action not restored, M9 no parent fsync, M10 sweep fresh tmp files, M11 sweep `sessions/` only, M12 old relative-key check, M14 duplicate handler, M15 `is_stopping` always False.
- SURVIVED (4): M5 (no per-session stop check: the test cannot tell it apart, S-6b-2), M8 (`main.py:44` wiring removed: untested, but E2-grow proves the wiring at runtime, S-6b-3), M13 (equivalent), M16 (InterruptedError logged: untested, S-6b-4).

### Whole-change sanity pass
- README.md:11 says Python >= 3.11, which matches `main.py:5-7`. README.md:31 matches `sidebar_patch.py`. README.md:36 is correct. README.md:37 has the residual in W-6b-2. README.md:7 "writes only its state dir and Herdr pane metadata" leaves out the explicit `--apply` config write, but SECURITY.md:5 covers it.
- SECURITY.md:14 "atomic state writes" is now stronger with the parent fsync. SECURITY.md:21 (a handoff can fail) is still a valid residual but is now narrower: E2-grow succeeds. SECURITY.md:20 (pid-reuse window) is unchanged and accurate.
- tasks.md: the only open items are 5.3a and 6.4, both user-owned [APPROVAL]. 6.2 is checked with an accurate "not run against `~/.config/herdr`" note.

### Issues found
**CRITICAL**: None.

**WARNING**:
- W-6b-1 (new, candidate-caused): the file-key allowlist (`state_store.py:15,19-22`) is narrower than the locator glob (`claude_locator.py:58`) and the key builder (`tick.py:85-86`). One subagent file whose name contains a character outside `[A-Za-z0-9_.-]`, or one stale key from older state (carried forward by `tick.py:84`), makes `save_session` fail on every tick. Offsets and ledger never persist, every tick re-reads from the old offsets and logs `save_session_failed`, and a transcript larger than the read cap shows a permanently low total (probe: 250 vs 1.1k tokens). This is unreachable with known Claude naming. Fix options: skip disallowed subagent names in the locator or in tick (log once), and drop `files` keys that are not in the current `paths`.
- W-6b-2 (W3-R residual): README.md:37 still offers `python3 -B src/main.py stop` without `HERDR_PLUGIN_STATE_DIR`, and that exits 2. Reuse the wording from :36.
- W7 (carried): apply-progress #159 has no TDD Cycle Evidence table (no TRIANGULATE or SAFETY NET columns). The RED/GREEN claim itself was reproduced (19 failures + 2 errors, then 195 OK).

**SUGGESTION**:
- S-6b-1: `log.py:17-18` returns a logger bound to the first directory when it is called again with the same name and a different directory. Compare the handler's `baseFilename` and replace the handler when it differs. There is no production impact today.
- S-6b-2: `test_stop_during_sessions_aborts_tick_without_publishing` should assert that no transcript was read (for example, with `CountingTail.reads == []`) so that it kills M5.
- S-6b-3: add a test that `_build_poller` wires `svc.should_stop` to `poller.is_stopping` (kills M8).
- S-6b-4: `tick.py:49,55` uses the built-in `InterruptedError` as a control signal. A real EINTR `OSError` from herdr would then go unlogged, and M16 survives. Use a private exception or break out of the loop.
- S-6b-5 (carried, slice 5 S-R2, out of 6b scope): `main.py:99` still logs `cmd="start/stop"`, which the sanitizer turns into `cmd=?`.
- S-6b-6 (pre-existing): when the 3 s cleanup budget runs out, panes published by the interrupted tick are left to the 60 s TTL (E2-grow: p3). Consider mentioning this next to SECURITY.md:21.

### Verdict
PASS WITH WARNINGS. All 6b carry-overs are resolved with runtime and mutation evidence, except the README.md:37 residual. The suite passes 195/195, and E2-grow (W-R1) no longer reproduces. One new low-likelihood regression from the file-key allowlist (W-6b-1) should be fixed or accepted before archive. 5.3a and 6.4 remain user-owned.

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:6db5201b2c8166e26ea74b0bbb2b89f9d821cfa2a20b4d6651bcf2576e115d4b
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 7/7
scenarios: 8/8
test_command: python3 -B -m unittest discover
test_exit_code: 0
test_output_hash: sha256:be8320a5b7671100c9f4f8feaf4ce1b1880efc57c1d1e8a7aaf5ef7b103f2a22
build_command: python3 -B -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report (slice 6b re-verification after one bounded correction)

**Change**: agent-token-usage-mvp
**Candidate**: `git diff 3732258 3e49814` on branch `slice-6b-hardening` (commits 3dabe15 and 3e49814; 8 files, +66/-10). `evidence_revision` is the SHA-256 of that diff.
**Mode**: Strict TDD (`openspec/config.yaml:9`). This is a re-verification under the single-correction rule. It checks that the earlier findings are resolved and looks for regressions. New non-critical findings become carry-overs.
**Method**: The tests, build, probes and mutants ran in a `git archive 3e49814` copy under the session scratchpad with Homebrew Python 3.14.8 (`python3 -B`). The repository was not modified (`git status --short` is empty). No real `~/.config/herdr`, `~/.claude/projects`, herdr binary, socket, network or plugin link/enable was used. The shell `stop` fallback ran under `env -i` with a temp HOME and a temp state dir. Final `pgrep -fl "src/main.py"`: no output (exit 1).
**Scope of counts**: the same 7 requirements and 8 scenarios as the slice 6b report.

### Completeness
| Metric | Value |
|--------|-------|
| Tasks complete | 40 of 42 |
| Tasks incomplete | 2, both user-owned [APPROVAL]: 5.3a (tasks.md:79) and 6.4 (tasks.md:86) |

### Build and tests
- Tests: `python3 -B -m unittest discover` gives `Ran 199 tests ... OK` (exit 0). That is 195 plus 4 new tests, as expected.
- Build: `python3 -B -m compileall -q src tests` exits 0 with empty output (scratch copy only).
- Coverage: not available (stdlib only).

### Finding resolution
| Item | Status | Evidence |
|---|---|---|
| W-6b-1: allowlist vs. locator glob | PARTIAL | `mapping.py:6` defines `SUBAGENT_NAME`, which both `claude_locator.py:60` and `state_store.py:20-22` use. `tick.py:92` drops saved keys that are no longer located or not allowed. I re-ran the earlier probe with `max_read=300` and 12 ticks. **`agent-a b.jsonl`**: the subagent is skipped, the session saves with keys `["main"]`, and there are 0 `save_session_failed` lines. **Old state with a disallowed key and a gone key**: the total converges to "1.1k tokens", the keys become `[main, subagents/agent-ok1.jsonl]`, and there are 0 failures. **Remaining gap**: `state_store.py:22` also rejects names that contain `..`, but the shared regex and the locator accept them. With `agent-a..b.jsonl`, the session never saved (state `None`), there were 12 `save_session_failed` lines in 12 ticks, and the display was stuck at "200 tokens" instead of "1.1k tokens". See W-6b-1r. |
| W-6b-2: README.md:37 | RESOLVED | README.md:37 now gives `HERDR_PLUGIN_STATE_DIR=<state dir> python3 -B src/main.py stop`. Under `env -i` with a temp state dir, it prints `stopped` and exits 0. Without the variable it exits 2, which is why the variable is required. |
| S-6b-4: InterruptedError as a control signal | RESOLVED | `tick.py:17-18` adds a private `_StopRequested`, used at `tick.py:54,60`. A real `InterruptedError` from herdr is now logged as `apply_failed error=InterruptedError` (`test_real_interrupted_error_from_herdr_is_a_publish_failure_not_stop`). Mutant MC (also treat InterruptedError as a stop) is KILLED. |
| S-6b-1: make_logger with a different directory | RESOLVED | `log.py:18-23` replaces a handler whose `baseFilename` differs and keeps one with the same file (`test_make_logger_with_different_directory_replaces_handler`). Mutant MD (old early return) is KILLED. |

### Questions from the caller
- **Does dropping stale keys lose offsets for a file that is temporarily unlocatable?**
  - If `locate()` returns `None` (`tick.py:83-84`), the method returns before the drop. A failed read (`tick.py:96-100`) also returns before any save. In both cases the stored offsets are kept.
  - If only one subagent file is temporarily missing from the glob, `tick.py:92` drops its key in memory. That drop is persisted only when the same tick is dirty for another reason. Probe P3b (missing file, nothing else changed) kept the key, and 0 bytes were re-read afterwards.
  - Probe P3 (missing file while main grows) persisted `[main]`. When the file came back, it was re-read from offset 0: 226,890 bytes, the whole file, read once. The total stayed correct (20.1k, then 20.2k, then 20.2k) because the ledger is idempotent (`ledger.py:9-12`, field-wise max) and its entries are not dropped with the key. A disappearing file therefore never lowers the total.
  - Cost: one full re-read of that file, bounded by `MAX_READ` = 4 MiB per file per tick (`jsonl_tail.py:9`), spread over later ticks for larger files. There is no double count. This is acceptable.
- **Does the SUBAGENT_NAME change affect attribution security?**
  - No. `claude_locator.py:60` still requires all of the following: the realpath is under the projects root and is a file (`:27-29`), `real.parent.name == "subagents"`, and `real.parent.parent.name == session_id`. The new rule narrows the old glob check.
  - Probe P4 tried three symlinks: to another session's `subagents/agent-z.jsonl`, to a file outside the root, and to a nested `subagents/nested/agent-n.jsonl`. `locate()` returned `[]` for all three, and the total stayed "100 tokens" (main only).
  - File keys are dictionary labels only. They are never used as filesystem paths (`tick.py:89,106`, `state_store.py:26`).

### Mutation summary (7 mutants, full suite)
- KILLED (4): MA (no stale-key drop), MB (locator back to the glob match), MC (InterruptedError treated as a stop), MD (old logger early return).
- SURVIVED (3):
  - ME (drop `and file_key_allowed(k)` at `tick.py:92`): effectively equivalent. Located keys already pass the shared rule, except `..` names, which fail at save either way.
  - MF (no `old.close()` at `log.py:22`): the replaced handler's file descriptor leaks. Untested and low impact.
  - MG (remove `".." not in name` at `state_store.py:22`): survives because no test uses a `..` name. This is the W-6b-1r gap.

### Spec compliance matrix (slice scope, unchanged plus new tests)
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Approval-gated config patch | Custom sidebar | `test_sidebar_patch > test_custom_claude_row_only_adds_tokens` | COMPLIANT |
| Single detached poller | Handoff re-run | `test_daemon > test_second_run_exits_zero_without_ticking` | COMPLIANT |
| Stop and status actions | Stop | `test_daemon > test_stop_clears_published_persists_and_removes_pidfile`, `test_tick > test_real_interrupted_error_from_herdr_is_a_publish_failure_not_stop` | COMPLIANT |
| Least privilege and safe logging | Content never stored | `test_log > test_sentinel_never_reaches_state_or_logs`, `test_state_store > test_file_key_allowlist` | COMPLIANT |
| Uninstall and documentation | Uninstall | `test_sidebar_patch > test_backup_then_atomic_replace`, plus README.md:37 runtime check | COMPLIANT |
| State and retention | Pruning | `test_state_store > test_prune_removes_sessions_older_than_30_days` | COMPLIANT |
| Incremental tail | Growing file | `test_tick > test_total_grows_after_new_lines`, `test_disallowed_subagent_name_is_ignored_and_session_still_saves`, `test_old_disallowed_file_key_is_dropped_and_session_saves` | COMPLIANT (with the W-6b-1r edge case) |
| Incremental tail | Truncation | `test_tail_ledger_integration > test_truncation_rescan_does_not_double_count` | COMPLIANT |

**Compliance summary**: 8/8 scenarios compliant.

### Issues found
**CRITICAL**: None.

**WARNING**:
- W-6b-1r (carry-over, residual of W-6b-1): `mapping.py:6` (`SUBAGENT_NAME`) and `claude_locator.py:60` accept subagent names that contain `..`, such as `agent-a..b.jsonl`. `state_store.py:22` rejects them, so the "one rule" is still split. With such a file, `save_session` fails on every tick, offsets never persist, and a transcript larger than the read cap shows a stuck low total (probe: 200 instead of 1.1k tokens). Known Claude subagent names (`agent-<hex>`) never contain `..`, so the risk is low. Fix: move the `..` exclusion into the shared rule (a helper in `mapping.py` used by both callers), or drop it from the store, since keys are never used as paths. Add a test with a `..` name, which would kill MG.
- W7 (carried): apply-progress has no TDD Cycle Evidence table.

**SUGGESTION**:
- S-6b-7 (new): skipped subagents are not logged. A file such as `agent-a b.jsonl` is dropped silently and the total excludes it. Consider logging the skip once per session.
- S-6b-8 (new): no test asserts that the replaced handler is closed (`log.py:22`), so mutant MF survives.
- S-6b-2, S-6b-3, S-6b-5 and S-6b-6: carried unchanged from the slice 6b report.

### Verdict
PASS WITH WARNINGS. W-6b-2, S-6b-4 and S-6b-1 are resolved with runtime and mutation evidence. W-6b-1 is resolved for the reported cases (odd names, stale and disallowed old keys), but `..` names still show the old failure mode (W-6b-1r, low likelihood), carried over under the single-correction rule. Stale-key dropping keeps the total correct; at worst it costs one bounded full re-read of the file. Attribution containment is unchanged. Tests pass 199/199. 5.3a and 6.4 remain user-owned.
