# Delta for Plugin Lifecycle

POSIX behavior unchanged. Baseline: agent-token-usage-mvp `plugin-lifecycle`.

## MODIFIED Requirements

### Requirement: Single detached poller (RF03, S1)
The plugin MUST start one self-detached poller from `[[startup]]` and via a start action, guarded by a pidfile (and, on Windows, the lock). It MUST poll every 3-5 s, work offline, and use only the Python standard library. On Windows at most one poller MUST run at any time.
(Previously: no Windows single-poller guarantee.)

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

#### Scenario: Windows concurrent starts
- GIVEN Windows and two simultaneous start requests
- WHEN both run
- THEN exactly one poller remains running

### Requirement: Stop and status actions
The plugin MUST expose start, stop and status actions. Stop MUST terminate only the pidfile process and clear its own pane metadata. On POSIX stop MUST send SIGTERM after pidfile/lock identity match. On Windows stop MUST create a stop request polled by the poller loop, which exits and clears published tokens as POSIX does. If the poller has not exited after 8 s, Windows stop MAY call TerminateProcess only if the lock holder and pidfile identity match; otherwise it MUST NOT terminate anything. While a stop request is pending, Windows status MUST report "stopping" (POSIX status MAY). Windows stop MUST NOT use `os.kill(pid, 0)`.
(Previously: stop semantics were signal-only and status had no "stopping" state.)

#### Scenario: Stop
- GIVEN a running poller
- WHEN stop runs
- THEN the process exits and `tokens` is cleared on tracked panes

#### Scenario: Windows cooperative stop
- GIVEN a running Windows poller
- WHEN stop runs
- THEN the poller sees the stop request, clears tokens, exits, and status reports not running

#### Scenario: Stopping status
- GIVEN Windows and a stop request pending
- WHEN status runs
- THEN it reports "stopping", not "running"

#### Scenario: Forced termination
- GIVEN the poller ignores the stop request for 8 s and identity matches
- WHEN stop's timeout elapses
- THEN the poller is terminated

#### Scenario: Pid reuse guard
- GIVEN the pidfile pid now belongs to an unrelated process (lock not held by it)
- WHEN the timeout elapses
- THEN no process is terminated and the stale request is cleared
