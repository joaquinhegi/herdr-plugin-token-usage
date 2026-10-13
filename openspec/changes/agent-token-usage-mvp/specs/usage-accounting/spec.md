# Usage Accounting Specification

## Purpose
Provider parsers, dedupe and incremental state. Cost is out of scope.

## Requirements

### Requirement: Total definition (RF02)
Total MUST be input + output + cache_creation + cache_read as integers; thinking tokens (inside output) MUST NOT be added again. README MUST document this.

#### Scenario: Sum
- GIVEN one call with input 10, output 20, cache_creation 5, cache_read 100, thinking 8
- WHEN totaled
- THEN the total is 135

### Requirement: Claude per-call dedupe (RF02, C3, C6, C7)
The Claude parser MUST count each `message.id` once (fallback `requestId`, keeping the max usage per id) and skip `<synthetic>` and API-error lines. Totals MUST persist across prompts and compaction.

#### Scenario: Repeated lines
- GIVEN three lines share one `message.id` with identical usage
- WHEN parsed
- THEN usage counts once

#### Scenario: Replay
- GIVEN an already-processed file is re-read
- WHEN polled
- THEN the total is unchanged

#### Scenario: Three prompts
- GIVEN three successive responses
- WHEN polled after each
- THEN the total grows monotonically

### Requirement: Codex cumulative parsing (RF02, C8)
The Codex parser MUST use the latest cumulative `total_token_usage` and MUST NOT sum snapshots; null `info` and identical re-emissions are ignored. Fixture-tested only.

#### Scenario: Snapshots
- GIVEN snapshots totaling 100, 250, 250
- WHEN parsed
- THEN the result is 250

### Requirement: Incremental tail (RF03, C9)
The plugin MUST keep per-file offsets, read only new bytes, ignore an incomplete trailing line until completed, and rescan on rotation or truncation.

#### Scenario: Growing file
- GIVEN a half-written final line
- WHEN polled, then completed and polled
- THEN the line is counted exactly once

#### Scenario: Truncation
- GIVEN the file shrinks below the stored offset
- WHEN polled
- THEN it is rescanned without double-counting known ids

### Requirement: State and retention (RF01, S7)
State MUST hold only ids, offsets and counters in the state dir, and survive restart. Closed-session counters MUST be retained 30 days, then pruned.

#### Scenario: Pruning
- GIVEN a closed session idle for over 30 days
- WHEN pruning runs
- THEN its counters are deleted
