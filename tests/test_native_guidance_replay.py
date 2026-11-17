"""Check modes and counters when comparing native Table VI runs."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    from compare_native_replay import compare_guidance_work
finally:
    sys.path.pop(0)


class NativeGuidanceReplayTests(unittest.TestCase):
    def test_counter_observations_can_be_reordered(self):
        original = {"two_et": [{"et_used": 7, "pivot_c": 11}, {"et_used": 8, "pivot_c": 12}]}
        replay = {"two_et": list(reversed(original["two_et"]))}
        self.assertEqual(compare_guidance_work(original, replay), {
            "two_et": {"runs": 2, "matched_counters": ["et_used", "pivot_c"], "unavailable_counters": []}
        })

    def test_changed_counter_pairing_is_rejected(self):
        original = {"two_et": [{"et_used": 7, "pivot_c": 11}, {"et_used": 8, "pivot_c": 12}]}
        replay = {"two_et": [{"et_used": 7, "pivot_c": 12}, {"et_used": 8, "pivot_c": 11}]}
        with self.assertRaisesRegex(ValueError, "two_et: archived and replayed guidance counters differ"):
            compare_guidance_work(original, replay)

    def test_unavailable_counter_is_reported(self):
        original = {"one_et": [{"et_hits": None, "tg_prefix2_hits": 0}]}
        replay = {"one_et": [{"et_hits": 47, "tg_prefix2_hits": 0}]}
        self.assertEqual(compare_guidance_work(original, replay), {
            "one_et": {"runs": 1, "matched_counters": ["tg_prefix2_hits"], "unavailable_counters": ["et_hits"]}
        })
