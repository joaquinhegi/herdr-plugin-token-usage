"""Pure Codex rollout line parser (fixture-tested only in the MVP)."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class CodexSnapshot:
    """Cumulative ``total_token_usage`` at a point in the rollout.

    Assumes cached tokens are already inside ``input`` and reasoning tokens
    inside ``output`` (unproven; see design.md open questions), so neither is
    added again and ``total = input + output``.
    """

    input: int
    output: int
    cached_input: int = 0
    reasoning_output: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output


def _count(usage: dict, field: str) -> int | None:
    value = usage.get(field, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def parse_line(obj: object) -> CodexSnapshot | None:
    """Return the cumulative snapshot of a ``token_count`` event, else None."""
    if not isinstance(obj, dict) or obj.get("type") != "event_msg":
        return None
    payload = obj.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    info = payload.get("info")
    usage = info.get("total_token_usage") if isinstance(info, dict) else None
    if not isinstance(usage, dict):
        return None
    fields = ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens")
    counts = [_count(usage, f) for f in fields]
    if None in counts:
        return None
    return CodexSnapshot(*counts)


def latest_total(objs: Iterable[object]) -> int | None:
    """Total of the latest cumulative snapshot (never a sum); None if none."""
    latest = None
    for obj in objs:
        snapshot = parse_line(obj)
        if snapshot is not None:
            latest = snapshot
    return None if latest is None else latest.total
