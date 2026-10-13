"""Strict pane -> Claude session resolution (cwd is never consulted)."""

import re

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def claude_session_id(pane: dict) -> str | None:
    ref = pane.get("agent_session")
    if not isinstance(ref, dict):
        return None
    if ref.get("source") != "herdr:claude" or ref.get("agent") != "claude" or ref.get("kind") != "id":
        return None
    value = ref.get("value")
    if isinstance(value, str) and UUID.fullmatch(value):
        return value
    return None
