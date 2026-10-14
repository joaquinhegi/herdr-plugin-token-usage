import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.domain.reconcile import (  # noqa: E402
    REFRESH_S, TTL_MS, Clear, Publish, reconcile,
)

S1 = "1a1a1a1a-1111-4111-8bbb-111111111111"
S2 = "2b2b2b2b-2222-4222-8ccc-222222222222"
NOW = 1_000.0
NOW_MS = 1_000_000


def state(seq=5, **panes):
    return {"seq": seq, "panes": panes}


def entry(session=S1, value="1.2k tokens", at=NOW - 1):
    return {"session": session, "value": value, "at": at}


class ReconcileTest(unittest.TestCase):
    def run_it(self, prev, desired, now=NOW, now_ms=NOW_MS):
        return reconcile(prev, desired, now, now_ms)

    def test_constants(self):
        self.assertEqual((REFRESH_S, TTL_MS), (20, 60000))

    def test_new_pane_is_published_and_recorded(self):
        actions, new = self.run_it(state(), {"p1": (S1, 1250)})
        self.assertEqual(actions, [Publish("p1", "1.3k tokens", NOW_MS)])
        self.assertEqual(new["panes"]["p1"], {"session": S1, "value": "1.3k tokens", "at": NOW})
        self.assertEqual(new["seq"], NOW_MS)

    def test_unchanged_recent_value_emits_nothing(self):
        prev = state(p1=entry(value="1.3k tokens"))
        actions, new = self.run_it(prev, {"p1": (S1, 1250)})
        self.assertEqual(actions, [])
        self.assertEqual(new, prev)

    def test_value_change_publishes(self):
        prev = state(p1=entry(value="950 tokens"))
        actions, _ = self.run_it(prev, {"p1": (S1, 1250)})
        self.assertEqual([type(a) for a in actions], [Publish])

    def test_session_change_same_value_publishes(self):
        prev = state(p1=entry(session=S1, value="1.3k tokens"))
        actions, new = self.run_it(prev, {"p1": (S2, 1250)})
        self.assertEqual(actions, [Publish("p1", "1.3k tokens", NOW_MS)])
        self.assertEqual(new["panes"]["p1"]["session"], S2)

    def test_refresh_at_exactly_20s_but_not_before(self):
        value = "1.3k tokens"
        young = state(p1=entry(value=value, at=NOW - 19.9))
        self.assertEqual(self.run_it(young, {"p1": (S1, 1250)})[0], [])
        old = state(p1=entry(value=value, at=NOW - 20))
        actions, new = self.run_it(old, {"p1": (S1, 1250)})
        self.assertEqual(actions, [Publish("p1", value, NOW_MS)])
        self.assertEqual(new["panes"]["p1"]["at"], NOW)

    def test_none_clears_previously_published_and_forgets(self):
        actions, new = self.run_it(state(p1=entry()), {"p1": None})
        self.assertEqual(actions, [Clear("p1", NOW_MS)])
        self.assertNotIn("p1", new["panes"])

    def test_zero_total_clears_and_never_publishes_zero(self):
        actions, new = self.run_it(state(p1=entry()), {"p1": (S1, 0)})
        self.assertEqual(actions, [Clear("p1", NOW_MS)])
        self.assertNotIn("p1", new["panes"])
        actions, new = self.run_it(state(), {"p1": (S1, 0), "p2": (S1, -5)})
        self.assertEqual(actions, [])
        self.assertEqual(new["panes"], {})

    def test_unmapped_never_published_emits_nothing(self):
        actions, new = self.run_it(state(), {"p1": None})
        self.assertEqual(actions, [])
        self.assertEqual(new, state())

    def test_absent_pane_is_forgotten_without_action(self):
        actions, new = self.run_it(state(p1=entry()), {})
        self.assertEqual(actions, [])
        self.assertEqual(new["panes"], {})

    def test_seq_strictly_increases_within_one_call(self):
        prev = state(p2=entry())
        desired = {"p1": (S1, 100), "p2": None, "p3": (S2, 200)}
        actions, new = self.run_it(prev, desired)
        seqs = [a.seq for a in actions]
        self.assertEqual(seqs, [NOW_MS, NOW_MS + 1, NOW_MS + 2])
        self.assertEqual(new["seq"], NOW_MS + 2)

    def test_seq_monotonic_when_clock_goes_backwards(self):
        prev = state(seq=NOW_MS + 500)
        actions, new = self.run_it(prev, {"p1": (S1, 100)})
        self.assertEqual(actions[0].seq, NOW_MS + 501)
        self.assertEqual(new["seq"], NOW_MS + 501)

    def test_seq_unchanged_when_no_actions(self):
        self.assertEqual(self.run_it(state(seq=7), {})[1]["seq"], 7)

    def test_previous_state_is_not_mutated(self):
        prev = state(p1=entry())
        snapshot = {"seq": prev["seq"], "panes": {"p1": dict(prev["panes"]["p1"])}}
        self.run_it(prev, {"p1": None})
        self.assertEqual(prev, snapshot)

    def test_empty_previous_state_is_tolerated(self):
        actions, _ = self.run_it({}, {"p1": (S1, 10)})
        self.assertEqual(actions, [Publish("p1", "10 tokens", NOW_MS)])


if __name__ == "__main__":
    unittest.main()
