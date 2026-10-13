import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.domain.ledger import Ledger  # noqa: E402
from token_usage.domain.usage import UsageCall  # noqa: E402


class LedgerTest(unittest.TestCase):
    def test_apply_true_when_only_alias_learned(self):
        ledger = Ledger()
        call = UsageCall(1, 2, 0, 0)
        self.assertTrue(ledger.apply("msg_1", call))
        self.assertTrue(ledger.apply("msg_1", call, alias="req_1"))
        self.assertFalse(ledger.apply("msg_1", call, alias="req_1"))

    def test_apply_true_on_late_binding(self):
        ledger = Ledger()
        call = UsageCall(1, 2, 0, 0)
        ledger.apply("req_1", call)
        self.assertTrue(ledger.apply("msg_1", call, alias="req_1"))
        self.assertEqual(ledger.total, 3)

    def test_repeated_id_counts_once(self):
        ledger = Ledger()
        call = UsageCall(10, 20, 0, 100)
        for _ in range(3):
            ledger.apply("msg_1", call)
        self.assertEqual(ledger.total, 130)

    def test_distinct_ids_accumulate(self):
        ledger = Ledger()
        ledger.apply("msg_1", UsageCall(10, 20, 0, 0))
        ledger.apply("msg_2", UsageCall(1, 2, 3, 4))
        self.assertEqual(ledger.total, 40)

    def test_total_grows_after_each_of_three_responses(self):
        ledger = Ledger()
        totals = []
        for i, key in enumerate(["msg_1", "msg_2", "msg_3"], start=1):
            ledger.apply(key, UsageCall(i, i, 0, 10))
            totals.append(ledger.total)
        self.assertEqual(totals, [12, 26, 42])

    def test_field_wise_max_keeps_streaming_growth(self):
        ledger = Ledger()
        ledger.apply("msg_1", UsageCall(10, 1, 0, 50))
        ledger.apply("msg_1", UsageCall(5, 30, 7, 20))
        self.assertEqual(ledger.entries["msg_1"], (10, 30, 7, 50))
        self.assertEqual(ledger.total, 97)

    def test_replay_leaves_total_unchanged(self):
        ledger = Ledger()
        calls = {"a": UsageCall(1, 2, 3, 4), "b": UsageCall(10, 20, 30, 40)}
        for key, call in calls.items():
            ledger.apply(key, call)
        before = ledger.total
        changed = [ledger.apply(key, call) for key, call in calls.items()]
        self.assertEqual(before, 110)
        self.assertEqual(ledger.total, before)
        self.assertEqual(changed, [False, False])

    def test_apply_reports_change(self):
        ledger = Ledger()
        self.assertTrue(ledger.apply("a", UsageCall(1, 0, 0, 0)))
        self.assertTrue(ledger.apply("a", UsageCall(2, 0, 0, 0)))

    def test_incremental_total_matches_recompute(self):
        ledger = Ledger()
        ledger.apply("a", UsageCall(1, 1, 1, 1))
        ledger.apply("a", UsageCall(2, 0, 5, 1))
        ledger.apply("b", UsageCall(0, 9, 0, 0))
        self.assertEqual(ledger.total, sum(sum(v) for v in ledger.entries.values()))
        self.assertEqual(ledger.total, 2 + 1 + 5 + 1 + 9)

    def test_from_entries_restores_total(self):
        ledger = Ledger.from_entries({"a": (1, 2, 3, 4)})
        self.assertEqual(ledger.total, 10)
        ledger.apply("a", UsageCall(1, 2, 3, 4))
        self.assertEqual(ledger.total, 10)


    def test_alias_late_binding_and_restore(self):
        ledger = Ledger()
        ledger.apply("req_x", UsageCall(1, 1, 0, 0))  # request-only first
        ledger.apply("msg_x", UsageCall(1, 1, 0, 0), alias="req_x")
        self.assertEqual((ledger.total, list(ledger.entries)), (2, ["msg_x"]))
        restored = Ledger.from_entries(ledger.entries, ledger.aliases)
        self.assertFalse(restored.apply("req_x", UsageCall(1, 1, 0, 0)))
        self.assertEqual(restored.total, 2)


if __name__ == "__main__":
    unittest.main()
