"""Check that Table VII timing comparisons require identical recorded search work."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    from compare_pure_replay import compare_work
finally:
    sys.path.pop(0)


class PureReplayTests(unittest.TestCase):
    def setUp(self):
        common = {"block": "1", "count": "9", "fingerprint": "10|11", "et": "True", "et_attempt": "7",
                  "et_hit": "4", "et_degree2_hit": "2", "et_pattern_components": "", "time_s": "0.2"}
        self.saved = [{**common, "mode": "single_et2", "kind": "single", "branch_calls": "", "et_output_count": ""},
                      {**common, "mode": "double_compact_et2", "kind": "double", "branch_calls": "27",
                       "et_output_count": "5"}]
        self.replay = [{**row, "time_s": "0.3"} for row in self.saved]

    def test_timing_variation_preserves_search_work_match(self):
        self.assertEqual(compare_work(self.saved, list(reversed(self.replay))), 2)

    def test_equal_outputs_do_not_hide_changed_work(self):
        for field, index in (("branch_calls", 1), ("et_hit", 0), ("et_degree2_hit", 1), ("et_output_count", 1)):
            with self.subTest(field=field):
                changed = [row.copy() for row in self.replay]
                changed[index][field] = str(int(changed[index][field]) + 1)
                with self.assertRaisesRegex(ValueError, f"replay changed {field}"):
                    compare_work(self.saved, changed)

    def test_matching_counters_do_not_hide_changed_fingerprint(self):
        self.replay[0]["fingerprint"] = "10|12"
        with self.assertRaisesRegex(ValueError, "replay changed fingerprint"):
            compare_work(self.saved, self.replay)

    def test_wrong_terminal_mode_or_pattern_reuse_is_rejected(self):
        for field, value in (("et", "False"), ("et_pattern_components", "1")):
            with self.subTest(field=field):
                changed = [row.copy() for row in self.replay]
                changed[1][field] = value
                with self.assertRaisesRegex(ValueError, "unexpected ET or pattern-reuse setting"):
                    compare_work(self.saved, changed)
