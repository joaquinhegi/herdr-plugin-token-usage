"""One poll tick: panes -> sessions -> totals -> reconcile -> Herdr, persisted."""

import logging

from token_usage.adapters.log import log_event, log_exception
from token_usage.domain.ledger import Ledger
from token_usage.domain.mapping import claude_session_id
from token_usage.domain.reconcile import TTL_MS, Clear, reconcile
from token_usage.ports import HerdrPort, StateStore, Tailer
from token_usage.sources import claude

SOURCE = "token-usage"
TOKEN = "tokens"


class TickService:
    def __init__(self, herdr: HerdrPort, locator, tailer: Tailer, store: StateStore, clock, logger: logging.Logger):
        self.herdr, self.locator, self.tailer = herdr, locator, tailer
        self.store, self.clock, self.logger = store, clock, logger

    def tick(self) -> None:
        try:
            panes = self.herdr.list_panes()
        except Exception as exc:  # Herdr down: change nothing, clear nothing
            log_exception(self.logger, "herdr_unreachable", exc)
            return
        now = self.clock.now()
        pane_session = {
            p["pane_id"]: claude_session_id(p) for p in panes if isinstance(p, dict) and isinstance(p.get("pane_id"), str)
        }
        totals = {sid: self._session_total(sid, now) for sid in sorted({s for s in pane_session.values() if s})}
        desired = {
            pane: (sid, totals[sid]) if sid and totals[sid] is not None else None for pane, sid in pane_session.items()
        }
        previous = self.store.load_published() or {}
        actions, state = reconcile(previous, desired, now, int(now * 1000))
        old = previous.get("panes", {})
        for action in actions:
            try:
                if isinstance(action, Clear):
                    self.herdr.clear(action.pane_id, SOURCE, TOKEN, action.seq)
                else:
                    self.herdr.report(action.pane_id, SOURCE, TOKEN, action.value, action.seq, TTL_MS)
            except Exception as exc:  # unapplied: keep the old record so the next tick retries
                log_exception(self.logger, "apply_failed", exc)
                if action.pane_id in old:
                    state["panes"][action.pane_id] = old[action.pane_id]
                else:
                    state["panes"].pop(action.pane_id, None)
        try:
            self.store.save_published({"seq": state["seq"], "panes": state["panes"]})
        except Exception as exc:  # next tick recomputes from the stored state
            log_exception(self.logger, "save_published_failed", exc)
        log_event(self.logger, "tick", panes=len(pane_session), actions=len(actions))

    def _session_total(self, sid: str, now: float) -> int | None:
        """Total for a session, or None when unknown. Never raises."""
        try:
            return self._read_session(sid, now)
        except Exception as exc:
            log_event(self.logger, "session_failed", error=type(exc).__name__, session=sid[:8])
            return None

    def _read_session(self, sid: str, now: float) -> int | None:
        located = self.locator.locate(sid)
        if located is None:
            return None
        saved = self.store.load_session(sid) or {}
        ledger = Ledger.from_entries(
            {k: tuple(v) for k, v in saved.get("ledger", {}).items()}, saved.get("aliases", {})
        )
        files = {k: dict(v) for k, v in saved.get("files", {}).items()}
        paths = {"main": located.main}
        paths.update({f"subagents/{p.name}": p for p in located.subagents})
        dirty = False
        for key, path in paths.items():
            result = self.tailer.read(path, files.get(key))
            if result.failed:  # main or subagent alike: a partial total would be an undercount shown as truth
                log_event(self.logger, "transcript_unreadable", session=sid[:8])
                return None
            for obj in result.objects:
                parsed = claude.parse_line(obj)
                if parsed:
                    dirty |= ledger.apply(*parsed, alias=claude.request_alias(obj))
            dirty |= files.get(key) != result.position
            files[key] = dict(result.position)
        if dirty:
            try:
                self.store.save_session(sid, {
                    "provider": "claude", "last_seen": now, "total": ledger.total, "files": files,
                    "ledger": {k: list(v) for k, v in ledger.entries.items()}, "aliases": ledger.aliases,
                })
            except Exception as exc:  # the total is still right; offsets are re-read idempotently
                log_exception(self.logger, "save_session_failed", exc)
        return ledger.total
