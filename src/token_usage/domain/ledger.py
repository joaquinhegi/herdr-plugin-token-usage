"""Idempotent per-session usage ledger."""

from .usage import UsageCall

Entry = tuple[int, int, int, int]


class Ledger:
    """Maps a call key (message id or requestId) to its max usage.

    Merging is field-wise max, so replays, resume-copied history, rotation
    re-reads and streaming partial usage never inflate the total.
    """

    def __init__(self) -> None:
        self.entries: dict[str, Entry] = {}
        self.total = 0

    @classmethod
    def from_entries(cls, entries: dict[str, Entry]) -> "Ledger":
        ledger = cls()
        ledger.entries = {key: tuple(value) for key, value in entries.items()}
        ledger.total = sum(sum(value) for value in ledger.entries.values())
        return ledger

    def apply(self, key: str, call: UsageCall) -> bool:
        """Merge one call; return True when the stored entry changed."""
        new = (call.input, call.output, call.cache_creation, call.cache_read)
        old = self.entries.get(key, (0, 0, 0, 0))
        merged = tuple(max(a, b) for a, b in zip(old, new))
        if key in self.entries and merged == old:
            return False
        self.entries[key] = merged
        self.total += sum(merged) - sum(old)
        return True
