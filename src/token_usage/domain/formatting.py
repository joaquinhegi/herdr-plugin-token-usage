"""Render token totals for the sidebar."""

_KILO = 1_000
_MEGA = 1_000_000


def _one_decimal(value: int, unit: int) -> str:
    # Integer round-half-up to one decimal; avoids float and banker's rounding.
    tenths = (value * 10 + unit // 2) // unit
    return f"{tenths // 10}.{tenths % 10}"


def format_tokens(total: int) -> str:
    if total < _KILO:
        return f"{total} tokens"
    if total < _MEGA:
        tenths = (total * 10 + _KILO // 2) // _KILO
        if tenths < 10_000:
            return f"{tenths // 10}.{tenths % 10}k tokens"
    return f"{_one_decimal(total, _MEGA)}M tokens"
