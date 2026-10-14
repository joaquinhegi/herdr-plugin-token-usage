"""Locates a Claude session's transcripts under an injected projects root."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from token_usage.adapters.log import log_event
from token_usage.domain.mapping import UUID


@dataclass
class Located:
    main: Path
    subagents: list[Path] = field(default_factory=list)


class ClaudeLocator:
    def __init__(self, projects_root: Path, logger: logging.Logger):
        self.root = Path(projects_root)
        self.logger = logger
        self._last_failure: dict[str, str] = {}  # session id -> last logged reason

    def _resolve(self, path: Path, root_real: Path) -> Path | None:
        real = Path(os.path.realpath(path))
        return real if real.is_relative_to(root_real) and real.is_file() else None

    def locate(self, session_id: str) -> Located | None:
        if not isinstance(session_id, str) or not UUID.fullmatch(session_id):
            return None
        root_real = Path(os.path.realpath(self.root))
        mains: dict[Path, Path] = {}
        try:
            projects = sorted(p for p in root_real.iterdir() if p.is_dir())
        except OSError:
            projects = []
        for project in projects:
            main = self._resolve(project / f"{session_id}.jsonl", root_real)
            if main and main.name == f"{session_id}.jsonl":
                mains.setdefault(main, project)
        if len(mains) != 1:
            reason = "ambiguous" if mains else "missing"
            if self._last_failure.get(session_id) != reason:  # log outcome changes only, not every tick
                self._last_failure[session_id] = reason
                log_event(self.logger, "locate_failed", reason=reason, matches=len(mains))
            return None
        self._last_failure.pop(session_id, None)
        main = next(iter(mains))
        project = main.parent
        subs: list[Path] = []
        sub_dir = project / session_id / "subagents"
        if sub_dir.is_dir():
            for f in sorted(sub_dir.glob("agent-*.jsonl")):
                real = self._resolve(f, root_real)
                if real and real.match("agent-*.jsonl") and real.parent.name == "subagents" and real.parent.parent.name == session_id:
                    if real not in subs:
                        subs.append(real)
        return Located(main, subs)
