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
        self.aliases: dict[str, str] = {}  # requestId -> canonical (message.id) key
        self.total = 0

    @classmethod
    def from_entries(cls, entries: dict[str, Entry], aliases: dict[str, str] | None = None) -> "Ledger":
        ledger = cls()
        ledger.aliases = dict(aliases or {})
        ledger.entries = {key: tuple(value) for key, value in entries.items()}
        ledger.total = sum(sum(value) for value in ledger.entries.values())
        return ledger

    def apply(self, key: str, call: UsageCall, alias: str | None = None) -> bool:
        """Merge one call; return True when the stored entry changed.

        ``alias`` is the line's requestId when ``key`` is its message id: it is
        remembered so a later requestId-only line maps to the same entry.
        """
        if key not in self.entries and key in self.aliases:
            key = self.aliases[key]
        if alias and alias != key:
            self.aliases[alias] = key
            moved = self.entries.pop(alias, None)  # requestId-only line seen first
            if moved is not None:
                existing = self.entries.get(key, (0, 0, 0, 0))
                self.entries[key] = tuple(max(a, b) for a, b in zip(existing, moved))
                self.total += sum(self.entries[key]) - sum(existing) - sum(moved)
        new = (call.input, call.output, call.cache_creation, call.cache_read)
        old = self.entries.get(key, (0, 0, 0, 0))
        merged = tuple(max(a, b) for a, b in zip(old, new))
        if key in self.entries and merged == old:
            return False
        self.entries[key] = merged
        self.total += sum(merged) - sum(old)
        return True
