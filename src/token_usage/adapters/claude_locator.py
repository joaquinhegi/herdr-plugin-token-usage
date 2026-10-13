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

    def _contained(self, path: Path, root_real: Path) -> bool:
        return Path(os.path.realpath(path)).is_relative_to(root_real)

    def locate(self, session_id: str) -> Located | None:
        if not UUID.fullmatch(session_id):
            return None
        root_real = Path(os.path.realpath(self.root))
        mains, subs = [], []
        try:
            projects = sorted(p for p in root_real.iterdir() if p.is_dir())
        except OSError:
            projects = []
        for project in projects:
            main = project / f"{session_id}.jsonl"
            if main.is_file() and self._contained(main, root_real):
                mains.append(main)
                sub_dir = project / session_id / "subagents"
                if sub_dir.is_dir():
                    subs = [f for f in sorted(sub_dir.glob("*.jsonl")) if f.is_file() and self._contained(f, root_real)]
        if len(mains) != 1:
            log_event(self.logger, "locate_failed", reason="ambiguous" if mains else "missing", matches=len(mains))
            return None
        return Located(mains[0], subs)
