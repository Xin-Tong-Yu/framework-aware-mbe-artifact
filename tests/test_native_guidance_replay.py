"""Check native replay counters and the Table VI timing analysis."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    from compare_native_replay import compare_work, guidance_timing_sensitivity
    from summarize_state_and_guidance import (
        DIRECT_GUIDANCE, GUIDED, WORK_COUNTERS, anchored_ratios, guidance_timing_by_block, recorded_work,
    )
finally:
    sys.path.pop(0)


class NativeGuidanceReplayTests(unittest.TestCase):
    def test_counter_observations_can_be_reordered(self):
        original = {"two_et": [{"et_used": 7, "pivot_c": 11}, {"et_used": 8, "pivot_c": 12}]}
        replay = {"two_et": list(reversed(original["two_et"]))}
        self.assertEqual(compare_work(original, replay), {
            "two_et": {"runs": 2, "matched_counters": ["et_used", "pivot_c"], "unavailable_counters": []}
        })

    def test_changed_counter_pairing_is_rejected(self):
        original = {"two_et": [{"et_used": 7, "pivot_c": 11}, {"et_used": 8, "pivot_c": 12}]}
        replay = {"two_et": [{"et_used": 7, "pivot_c": 12}, {"et_used": 8, "pivot_c": 11}]}
        with self.assertRaisesRegex(ValueError, "two_et: archived and replayed work counters differ"):
            compare_work(original, replay)

    def test_unavailable_counter_is_reported(self):
        original = {"one_et": [{"et_hits": None, "tg_prefix2_hits": 0}]}
        replay = {"one_et": [{"et_hits": 47, "tg_prefix2_hits": 0}]}
        self.assertEqual(compare_work(original, replay), {
            "one_et": {"runs": 1, "matched_counters": ["tg_prefix2_hits"], "unavailable_counters": ["et_hits"]}
        })

    def test_required_work_counters_cannot_disappear(self):
        candidate = {"bitmask_hits": 0, "bitmask_outputs": 0}
        with self.assertRaisesRegex(ValueError, "v63_core_d: invalid prefork_skips counter"):
            recorded_work([("v63_core_d", candidate)], WORK_COUNTERS["iii"])
        double = {"branches": 1, "leaves": 1, "et_used": 0}
        with self.assertRaisesRegex(ValueError, "vector_st: invalid et_output counter"):
            recorded_work([("vector_st", double)], WORK_COUNTERS["v"])

    def test_normalization_uses_each_variants_st_position_and_keeps_order(self):
        mode_times = (("one_st", 100), ("two_st", 50), ("one_et", 110), ("two_et_tg_compact", 45),
                      ("two_et", 52), ("one_et_tg", 100), ("two_st", 70), ("one_st", 180))
        block = {"seed": 19, "jobs": [{"mode": mode, "ms": time} for mode, time in mode_times]}
        bracketed = anchored_ratios(block["jobs"], ("one_st", "two_st"), GUIDED, "ms")
        direct = {"single": {"block_ratios": [110 / 100]}, "double": {"block_ratios": [52 / 45]}}
        timing = guidance_timing_by_block([block], [bracketed], direct)
        single = timing["single"][0]
        self.assertEqual(single["seed"], 19)
        self.assertFalse(single["policy_before_et"])
        self.assertEqual(single["st_end_over_start"], 1.8)
        self.assertAlmostEqual(single["st_normalized_policy_ratio"], (110 / 100) * (100 + 80 * 5 / 7) / (100 + 80 * 2 / 7))
        double = timing["double"][0]
        self.assertTrue(double["policy_before_et"])
        self.assertAlmostEqual(double["st_normalized_policy_ratio"], (52 / 45) * (50 + 20 * 2 / 5) / (50 + 20 * 3 / 5))

    def test_grouped_counts_and_sign_changes_are_reported(self):
        earlier = {"policy_before_et": True, "st_end_over_start": 1.2,
                   "direct_policy_ratio": 1.1, "st_normalized_policy_ratio": 0.99}
        later = {"policy_before_et": False, "st_end_over_start": 1.0,
                 "direct_policy_ratio": 1.0, "st_normalized_policy_ratio": 1.0}
        graphs = [
            {"graph": "first", "guidance_timing_by_block": {framework: [earlier] for framework in DIRECT_GUIDANCE}},
            {"graph": "second", "guidance_timing_by_block": {framework: [later] for framework in DIRECT_GUIDANCE}},
        ]
        result = guidance_timing_sensitivity(graphs)["single"]
        self.assertAlmostEqual(result["direct_geometric_mean_ratio"], 1.1**0.5)
        self.assertAlmostEqual(result["st_normalized_geometric_mean_ratio"], 0.99**0.5)
        self.assertEqual(result["graphs_with_changed_median_direction"], ["first"])
        self.assertEqual(result["direct_policy_block_directions_by_order"], {
            "policy_before_et": {"faster_blocks": 1, "slower_blocks": 0, "equal_blocks": 0},
            "et_before_policy": {"faster_blocks": 0, "slower_blocks": 0, "equal_blocks": 1},
        })
