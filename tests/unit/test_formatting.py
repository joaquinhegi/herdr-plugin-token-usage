import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from token_usage.domain.formatting import format_tokens  # noqa: E402
from token_usage.domain.usage import UsageCall  # noqa: E402


class FormatTokensTest(unittest.TestCase):
    def test_spec_examples(self):
        cases = {
            950: "950 tokens",
            1250: "1.3k tokens",
            125400: "125.4k tokens",
            1200000: "1.2M tokens",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_tokens(value), expected)

    def test_boundaries(self):
        self.assertEqual(format_tokens(1), "1 tokens")
        self.assertEqual(format_tokens(999), "999 tokens")
        self.assertEqual(format_tokens(1000), "1.0k tokens")
        self.assertEqual(format_tokens(999_949), "999.9k tokens")
        self.assertEqual(format_tokens(999_950), "1.0M tokens")
        self.assertEqual(format_tokens(1_000_000), "1.0M tokens")

    def test_max_length(self):
        self.assertLessEqual(len(format_tokens(10**30)), 80)


class UsageCallTest(unittest.TestCase):
    def test_total_sums_four_fields(self):
        self.assertEqual(UsageCall(10, 20, 5, 100).total, 135)

    def test_thinking_not_added_again(self):
        call = UsageCall(input=10, output=20, cache_creation=5, cache_read=100, thinking=8)
        self.assertEqual(call.total, 135)

    def test_different_values(self):
        self.assertEqual(UsageCall(1, 2, 3, 4).total, 10)


if __name__ == "__main__":
    unittest.main()
