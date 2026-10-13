"""Incremental JSONL tailer: complete lines only, bounded reads."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_READ = 4 * 1024 * 1024
MAX_FRAGMENT = 16 * 1024 * 1024


@dataclass
class TailResult:
    objects: list[Any] = field(default_factory=list)
    undecodable: int = 0
    position: dict[str, int] = field(default_factory=dict)


class JsonlTail:
    def __init__(self, max_read: int = MAX_READ, max_fragment: int = MAX_FRAGMENT) -> None:
        self.max_read = max_read
        self.max_fragment = max_fragment

    def read(self, path: Path, position: dict[str, int] | None) -> TailResult:
        try:
            st = os.stat(path)
            fh = open(path, "rb")
        except OSError:
            return TailResult(position=dict(position or {}))
        with fh:
            offset = 0
            if position and position.get("inode") == st.st_ino and position.get("dev") == st.st_dev \
                    and position.get("offset", 0) <= st.st_size:
                offset = position.get("offset", 0)
            result = TailResult(position={"inode": st.st_ino, "dev": st.st_dev, "size": st.st_size, "offset": offset})
            if offset and position.get("skip"):  # still inside a skipped oversized line
                self._skip_fragment(fh, offset, result)
                offset = result.position["offset"]
                if result.position.get("skip"):
                    return result
            available = st.st_size - offset
            fh.seek(offset)
            data = fh.read(min(available, self.max_read))
            end = data.rfind(b"\n")
            if end < 0 and available > len(data):
                if available > self.max_fragment:
                    return self._skip_fragment(fh, offset, result)
                fh.seek(offset)
                data = fh.read(available)
                end = data.rfind(b"\n")
            if end < 0:
                return result
            for raw in data[:end].split(b"\n"):
                if not raw.strip():
                    continue
                try:
                    result.objects.append(json.loads(raw.decode("utf-8")))
                except ValueError:  # includes UnicodeDecodeError
                    result.undecodable += 1
            result.position["offset"] = offset + end + 1
            return result

    def _skip_fragment(self, fh, offset: int, result: TailResult) -> TailResult:
        """Drop an oversized newline-less fragment up to the next newline (or EOF)."""
        result.position.pop("skip", None)
        fh.seek(offset)
        pos = offset
        while chunk := fh.read(65536):
            nl = chunk.find(b"\n")
            if nl >= 0:
                pos += nl + 1
                break
            pos += len(chunk)
        else:
            result.position["skip"] = 1  # EOF before the newline: keep skipping next time
        result.position["offset"] = pos
        return result
