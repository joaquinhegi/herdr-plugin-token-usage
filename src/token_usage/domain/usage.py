"""Token usage value object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageCall:
    """Usage of one model call.

    ``thinking`` is informational: thinking tokens are already counted inside
    ``output`` and MUST NOT be added again to the total.
    """

    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0
    thinking: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_creation + self.cache_read
