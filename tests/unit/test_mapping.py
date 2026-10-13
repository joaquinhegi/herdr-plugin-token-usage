import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.domain.mapping import claude_session_id  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "herdr" / "pane_list.json"
GOOD = "1a1a1a1a-1111-4111-8bbb-111111111111"


def session(**overrides):
    base = {"source": "herdr:claude", "agent": "claude", "kind": "id", "value": GOOD}
    base.update(overrides)
    return {"agent_session": base}


class MappingTest(unittest.TestCase):
    def setUp(self):
        self.panes = {p["pane_id"]: p for p in json.loads(FIXTURE.read_text())["result"]["panes"]}

    def test_two_claude_panes_same_cwd_map_to_own_ids(self):
        self.assertEqual(self.panes["w1:p1"]["cwd"], self.panes["w1:p2"]["cwd"])
        self.assertEqual(claude_session_id(self.panes["w1:p1"]), "11111111-1111-4111-8111-111111111111")
        self.assertEqual(claude_session_id(self.panes["w1:p2"]), "22222222-2222-4222-8222-222222222222")

    def test_codex_absent_and_malformed_value_are_none(self):
        self.assertIsNone(claude_session_id(self.panes["w1:p3"]))
        self.assertIsNone(claude_session_id(self.panes["w1:p4"]))
        self.assertIsNone(claude_session_id(self.panes["w1:p5"]))

    def test_each_strict_field_is_required(self):
        for bad in ({"source": "herdr:codex"}, {"agent": "codex"}, {"kind": "path"}, {"value": GOOD.upper()},
                    {"value": GOOD + "0"}, {"value": 5}, {"value": None}):
            with self.subTest(bad=bad):
                self.assertIsNone(claude_session_id(session(**bad)))
        self.assertEqual(claude_session_id(session()), GOOD)

    def test_non_dict_agent_session_is_none(self):
        for bad in ("x", None, [], 3):
            self.assertIsNone(claude_session_id({"agent_session": bad}))

    def test_cwd_is_ignored(self):
        self.assertEqual(claude_session_id({**session(), "cwd": "/a"}), claude_session_id({**session(), "cwd": "/b"}))
        self.assertIsNone(claude_session_id({"cwd": "/a/" + GOOD}))


if __name__ == "__main__":
    unittest.main()
