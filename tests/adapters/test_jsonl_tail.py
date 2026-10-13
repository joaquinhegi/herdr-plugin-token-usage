import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters.jsonl_tail import JsonlTail  # noqa: E402


class TailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "s.jsonl"
        self.tail = JsonlTail()

    def append(self, data: bytes):
        with open(self.path, "ab") as fh:
            fh.write(data)

    def test_growth_returns_only_new_lines(self):
        self.append(b'{"a":1}\n')
        r1 = self.tail.read(self.path, None)
        self.assertEqual(r1.objects, [{"a": 1}])
        self.append(b'{"a":2}\n')
        r2 = self.tail.read(self.path, r1.position)
        self.assertEqual(r2.objects, [{"a": 2}])
        self.assertEqual(self.tail.read(self.path, r2.position).objects, [])

    def test_partial_line_is_counted_once_when_completed(self):
        self.append(b'{"a":1}\n{"a":')
        r1 = self.tail.read(self.path, None)
        self.assertEqual(r1.objects, [{"a": 1}])
        self.append(b'2}\n')
        r2 = self.tail.read(self.path, r1.position)
        self.assertEqual(r2.objects, [{"a": 2}])

    def test_truncate_rescans_from_start(self):
        self.append(b'{"a":1}\n{"a":2}\n')
        r1 = self.tail.read(self.path, None)
        self.path.write_bytes(b'{"a":3}\n')
        self.assertEqual(self.tail.read(self.path, r1.position).objects, [{"a": 3}])

    def test_rotation_new_inode_rescans(self):
        self.append(b'{"a":1}\n{"a":2}\n')
        r1 = self.tail.read(self.path, None)
        os.replace(self.path, self.path.with_suffix(".old"))
        self.append(b'{"a":1}\n{"a":2}\n{"a":4}\n')
        self.assertEqual(len(self.tail.read(self.path, r1.position).objects), 3)

    def test_read_cap_limits_bytes_per_call(self):
        line = b'{"a":1}\n'
        self.append(line * 10)
        tail = JsonlTail(max_read=len(line) * 4)
        r1 = tail.read(self.path, None)
        self.assertEqual(len(r1.objects), 4)
        r2 = tail.read(self.path, r1.position)
        self.assertEqual(len(r2.objects), 4)

    def test_line_larger_than_read_cap_is_still_consumed(self):
        big = b'{"a":"' + b"x" * 100 + b'"}\n'
        self.append(big + b'{"a":2}\n')
        tail = JsonlTail(max_read=32, max_fragment=1000)
        r1 = tail.read(self.path, None)
        self.assertEqual(r1.objects[-1], {"a": 2})
        self.assertEqual(len(r1.objects), 2)

    def test_oversized_fragment_skipped_to_next_newline(self):
        tail = JsonlTail(max_read=32, max_fragment=64)
        self.append(b"y" * 200)
        r1 = tail.read(self.path, None)
        self.assertEqual(r1.objects, [])
        self.append(b'zzz\n{"a":9}\n')
        r2 = tail.read(self.path, r1.position)
        self.assertEqual(r2.objects, [{"a": 9}])
        self.assertEqual(r2.undecodable, 0)

    def test_midsize_line_kept_when_much_data_follows(self):
        mid = b'{"a":"' + b"x" * 100 + b'"}\n'  # > read cap, < fragment cap
        self.append(mid + b'{"a":2}\n' * 50)  # remaining bytes far exceed the fragment cap
        tail = JsonlTail(max_read=32, max_fragment=200)
        r1 = tail.read(self.path, None)
        self.assertEqual(r1.objects[0]["a"], "x" * 100)
        self.assertEqual(r1.undecodable, 0)

    def test_undecodable_lines_are_counted_and_skipped(self):
        self.append(b'{"a":1}\n\xff\xfe\nnot json\n[1]\n{"a":2}\n')
        r = self.tail.read(self.path, None)
        self.assertEqual(r.objects, [{"a": 1}, [1], {"a": 2}])
        self.assertEqual(r.undecodable, 2)

    def test_missing_file_returns_empty_and_keeps_position(self):
        pos = {"inode": 1, "dev": 1, "size": 1, "offset": 1}
        r = self.tail.read(Path(self.tmp.name) / "nope.jsonl", pos)
        self.assertEqual((r.objects, r.position), ([], pos))


if __name__ == "__main__":
    unittest.main()
