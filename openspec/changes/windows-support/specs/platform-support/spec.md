# Platform Support Specification

## Purpose
Supported OSes, per-OS adapters, launcher, manifest ids and Herdr transport. POSIX (Linux/macOS) behavior is unchanged by this capability.

## Requirements

### Requirement: Platform adapter selection
`main.py` MUST select a POSIX adapter on POSIX and a Windows adapter on Windows. Each adapter MUST cover lock, spawn, stop request/check, signal install and liveness. The POSIX adapter MUST preserve current behavior (flock, SIGTERM, `start_new_session`).

#### Scenario: Windows selection
- GIVEN the OS is Windows
- WHEN `main.py` starts
- THEN the Windows adapter is used and `fcntl` is never imported

#### Scenario: POSIX selection
- GIVEN the OS is Linux or macOS
- WHEN `main.py` starts
- THEN the POSIX adapter is used and behavior matches the pre-change baseline

### Requirement: Windows single-instance lock
The Windows adapter MUST lock `poller.lock` non-blockingly (`msvcrt.locking`), keep the pid outside the locked byte range, and release the lock on process death.

#### Scenario: Second instance
- GIVEN a poller holds the lock
- WHEN another start attempts the lock
- THEN it fails without starting a poller and the pid is still readable

#### Scenario: Crashed holder
- GIVEN the holder died
- WHEN start runs
- THEN the lock is acquired and a new poller starts

### Requirement: Windows spawn
The Windows adapter MUST spawn the poller with `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` and MUST NOT use `DETACHED_PROCESS`. Herdr CLI calls MUST use `CREATE_NO_WINDOW`.

#### Scenario: Spawn flags
- GIVEN the Windows adapter
- WHEN it spawns the poller or runs a CLI call
- THEN the creation flags above are passed and no console window appears

### Requirement: Windows liveness without signals
On Windows, liveness MUST be determined by probing the lock. The plugin MUST NOT call `os.kill(pid, 0)` (or any `os.kill`) for liveness on Windows.

#### Scenario: Liveness probe
- GIVEN a live poller holding the lock
- WHEN status checks liveness
- THEN it reports alive via the lock probe and no process is signalled

### Requirement: Launcher and manifest
The manifest MUST declare top-level `platforms` including `windows`. It MUST define `start-windows`, `stop-windows` and `status-windows` items with item-level `platforms = ["windows"]` and argv `["py","-3","-X","utf8","-B","src/main.py",...]`. POSIX items MUST keep `python3`, MUST be POSIX-only, and ids MUST be unique across platforms.

#### Scenario: Manifest
- GIVEN `herdr-plugin.toml`
- WHEN parsed
- THEN Windows items use `py -3`, POSIX items use `python3`, and all ids are distinct

### Requirement: CLI-only Herdr transport on Windows
On Windows the plugin MUST NOT build the `AF_UNIX` socket client and MUST use the Herdr CLI for reads and writes. `FallbackHerdr` MUST catch `AttributeError` in addition to `HerdrError`/`OSError` on all OSes and fall back to the CLI.

#### Scenario: No AF_UNIX
- GIVEN `socket.AF_UNIX` is absent
- WHEN panes are listed
- THEN the CLI is used and no crash occurs

#### Scenario: AttributeError on POSIX
- GIVEN the socket client raises `AttributeError`
- WHEN panes are listed
- THEN the CLI fallback is used

### Requirement: Atomic state replace retry
`os.replace` of state files MUST be retried a bounded number of times on `PermissionError` before the error propagates.

#### Scenario: Transient sharing violation
- GIVEN the target is briefly open elsewhere
- WHEN state is saved
- THEN the replace succeeds on retry

#### Scenario: Persistent failure
- GIVEN `PermissionError` on every attempt
- WHEN retries are exhausted
- THEN the error propagates and no partial state file is left

### Requirement: CI and documentation status
CI MUST run ubuntu, macos and windows on Python 3.11 and 3.13. Docs MUST mark Windows "experimental" until manual validation passes, and MUST state the `py` prerequisite and the detached-process risk.

#### Scenario: Matrix
- GIVEN the workflow
- WHEN a PR opens
- THEN 6 jobs run the unittest suite
