"""Pure Claude transcript line parser: dict -> (call key, UsageCall) | None."""

from ..domain.usage import UsageCall

SYNTHETIC_MODEL = "<synthetic>"


def _count(usage: dict, field: str) -> int | None:
    value = usage.get(field, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def parse_line(obj: object) -> tuple[str, UsageCall] | None:
    """Return ``(key, call)`` for a countable assistant line, else None.

    Key is ``message.id`` with ``requestId`` as fallback. Synthetic, API-error,
    id-less and malformed lines are skipped.
    """
    if not isinstance(obj, dict) or obj.get("type") != "assistant" or obj.get("isApiErrorMessage"):
        return None
    message = obj.get("message")
    if not isinstance(message, dict) or message.get("model") == SYNTHETIC_MODEL:
        return None
    key = message.get("id") or obj.get("requestId")
    usage = message.get("usage")
    if not isinstance(key, str) or not key or not isinstance(usage, dict):
        return None
    counts = [
        _count(usage, f)
        for f in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    ]
    details = usage.get("output_tokens_details")
    thinking = _count(details, "thinking_tokens") if isinstance(details, dict) else 0
    if None in counts or thinking is None:
        return None
    return key, UsageCall(*counts, thinking=thinking)
