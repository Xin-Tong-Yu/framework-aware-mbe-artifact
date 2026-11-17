"""Exercise the six-mode driver with simulated native failures and legacy checkpoints."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/paper_ablations/termination_guidance/bench.py"
GRAPHS = ("youtube", "actors")


@unittest.skipUnless(sys.platform == "linux", "the native driver runs on Linux or WSL")
class GuidanceResumeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        driver = self.root / "MBE_CORRECTED_13DATA/bench.py"
        driver.parent.mkdir()
        shutil.copyfile(SOURCE, driver)
        for relpath in ("MBE_FAST_FOUR_MODES/run.sh", "MBE_FAST_FOUR_MODES/bin/one_core",
                        *(f"MBE_CORRECTED_13DATA/bin/{mode}_safe" for mode in
                          ("two_st", "two_et", "two_et_tg_compact")),
                        *(f"data_clean/{graph}.txt" for graph in GRAPHS)):
            path = self.root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relpath, encoding="utf-8")

        spec = importlib.util.spec_from_file_location("guidance_bench", driver)
        self.driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.driver)
        self.checkpoint = self.root / "diagnostics/MBE_CORRECTED_MAIN_CHECKPOINT.json"
        self.calls = []
        self.failure = None

    def execute(self, cmd, timeout, cpu, root, memory_limit):
        graph = Path(cmd[-1] if cmd[0] == "bash" else cmd[2]).name.split(".")[0]
        self.calls.append(graph)
        failure = self.failure if graph == GRAPHS[0] and self.calls.count(graph) == 3 else None
        return (1 if failure == "error" else 0), failure or "ok", "", 1.0, None

    @staticmethod
    def statistics(mode, output, wall_s):
        xor = 1 if mode.startswith("one_") else 2
        return {"count": 5, "xor": xor + (10 if output == "mismatch" else 0),
                "sum": 7, "ms": 1.0, "wall_s": wall_s}

    def run_driver(self):
        self.calls.clear()
        prepare = ModuleType("prepare_corrected")
        prepare.prepare_corrected = lambda *args: None
        counts = ModuleType("known_counts")
        counts.KNOWN_COUNT = dict.fromkeys(GRAPHS, 5)
        args = ["bench.py", "--project-root", str(self.root), "--datasets", *GRAPHS,
                "--runs", "3", "--cpu", "none", "--skip-build", "--retry-failed"]
        with (patch.dict(sys.modules, {"prepare_corrected": prepare, "known_counts": counts}),
              patch.object(sys, "argv", args), patch.object(self.driver, "execute", self.execute),
              patch.object(self.driver, "parse_run", self.statistics), contextlib.redirect_stdout(io.StringIO())):
            result = self.driver.main()
        return result, json.loads(self.checkpoint.read_text(encoding="utf-8"))

    def test_native_failure_leaves_one_partial_block_and_runs_next_graph(self):
        self.failure = "error"
        status, failed = self.run_driver()
        self.assertEqual(status, 1)
        self.assertEqual(self.calls, ["youtube"] * 3 + ["actors"] * 24)
        self.assertEqual(len(failed["blocks"]["youtube"]), 1)
        self.assertFalse(failed["blocks"]["youtube"][0]["completed"])

        self.failure = None
        status, resumed = self.run_driver()
        self.assertEqual(status, 0)
        self.assertEqual(self.calls, ["youtube"] * 24)
        self.assertEqual(resumed["blocks"]["actors"], failed["blocks"]["actors"])
        self.assertEqual(resumed["meta"]["created"], failed["meta"]["created"])

    def test_fingerprint_mismatch_stops_the_graph_after_its_current_block(self):
        self.failure = "mismatch"
        status, failed = self.run_driver()
        self.assertEqual(status, 1)
        self.assertEqual(self.calls, ["youtube"] * 8 + ["actors"] * 24)
        self.assertTrue(failed["blocks"]["youtube"][0]["validation"].startswith("FAIL"))

    def test_legacy_bad_block_is_replaced_without_repeating_later_valid_blocks(self):
        status, legacy = self.run_driver()
        self.assertEqual(status, 0)
        legacy["blocks"]["youtube"][0]["validation"] = "FAIL output mismatch"
        self.checkpoint.write_text(json.dumps(legacy), encoding="utf-8")

        status, resumed = self.run_driver()
        self.assertEqual(status, 0)
        self.assertEqual(self.calls, ["youtube"] * 8)
        self.assertEqual(resumed["blocks"]["youtube"][1:], legacy["blocks"]["youtube"][1:])
        self.assertTrue(all(block["validation"].startswith("PASS") for block in resumed["blocks"]["youtube"]))


if __name__ == "__main__":
    unittest.main()
