import json
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.adapters.herdr_cli import HerdrCli  # noqa: E402
from token_usage.ports import HerdrError  # noqa: E402
from tests.adapters.herdr_fakes import fixture_panes, make_fake_bin  # noqa: E402


class HerdrCliTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def argv(self):
        return json.loads((self.dir / "argv.json").read_text())

    def test_relative_bin_rejected(self):
        make_fake_bin(self.dir)
        old = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, old)
        self.assertTrue(os.path.isfile("herdr") and os.access("herdr", os.X_OK))
        with self.assertRaises(HerdrError):
            HerdrCli("herdr")

    def test_default_timeout_is_2(self):
        self.assertEqual(HerdrCli(str(make_fake_bin(self.dir)))._timeout, 2)

    def test_clear_invalid_ids_rejected_before_spawn(self):
        cli = HerdrCli(str(make_fake_bin(self.dir)))
        for pane, source, name in [("w1 p1", "s", "n"), ("--evil", "s", "n"), ("p", "s;x", "n"), ("p", "s", "n=v"), ("p", "s", "")]:
            with self.assertRaises(HerdrError):
                cli.clear(pane, source, name, 1)
        self.assertFalse((self.dir / "argv.json").exists())

    def test_invalid_value_seq_ttl_rejected_before_spawn(self):
        cli = HerdrCli(str(make_fake_bin(self.dir)))
        cases = [("a\0b", 1, 1), ("a\nb", 1, 1), ("", 1, 1), ("x" * 81, 1, 1), (5, 1, 1),
                 ("v", "1", 1), ("v", -1, 1), ("v", True, 1), ("v", 1, True), ("v", 1, -1), ("v", 1, 1.5)]
        for value, seq, ttl in cases:
            with self.assertRaises(HerdrError, msg=repr((value, seq, ttl))):
                cli.report("p", "s", "n", value, seq, ttl)
        for seq in ("1", -1, True, None):
            with self.assertRaises(HerdrError, msg=repr(seq)):
                cli.clear("p", "s", "n", seq)
        self.assertFalse((self.dir / "argv.json").exists())
        cli.report("p", "s", "n", "x" * 80, 0, 0)

    def test_missing_bin_rejected(self):
        with self.assertRaises(HerdrError):
            HerdrCli(str(self.dir / "nope"))

    def test_non_executable_rejected(self):
        p = self.dir / "plain"
        p.write_text("x")
        p.chmod(0o644)
        with self.assertRaises(HerdrError):
            HerdrCli(str(p))

    def test_list_panes_parses_fixture_and_bare_list(self):
        cli = HerdrCli(str(make_fake_bin(self.dir)))
        self.assertEqual(cli.list_panes(), fixture_panes())
        self.assertEqual(self.argv(), ["pane", "list"])
        bare = HerdrCli(str(make_fake_bin(self.dir, out='[{"pane_id":"a"}]')))
        self.assertEqual(bare.list_panes(), [{"pane_id": "a"}])

    def test_metacharacters_are_literal_single_argv_item(self):
        cli = HerdrCli(str(make_fake_bin(self.dir)))
        value = "; rm -rf ~ $(x)"
        cli.report("w1:p1", "token-usage", "usage", value, 3, 60000)
        self.assertEqual(
            self.argv(),
            ["pane", "report-metadata", "w1:p1", "--source", "token-usage",
             "--token", f"usage={value}", "--seq", "3", "--ttl-ms", "60000"],
        )

    def test_clear_argv(self):
        HerdrCli(str(make_fake_bin(self.dir))).clear("w1:p1", "token-usage", "usage", 4)
        self.assertEqual(
            self.argv(),
            ["pane", "report-metadata", "w1:p1", "--source", "token-usage",
             "--clear-token", "usage", "--seq", "4"],
        )

    def test_timeout_nonzero_and_invalid_json(self):
        with self.assertRaises(HerdrError):
            HerdrCli(str(make_fake_bin(self.dir, sleep=5)), timeout=0.3).list_panes()
        with self.assertRaises(HerdrError):
            HerdrCli(str(make_fake_bin(self.dir, code=1))).list_panes()
        with self.assertRaises(HerdrError):
            HerdrCli(str(make_fake_bin(self.dir, out="not json"))).list_panes()

    def test_invalid_ids_rejected_before_spawn(self):
        cli = HerdrCli(str(make_fake_bin(self.dir)))
        for pane, source, name in [("w1 p1", "s", "n"), ("--evil", "s", "n"), ("p", "s;x", "n"), ("p", "s", "n=v"), ("p", "s", "")]:
            with self.assertRaises(HerdrError):
                cli.report(pane, source, name, "v", 1, 1000)
        self.assertFalse((self.dir / "argv.json").exists())


if __name__ == "__main__":
    unittest.main()
