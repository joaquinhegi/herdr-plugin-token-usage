# Design: Windows Support

## Technical Approach

Move every OS-specific lifecycle primitive out of `daemon.py` behind a `HostPlatform` port. `PosixHost` reproduces current behavior byte for byte; `WindowsHost` uses `msvcrt.locking`, a stop file and a guarded `TerminateProcess`. `main.py` selects the adapter by `os.name`. The detached poller stays (known risk), started with `CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW`.

## Architecture Decisions

| Topic | Choice | Rejected | Rationale |
|---|---|---|---|
| Seam | `HostPlatform` Protocol in `ports.py`; `lifecycle/host_posix.py`, `lifecycle/host_windows.py` | `if os.name` inside `daemon.py` | Testable by injection; POSIX untouched |
| Windows lock | `msvcrt.locking(fd, LK_NBLCK, 1)` on byte 0 after `lseek(0)`; holder pid written as ASCII at offset `PID_OFFSET = 16`; release = `LK_UNLCK` then close | pid in locked range; pid only in pidfile | Locked bytes are unreadable to others; offset 16 stays readable, so holder identity survives |
| Windows liveness | Lock probe only | `os.kill(pid, 0)` (kills), `tasklist` | Lock dies with the process |
| Windows stop | `poller.stop` file, wait `WAIT_S`, then guarded `TerminateProcess` | Ctrl events (do not cross hidden consoles) | Only reliable cross-console request |
| Spawn | `creationflags=CREATE_NEW_PROCESS_GROUP\|CREATE_NO_WINDOW`, argv `[sys.executable, "-X", "utf8", "-B", main, "run"]` | `DETACHED_PROCESS` | No console flash on child `herdr.exe` calls |
| Transport | Windows: CLI only (`supports_socket = False`); `FallbackHerdr` also catches `AttributeError` (all OSes) | named-pipe client | Out of scope; CLI already sufficient |
| Atomic writes | `adapters/atomic.py: replace_with_retry` (PermissionError only, 5 tries, 0.05 s doubling, ≤1.6 s), used by `StateStore` and `_write_pidfile` | unbounded retry | Sharing violations are transient |
| Herdr bin on Windows | `HerdrCli` rejects non-`.exe` paths on Windows | allow `.cmd/.bat` | Batch files route argv through `cmd.exe` |

## Interfaces / Contracts

```python
class HostPlatform(Protocol):
    supports_socket: bool
    stop_poll_s: float | None          # None = signals wake the loop (POSIX)
    def acquire_lock(self, d: Path) -> object | None: ...   # non-blocking
    def record_identity(self, h, pid: int) -> None: ...
    def release(self, h) -> None: ...                       # wipe identity, unlock, close
    def held(self, d: Path) -> bool: ...                    # probe; winner wipes stale identity
    def holder_pid(self, d: Path) -> int | None: ...
    def spawn(self, argv_tail: list[str]) -> None: ...
    def request_stop(self, d: Path, verified_pid: int | None, started_at: float | None = None) -> None: ...
    def stop_requested(self, d: Path) -> bool: ...
    def clear_stop(self, d: Path, own: tuple[int, float] | None = None) -> None: ...  # own=(pid, started_at): keep a request naming it
    def force_terminate(self, d: Path, pid: int, started_at: float) -> bool: ...
    def install_signal_handlers(self, on_stop) -> None: ...
```

| Method | POSIX | Windows |
|---|---|---|
| request_stop | `kill(pid, SIGTERM)` iff verified | write `d/poller.stop` = `{pid, started_at}` of the target |
| stop_requested / clear_stop | False / no-op | `exists()` / unlink; with `own`, keeps a file naming exactly `own` |
| force_terminate | False (current behavior) | guard below, then `TerminateProcess` |
| install_signal_handlers | TERM/INT → stop, HUP ignored | INT, BREAK → stop; no HUP |

`verified_pid` (daemon): pidfile pid == `holder_pid`, > 1, != own pid, and `held()` is True.

Windows `force_terminate` guard: re-verify `verified_pid`; `OpenProcess(PROCESS_TERMINATE|PROCESS_QUERY_LIMITED_INFORMATION)` via `ctypes`; `GetProcessTimes` creation time ≤ pidfile `started_at` and within 60 s of it; `TerminateProcess` on that same handle (handle pins the object, no TOCTOU); close handle. Any mismatch → False.

## Data Flow

```
stop (Windows): held? ─no─► "stopped"
        └yes─► touch poller.stop ─► wait ≤8 s for lock free ─► free: "stopped"
                                       └ not free ─► force_terminate ─► wait 2 s ─► "stopped" | "failed"
poller: lock ─► record_identity ─► clear_stop ─► loop ─► exit: cleanup ─► clear_stop ─► release
```

Stop checks: `Poller.is_stopping()` = `_stop.is_set() or host.stop_requested(dir)` (sets `_stop` when true). `TickService.should_stop` already points at it, so a stop is honored between panes. Between ticks, `_wait(interval)` sleeps in `stop_poll_s` (0.5 s) slices checking `is_stopping()`; POSIX keeps a single `_stop.wait(interval)`. Stale stop files: only `stop` creates one, naming the target `{pid, started_at}`; the poller deletes it on startup (after taking the lock) unless it names this poller, and unconditionally on exit. `status` → `stopping pid=… ` when held and `stop_requested`.

Injection: `daemon.start/stop/status(..., host=)` and `Poller(..., host=)`; `PosixHost(popen=, kill=)` keeps existing test fakes; `tests/lifecycle/fake_host.py` provides `FakeHost` with recorded calls.

## File Changes

| File | Action |
|---|---|
| `src/token_usage/ports.py` | Add `HostPlatform` |
| `src/token_usage/lifecycle/host_posix.py`, `host_windows.py` | Create |
| `src/token_usage/lifecycle/daemon.py` | Use host; `stopping` status; force-terminate step |
| `src/token_usage/adapters/atomic.py` | Create (`replace_with_retry`) |
| `src/main.py` | Select host; no `HerdrSocket` when `not supports_socket` |
| `herdr_fallback.py`, `herdr_cli.py`, `state_store.py` | AttributeError; `CREATE_NO_WINDOW` + `.exe` + test `launcher` prefix; retry |
| `sidebar_patch.py` | Config path order: `HERDR_CONFIG_PATH` > `XDG_CONFIG_HOME/herdr/config.toml` > `%APPDATA%\herdr\config.toml` (nt) > `~/.config/herdr/config.toml` |
| `herdr-plugin.toml` | Top-level `platforms = ["linux","macos","windows"]`; POSIX items `platforms=["linux","macos"]`; `start-windows`/`stop-windows`/`status-windows` + Windows startup, argv `["py","-3","-X","utf8","-B","src/main.py",…]` |
| `tests/**`, `.github/workflows/ci.yml` | Portability, CI |
| `README.md`, `docs/SECURITY.md` | Windows (experimental) |

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | daemon flows, stop file, stopping status, guard refusals | `FakeHost`; runs on every OS |
| Unit | `PosixHost` | existing tests, `skipUnless(os.name == "posix")`, `fcntl` imported inside guarded class |
| Unit | `WindowsHost` lock/offset/stop file/terminate guard | `skipUnless(os.name == "nt")`; real child `[sys.executable, "-c", …]` |
| Unit | `HerdrCli` | fake herdr as `launcher=[sys.executable]`, `bin=fake.py`; flags asserted via patched `subprocess.run` |
| Integration | `TestRealSpawn` | POSIX only; Windows envs must include `SYSTEMROOT` |
| Manual | user's Windows PC checklist | install, start, status, sidebar, stop leaves no process |

`herdr_fakes.FakeServer` and `/tmp` users skip on non-POSIX; `tempfile.mkdtemp()` without `dir`.

CI: `on: [push, pull_request]`, `permissions: contents: read`, no secrets, actions pinned by SHA, `persist-credentials: false`; matrix `ubuntu-latest, macos-latest, windows-latest` × `3.11, 3.13`; step `python -B -m unittest discover -v`.

## Threat Matrix

| Boundary | Applicability | Response | RED tests |
|---|---|---|---|
| Documentation-like paths / Git / commit / push / PR | N/A: no VCS or classification logic | — | — |
| TerminateProcess pid reuse | Applicable | identity + held lock + creation-time guard; same handle | mismatched pid, unheld lock, creation time after `started_at` → no terminate |
| Stop file | Applicable | fixed name in state dir only; content ignored; deleted at startup/exit | stale file at startup removed; status `stopping` |
| Console windows | Applicable | `CREATE_NO_WINDOW` on spawn and every CLI call | flags asserted on Windows |
| Herdr bin via cmd.exe | Applicable | `.exe` required on Windows | `.cmd` rejected |
| `py` resolution | Applicable (doc) | Herdr PATH lookup; documented prerequisite | manifest test |

## Slice Plan (≤400 lines each)

| # | Content | Est. lines |
|---|---|---|
| 1 | Port, `PosixHost`, daemon refactor, `atomic.py`, AttributeError fix; no behavior change | ~330 |
| 2 | `WindowsHost`, stopping status, force-terminate step, CLI flags/.exe, main selection, manifest + manifest test | ~380 |
| 3 | Test portability, `FakeHost` cross-OS tests, CI workflow | ~300 |
| 4 | Sidebar-patch path, README/SECURITY, experimental notes | ~150 |

## Migration / Rollout

No data migration. Windows marked experimental until the manual checklist passes. Rollback: revert the slice.

## Open Questions

- [ ] Confirm `.exe`-only `HERDR_BIN_PATH` on Windows (added hardening).
- [ ] Creation-time window (60 s) acceptable for the terminate guard.
- [ ] `CREATE_BREAKAWAY_FROM_JOB` need remains unverified (manual).
