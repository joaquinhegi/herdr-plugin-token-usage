"""Pure reconciliation of desired pane totals against what was last published."""

from dataclasses import dataclass

from token_usage.domain.formatting import format_tokens

REFRESH_S = 20
TTL_MS = 60000


@dataclass(frozen=True)
class Publish:
    pane_id: str
    value: str
    seq: int


@dataclass(frozen=True)
class Clear:
    pane_id: str
    seq: int


def reconcile(previous: dict, desired: dict, now: float, now_ms: int) -> tuple[list, dict]:
    """Return (actions, new published state). Never mutates `previous`."""
    last_seq = previous.get("seq", 0)
    old = previous.get("panes", {})
    panes: dict[str, dict] = {}
    actions: list = []

    def next_seq() -> int:
        nonlocal last_seq
        last_seq = max(last_seq + 1, now_ms)
        return last_seq

    for pane_id in sorted(desired):  # panes absent from `desired` are forgotten
        want = desired[pane_id]
        prev = old.get(pane_id)
        if want is None or want[1] <= 0:
            if prev is not None:
                actions.append(Clear(pane_id, next_seq()))
            continue
        session, total = want
        value = format_tokens(total)
        if prev and prev.get("session") == session and prev.get("value") == value \
                and 0 <= now - prev.get("at", 0) < REFRESH_S:
            panes[pane_id] = dict(prev)
            continue
        actions.append(Publish(pane_id, value, next_seq()))
        panes[pane_id] = {"session": session, "value": value, "at": now}
    return actions, {"seq": last_seq, "panes": panes}
