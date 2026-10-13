# Plugin Lifecycle Specification

## Purpose
Manifest, detached poller, safety and uninstall. Refs: S=security requirement, C=acceptance case.

## Requirements

### Requirement: Single detached poller (RF03, S1)
The plugin MUST start one self-detached poller from `[[startup]]` and via a start action, guarded by a pidfile. It MUST poll every 3-5 s, work offline, and use only the Python standard library.

#### Scenario: Handoff re-run
- GIVEN a live poller with a valid pidfile
- WHEN the startup hook runs again
- THEN no second poller starts

#### Scenario: Stale pidfile
- GIVEN a pidfile whose process is dead
- WHEN start runs
- THEN a new poller starts and the pidfile is replaced

#### Scenario: No connectivity (C13)
- GIVEN no network
- WHEN Herdr restarts
- THEN the poller runs and publishes locally

### Requirement: Stop and status actions
The plugin MUST expose start, stop and status actions. Stop MUST terminate only the pidfile process and clear its own pane metadata.

#### Scenario: Stop
- GIVEN a running poller
- WHEN stop runs
- THEN the process exits and `tokens` is cleared on tracked panes

### Requirement: Fault isolation (C12)
A failure parsing one session MUST NOT stop processing of other sessions; the error is logged technically.

#### Scenario: Corrupt transcript
- GIVEN session A's file is unreadable and B's is valid
- WHEN a poll cycle runs
- THEN B is published and A shows nothing

### Requirement: Least privilege and safe logging (S2-S8)
The plugin MUST read only agent transcript files, write only to `HERDR_PLUGIN_STATE_DIR` and Herdr metadata, never edit Claude/Codex settings or hooks, run subprocesses without a shell using structured arguments, and persist only ids, offsets and counters. Logs MUST contain no conversation content.

#### Scenario: Content never stored
- GIVEN a transcript with message text
- WHEN state and logs are inspected after polling
- THEN no prompt or response text appears

### Requirement: Uninstall and documentation (S9, S10)
Docs MUST list inspected directories and why, and install/reload/log/disable/uninstall steps. Uninstall MUST remove only plugin metadata and state, and revert only plugin config changes.

#### Scenario: Uninstall
- GIVEN an applied sidebar patch
- WHEN the documented rollback runs
- THEN only the plugin's changes are reverted
