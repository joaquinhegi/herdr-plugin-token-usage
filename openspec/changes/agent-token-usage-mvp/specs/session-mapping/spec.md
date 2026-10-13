# Session Mapping Specification

## Purpose
Strict pane-to-session resolution. Never attribute another session's usage.

## Requirements

### Requirement: Strict Claude resolution (RF01, C1, C2)
A pane MUST map only via its Herdr `agent_session` (`kind: id`, UUID) to `<uuid>.jsonl` plus `<uuid>/subagents/agent-*.jsonl`. Working directory MUST NOT be used.

#### Scenario: Same repo, two sessions
- GIVEN two Claude panes in one cwd with different UUIDs
- WHEN resolved
- THEN each maps to its own files

#### Scenario: Subagents included
- GIVEN a session with subagent transcripts
- WHEN resolved
- THEN subagent files belong to the parent session

### Requirement: No reliable session, no figure (C10)
If `agent_session` is missing, malformed, ambiguous or its file is absent or inaccessible, the pane MUST show nothing and a technical diagnostic MUST be logged.

#### Scenario: Missing file
- GIVEN a valid UUID with no transcript
- WHEN polled
- THEN `tokens` is cleared, never `0`, and a diagnostic is logged

### Requirement: Codex panes unmapped
The MVP MUST NOT map Codex panes or touch `~/.codex`; Codex panes show nothing (C2).

#### Scenario: Codex pane
- GIVEN a Codex pane beside a Claude pane
- WHEN polled
- THEN only the Claude pane shows a figure

### Requirement: Session change and resume (RF01, C4, C5)
The plugin MUST follow the session id Herdr reports. A new id MUST start a fresh counter and clear the old value; a resumed id MUST recover its counter, with copied history deduped by `message.id`.

#### Scenario: New session in same pane
- GIVEN a pane reporting UUID A then UUID B
- WHEN B appears
- THEN A's value is cleared and B starts from B's own usage

#### Scenario: Resume after restart
- GIVEN a persisted counter for A
- WHEN Herdr restarts reporting A
- THEN the same total is shown
