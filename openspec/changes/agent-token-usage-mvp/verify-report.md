```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:cb39e6b31f5d4dfb3a524542ddba89320d8378e90f2b519dff41cc944f04a3ec
verdict: fail
blockers: 1
critical_findings: 1
requirements: 4/4
scenarios: 5/6
test_command: python3 -m unittest discover -v
test_exit_code: 0
test_output_hash: sha256:a62a5ed4c42c01cfdee610c1ff7b7171af8255f65909b1ec919497b3c103ac18
build_command: python3 -m compileall -q src tests
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: agent-token-usage-mvp
**Section**: Slice 1 (tasks 1.0-1.7): domain + parsers
**Candidate**: branch `slice-1-domain`, commit `419482c` (tree `7f8eda6`) over `main` `720c2cc`
**Mode**: Strict TDD
**Scope note**: The envelope counts cover only slice-1 requirements and scenarios: 4 requirements and 6 scenarios. The full change has 17 requirements and 26 scenarios across 4 specs. Requirements for later slices are listed as deferred, not as failures.

### Completeness (slice 1)
| Metric | Value |
|--------|-------|
| Tasks total (slice 1) | 8 (1.0-1.7) |
| Tasks complete | 8 |
| Tasks incomplete | 0 |
| Later-slice tasks (2.x-6.x) | Unchecked, out of scope |
| Changed lines | 414 insertions + 8 deletions = 422. The maintainer accepted this against the 400-line budget. |

### Build & Tests Execution
**Build**: Passed (`python3 -m compileall -q src tests`, exit 0, empty output)
**Tests**: 23 passed / 0 failed / 0 skipped (`python3 -m unittest discover -v`, exit 0, Python 3.14.8). `python3 -m unittest discover -s tests/unit` also reports 23 OK.
**Coverage**: Not available. The `coverage` module is not installed.

### Spec Compliance Matrix (slice-1 scope)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Formatting (RF05) | Examples (950, 1250, 125400, 1200000) | `test_formatting > FormatTokensTest.test_spec_examples`, `test_boundaries`, `test_max_length` | COMPLIANT |
| Total definition (RF02) | Sum = 135 (thinking 8 not re-added) | `test_formatting > UsageCallTest.test_thinking_not_added_again`, `test_parsers > test_basic_total_and_thinking_not_added` | COMPLIANT |
| Claude per-call dedupe | Repeated lines | `test_ledger > test_repeated_id_counts_once`, `test_parsers > test_duplicates_and_request_id_fallback` | COMPLIANT |
| Claude per-call dedupe | Replay | `test_ledger > test_replay_leaves_total_unchanged`, `test_parsers > test_resume_copy_and_replay_do_not_double_count` | COMPLIANT |
| Claude per-call dedupe | Three prompts (monotonic growth when polled after each) | `test_ledger > test_distinct_ids_accumulate`, `test_parsers > test_resume_copy_and_replay_do_not_double_count` (one growth step only) | PARTIAL |
| Codex cumulative parsing | Snapshots 100, 250, 250 -> 250 | `test_parsers > CodexParserTest.test_snapshots_use_latest_not_sum`, `test_null_info_ignored` | COMPLIANT |

**Compliance summary**: 5/6 slice-1 scenarios compliant and 1 partial.

**Deferred to later slices (not failures)**:
- Total definition, "README MUST document this": deferred to slice 6 (task 6.3).
- Claude dedupe, "Totals MUST persist across compaction/restart": persistence deferred to slice 2 (state store). End-to-end polling deferred to slice 4 (scenario tests).
- Incremental tail (Growing file, Truncation): slice 2.
- State and retention (Pruning): slice 2.
- Session mapping (all requirements, including "Subagents included"): slice 3.
- Publish and clear (Unchanged value, Pane closed, Herdr unreachable): slice 4.
- Approval-gated config patch: slice 6.
- Plugin lifecycle (all requirements): slice 5.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Formatting | Implemented | Integer round-half-up. 1250 -> `1.3k tokens` and 1249 -> `1.2k tokens`. 999949 -> `999.9k tokens`. 999950 rolls over to `1.0M tokens` because the k branch checks `tenths < 10_000`. The output stays within 80 characters for 10**30. Internal values stay integers. |
| Total definition | Implemented | `UsageCall.total = input + output + cache_creation + cache_read`. `thinking` is informational only. |
| Claude per-call dedupe | Implemented | The key is `message.id`, with `requestId` as fallback. The ledger takes the field-wise max and updates the total incrementally. `<synthetic>` model, `isApiErrorMessage`, id-less, non-assistant, malformed, bool, and negative counts are skipped. Subagent lines (`isSidechain: true`) are not filtered. An ad hoc probe confirmed they parse, which matches the design decision of one shared ledger. |
| Codex cumulative parsing | Implemented (assumption) | The parser uses the latest `total_token_usage` and never sums snapshots. Null `info` is ignored. An identical re-emission does not change the latest value. If there are no snapshots, the result is `None`, not 0. The total is `input + output`. See the WARNING about this assumption. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Pure `sources/` (dict -> UsageCall/CodexSnapshot/None) | Yes | No I/O in the parsers. |
| Ledger: message.id -> requestId, field-wise max, incremental total | Yes | `Ledger.from_entries` is ready for slice-2 restore. |
| Subagents share one session ledger | Yes (parser side) | No subagent fixture or test exists yet. See WARNING. |
| Fixture list (design line 103) | Partial | `partial_tail.jsonl` and `<uuid>/subagents/agent-a.jsonl` are absent. Task 1.5 did not list them, and they belong to slices 2 and 3. |
| Open question: Codex output includes reasoning (design line 112) | Inconsistent | design.md still lists this question as open. The `codex.py` docstring says "open question resolved". |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Missing | apply-progress (#159) has only a prose claim ("RED (module missing) -> GREEN ... triangulated"). It has no "TDD Cycle Evidence" table. |
| All tasks have tests | Yes | 1.1/1.2 -> test_formatting.py, 1.3/1.4 -> test_ledger.py, 1.5-1.7 -> test_parsers.py |
| RED confirmed (tests exist) | Yes | 3/3 test files exist. RED cannot be confirmed from history because the slice is a single commit. |
| GREEN confirmed (tests pass) | Yes | 23/23 pass on execution |
| Triangulation adequate | Yes | Formatting: 4 spec values + 6 boundaries. Ledger: 7 cases. Parsers: 10 cases. |
| Safety Net for modified files | Yes | All source and test files are new. The only modified file is tasks.md (checkboxes). |

**TDD Compliance**: 5/6 checks passed (evidence table missing)

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 23 | 3 | unittest |
| Integration | 0 | 0 | not applicable in slice 1 |
| E2E | 0 | 0 | not installed |
| **Total** | **23** | **3** | |

### Changed File Coverage
Coverage analysis skipped. No coverage tool was detected (`coverage` is not installed).

### Assertion Quality
**Assertion quality**: All assertions verify real behavior. There are no tautologies, ghost loops, or orphan empty checks. `test_no_snapshots_is_none_not_zero` has non-None companions. All subTest loops iterate over non-empty literals.

### Quality Metrics
**Linter**: Not available
**Type Checker**: Not available

### Fixture Hygiene
All fixtures are synthetic. The model is `claude-synth-1`, and ids look like `msg_1` and `req_1`. Content and cwd fields use `SENTINEL_SECRET_PROMPT_TEXT`. `rg` found no absolute paths, usernames, or real content under `tests/`.

### Issues Found
**CRITICAL**:
1. Strict TDD protocol: apply-progress (`sdd/agent-token-usage-mvp/apply-progress`, #159) has no "TDD Cycle Evidence" table (RED/GREEN/TRIANGULATE/SAFETY NET/REFACTOR per task). The strict-tdd-verify module treats a missing table as CRITICAL. Remediation affects artifacts only: backfill the table in apply-progress. No code change is needed, because tests exist, pass, and are well triangulated.

**WARNING**:
1. The Codex total is an assumption to verify. `total = input_tokens + output_tokens` relies on two things. First, cached tokens are inside input: explore.md only says "reportedly". Second, reasoning is inside output: design.md line 112 still lists this as an open question. The code and tests encode the assumption without proving it. Two more gaps exist. explore.md lists `cache_write_input_tokens` in Codex `TokenUsage`, and the parser ignores it. The parser also ignores the upstream `total_tokens` field. An ad hoc probe with `{input:10, output:5, cache_write_input_tokens:7, total_tokens:22}` produced 15. The risk is low for the MVP because Codex is fixture-only and has no pane mapping, but the open question should stay tracked. Also, design.md and the code docstring disagree about whether it is resolved.
2. The "Three prompts" scenario is only partially covered. No test polls after each of three successive responses and asserts monotonic growth at each step. The end-to-end form is expected in slice 4 (task 4.3).
3. No fixture or test exercises a subagent line (`isSidechain: true`) to show it is counted rather than skipped. The behavior is correct (probe), but nothing guards it against regression. It may be covered in slice 3 (task 3.4).

**SUGGESTION**:
1. Claude: one malformed `output_tokens_details.thinking_tokens` (for example, a string) drops the whole line. Thinking is informational, so you could ignore the bad field and keep the counts.
2. Claude: `message.id` and `requestId` share one key namespace. A duplicate line where `message.id` is missing but `requestId` matches an earlier id-bearing line is counted twice (probe: 5 + 5 = 10). This is unlikely in real transcripts, so a note in the design is enough.
3. Codex: when `total_tokens` is present and differs from `input + output`, consider cross-checking it or logging the difference. This would settle WARNING 1 empirically.
4. Add `coverage` as an optional dev tool so changed-file coverage can be reported.

### Verdict
FAIL (artifact-only). The slice-1 code is functionally sound: 23/23 tests pass, all slice-1 scenarios are compliant except one partial, and the fixtures are synthetic. However, the Strict TDD evidence table is missing from apply-progress, which the strict-tdd-verify module treats as CRITICAL. Backfill the table and re-verify. No source change is needed.
