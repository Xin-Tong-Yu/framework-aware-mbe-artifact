"""Check paired profiler comparisons and nonoverlapping phase estimates."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import summarize_double_profile as double
    import summarize_single_profile as single
finally:
    sys.path.pop(0)


class PhaseComparisonTests(unittest.TestCase):
    def test_double_subtracts_nested_output_and_fallback_once(self):
        control = {"mode": "double_compact_et2", "time_s": "0.10", "branch_calls": "200",
                   "et_attempt": "4", "et_hit": "3", "et_degree2_hit": "3", "et_output_count": "10",
                   "et_profile_interval": ""}
        sampled = {**control, "mode": "double_compact_et2_profile", "time_s": "0.12",
                   "et_profile_interval": "64", "et_gate_calls": "100", "et_gate_samples": "2",
                   "et_gate_passes": "4", "et_terminal_calls": "4", "et_terminal_samples": "2", "et_fallbacks": "1",
                   "et_gate_ms": "0.10", "et_setup_ms": "0.30", "et_build_ms": "0.60", "et_decompose_ms": "0.25",
                   "et_generate_ms": "0.70", "et_emit_ms": "0.15", "et_fallback_ms": "0.20"}
        result = double.check_pair(control, sampled)
        times = result["exclusive_estimated_ms"]
        self.assertAlmostEqual(times["successful_setup_and_complement"], 1.4)
        self.assertAlmostEqual(times["failed_setup_and_complement"], 0.4)
        self.assertAlmostEqual(times["enumeration_without_callback"], 1.1)
        self.assertAlmostEqual(times["terminal_output_callback"], 0.3)
        self.assertAlmostEqual(sum(times.values()), 8.7)

    def test_single_counts_failed_attempt_time_once_and_retains_missing_samples(self):
        control = {"mode": "single_et2", "time_s": "0.10", "count": "100", "et_attempt": "4", "et_hit": "3",
                   "et_degree2_hit": "2", "single_profile_interval": ""}
        sampled = {**control, "mode": "single_et2_profile", "time_s": "0.12", "single_profile_interval": "64",
                   "single_gate_calls": "100", "single_gate_samples": "2", "single_terminal_samples": "2",
                   "single_fallbacks": "1", "single_output_calls": "125", "single_output_samples": "5",
                   "single_gate_ns": "200000", "single_terminal_ns": "12000000", "single_fallback_ns": "3000000",
                   "single_matching_ns": "0", "single_generate_ns": "6000000", "single_commit_ns": "2000000",
                   "single_output_ns": "400000"}
        result = single.check_pair(control, sampled)
        self.assertAlmostEqual(sum(result["exclusive_estimated_ms"].values()), 44.0)
        self.assertAlmostEqual(result["estimated_ms"]["fallback"], 6.0)
        sampled["single_terminal_samples"] = "0"
        for phase in ("terminal", "fallback", "generate", "commit"):
            sampled[f"single_{phase}_ns"] = "0"
        sparse = single.check_pair(control, sampled)["exclusive_estimated_ms"]
        self.assertIsNone(sparse["mis_generation"])
        self.assertIsNone(sparse["result_tree_integration"])
        self.assertEqual(sparse["matching_with_tree_updates"], 0.0)

    def test_terminal_changes_keep_ordinary_profiled_and_sampled_deltas_separate(self):
        et1 = {"blocks": [self.block(1, 100, 150, 2, 3), self.block(2, 80, 90, None, 4)]}
        et2 = {"blocks": [self.block(1, 120, 145, 5, 2), self.block(2, 75, 100, 8, 2)]}
        result = double.compare_terminals(et1, et2)
        self.assertEqual(result["ordinary_search_change_ms"], {"available_blocks": 2, "median": 7.5, "range": [-5, 20]})
        self.assertEqual(result["profiled_search_change_ms"], {"available_blocks": 2, "median": 2.5, "range": [-5, 10]})
        self.assertEqual(result["profiled_minus_ordinary_change_ms"],
                         {"available_blocks": 2, "median": -5.0, "range": [-25, 15]})
        self.assertAlmostEqual(result["profiled_search_speed_ratio"]["median"], (150 / 145 + 90 / 100) / 2)
        self.assertEqual(result["estimated_phase_changes_ms"]["eligibility"],
                         {"available_blocks": 1, "median": 3, "range": [3, 3]})
        self.assertEqual(result["estimated_phase_changes_ms"]["output"]["range"], [-2, -1])
        self.assertEqual(result["estimated_phase_total_change_ms"], {"available_blocks": 1, "median": 2, "range": [2, 2]})
        self.assertEqual(result["profiled_change_minus_estimated_phases_ms"],
                         {"available_blocks": 1, "median": -7, "range": [-7, -7]})
        self.assertIsNone(result["blocks"][1]["estimated_phase_changes_ms"]["eligibility"])
        self.assertIsNone(result["blocks"][1]["estimated_phase_total_change_ms"])
        self.assertIsNone(result["blocks"][1]["profiled_change_minus_estimated_phases_ms"])
        et2["blocks"][0]["profile_seed"] = "mismatch"
        with self.assertRaisesRegex(ValueError, "blocks or seeds differ"):
            double.compare_terminals(et1, et2)

    def test_original_search_work_is_checked_for_both_kinds_of_measurement(self):
        original = [
            {"block": str(block), "mode": mode, "kind": "single", "time_s": str(index + 1),
             "count": "19", "fingerprint": "20|21", "et": str(index != 0),
             "et_attempt": str(index), "et_hit": str(index), "et_degree2_hit": str(int(index == 2))}
            for block in double.BLOCKS for index, mode in enumerate(single.BASE)
        ]
        measured = [*original, *({**row, "mode": row["mode"] + "_profile"} for row in original)]
        summary = double.compare_original_work(original, measured, single.BASE)
        self.assertEqual(summary["matched_search_work"], {"ordinary": 15, "profiled": 15})
        self.assertEqual(summary["original_et2_minus_et1_ms"]["median"], 1000)
        measured[-1]["et_hit"] = "3"
        with self.assertRaisesRegex(ValueError, "replay changed et_hit"):
            double.compare_original_work(original, measured, single.BASE)

    @staticmethod
    def block(number, search, profiled_search, eligibility, output):
        return {"block": number, "profile_seed": str(number), "control_search_ms": search,
                "profiled_search_ms": profiled_search,
                "exclusive_estimated_ms": {"eligibility": eligibility, "output": output}}
