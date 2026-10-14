import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters.state_store import StateStore  # noqa: E402
from token_usage.domain.ledger import Ledger  # noqa: E402
from token_usage.domain.usage import UsageCall  # noqa: E402

UUID = "11111111-2222-3333-4444-555555555555"


def state(**over):
    base = {"provider": "claude", "last_seen": 1000, "total": 5,
            "files": {"main": {"inode": 1, "dev": 1, "size": 9, "offset": 9}},
            "ledger": {"msg_a": [2, 3, 0, 0]}, "aliases": {"req_a": "msg_a"}}
    base.update(over)
    return base


class StateStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = StateStore(self.root)

    def test_trailing_newline_id_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save_session("abc\n", state())

    def test_roundtrip_restores_ledger_with_aliases(self):
        ledger = Ledger()
        ledger.apply("msg_a", UsageCall(2, 3, 0, 0), alias="req_a")
        self.store.save_session(UUID, state(ledger=ledger.entries, aliases=ledger.aliases))
        loaded = StateStore(self.root).load_session(UUID)
        self.assertEqual(loaded["v"], 1)
        restored = Ledger.from_entries(loaded["ledger"], loaded["aliases"])
        self.assertFalse(restored.apply("req_a", UsageCall(2, 3, 0, 0)))
        self.assertEqual(restored.total, 5)

    def test_atomic_write_uses_fsync_then_replace(self):
        calls = []
        with mock.patch("os.fsync", side_effect=lambda fd: calls.append("fsync")), \
                mock.patch("os.replace", side_effect=lambda a, b: calls.append("replace")):
            self.store.save_session(UUID, state())
        self.assertEqual(calls, ["fsync", "replace", "fsync"])  # file, rename, parent dir

    def test_no_temp_files_left_and_only_dirty_written(self):
        self.assertTrue(self.store.save_session(UUID, state()))
        self.assertFalse(self.store.save_session(UUID, state()))
        self.assertTrue(self.store.save_session(UUID, state(total=6)))
        self.assertEqual([p.name for p in (self.root / "sessions").iterdir()], [f"{UUID}.json"])

    def test_unknown_version_or_corrupt_means_rebuild(self):
        path = self.root / "sessions" / f"{UUID}.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"v": 99}))
        self.assertIsNone(self.store.load_session(UUID))
        path.write_text("{not json")
        self.assertIsNone(self.store.load_session(UUID))

    def test_prune_removes_sessions_older_than_30_days(self):
        other = "99999999-2222-3333-4444-555555555555"
        self.store.save_session(UUID, state(last_seen=1000))
        self.store.save_session(other, state(last_seen=1000 + 31 * 86400))
        removed = self.store.prune(now=1000 + 31 * 86400 + 1)
        self.assertEqual(removed, 1)
        self.assertIsNone(self.store.load_session(UUID))
        self.assertIsNotNone(self.store.load_session(other))

    def test_rejects_absolute_or_escaping_keys_and_ids(self):
        for bad in ("/abs/path.jsonl", "../x.jsonl", "a/../../x"):
            with self.assertRaises(ValueError):
                self.store.save_session(UUID, state(files={bad: {"offset": 0}}))
        with self.assertRaises(ValueError):
            self.store.save_session("../evil", state())

    def test_file_key_allowlist(self):
        for bad in ("", ".", "..", "/abs", "~/x", "~", "other", "subagents/x.jsonl", "subagents/agent-1.json",
                    "subagents/agent-1/x.jsonl", "main/x"):
            with self.subTest(key=bad), self.assertRaises(ValueError):
                self.store.save_session(UUID, state(files={bad: {"offset": 0}}))
        self.assertTrue(self.store.save_session(UUID, state(files={"main": {}, "subagents/agent-a1.jsonl": {}})))

    def test_prune_sweeps_only_old_orphan_tmp_files(self):
        self.store.save_session(UUID, state(last_seen=1000))
        old, fresh = self.root / "sessions" / "a.tmp", self.root / "sessions" / "b.tmp"
        root_old = self.root / "c.tmp"
        for f in (old, fresh, root_old):
            f.write_text("x")
        for f, age in ((old, 7200), (root_old, 7200), (fresh, 10)):
            os.utime(f, (5000 - age, 5000 - age))
        self.store.prune(now=5000)
        self.assertEqual((old.exists(), root_old.exists(), fresh.exists()), (False, False, True))

    def test_published_roundtrip(self):
        self.store.save_published({"seq": 7, "panes": {}})
        self.assertEqual(self.store.load_published()["seq"], 7)


if __name__ == "__main__":
    unittest.main()
