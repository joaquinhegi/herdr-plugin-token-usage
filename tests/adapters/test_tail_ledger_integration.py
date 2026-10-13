import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters.jsonl_tail import JsonlTail  # noqa: E402
from token_usage.domain.ledger import Ledger  # noqa: E402
from token_usage.sources import claude  # noqa: E402


def line(mid: str, out: int) -> bytes:
    obj = {"type": "assistant", "message": {"id": mid, "model": "m", "usage": {"input_tokens": 1, "output_tokens": out}}}
    return json.dumps(obj).encode() + b"\n"


class TailLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "s.jsonl"
        self.tail, self.ledger, self.pos = JsonlTail(), Ledger(), None

    def tick(self):
        result = self.tail.read(self.path, self.pos)
        self.pos = result.position
        for obj in result.objects:
            parsed = claude.parse_line(obj)
            if parsed:
                self.ledger.apply(*parsed)

    def test_truncation_rescan_does_not_double_count(self):
        self.path.write_bytes(line("m1", 4) + line("m2", 6))
        self.tick()
        self.assertEqual(self.ledger.total, 12)
        self.path.write_bytes(line("m1", 4))  # truncated: rescanned from start
        self.tick()
        self.assertEqual(self.ledger.total, 12)

    def test_rotation_reread_does_not_double_count(self):
        self.path.write_bytes(line("m1", 4) + line("m2", 6))
        self.tick()
        os.replace(self.path, self.path.with_suffix(".old"))
        self.path.write_bytes(line("m1", 4) + line("m2", 6) + line("m3", 1))
        self.tick()
        self.assertEqual(self.ledger.total, 14)


if __name__ == "__main__":
    unittest.main()
