"""Exercise the Vector/Compact paired-block driver with simulated native runs."""

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
SOURCE = ROOT / "src/paper_ablations/double_state/bench.py"
GRAPHS = ("youtube", "actors")


@unittest.skipUnless(sys.platform == "linux" and Path("/usr/bin/time").is_file(),
                     "the Double measurement driver requires Linux and GNU time")
class DoubleRepresentationResumeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        driver = self.root / "MBE_NEW_P0_20261109/bench.py"
        driver.parent.mkdir()
        shutil.copyfile(SOURCE, driver)
        for name in ("MBE_CORRECTED_13DATA/prepare_corrected.py", "MBE_FAST_FOUR_MODES/run.sh",
                     *(f"MBE_NEW_P0_20261109/bin/double_{representation}_{setting}"
                       for representation in ("vector", "compact")
                       for setting in ("st", "et_tg")),
                     *(f"data_clean/{graph}.txt" for graph in GRAPHS)):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("representation_bench", driver)
        self.driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.driver)
        self.cp = driver.parent / "diagnostics/P0_DOUBLE_CHECKPOINT.json"
        self.calls = []
        self.failure = None

    def execute(self, cmd, cpu, timeout, memory):
        graph = Path(cmd[2]).name.split(".")[0]
        self.calls.append(graph)
        missing_rss = self.failure == "rss" and graph == "youtube"
        stderr = "" if missing_rss else "MBE_PEAK_RSS_KB=2048\n"
        return graph, stderr, 0.012

    def parse(self, mode, graph):
        differences = self.failure == "branches" and graph == "youtube" and mode == "compact_et_tg"
        return {"count": self.driver.KNOWN[graph], "ms": 10.0, "fp": (17, 61),
                "branches": 161 if differences else 160}

    def run_driver(self):
        self.calls.clear()
        prepare = ModuleType("prepare_corrected")
        prepare.prepare_corrected = lambda *args: None
        argv = ["bench.py", "--root", str(self.root), "--kind", "double", "--runs", "2", "--cpu", "none",
                "--skip-build", "--retry-failed", "--process-only", *GRAPHS]
        with (patch.dict(sys.modules, {"prepare_corrected": prepare}), patch.object(sys, "argv", argv),
              patch.object(sys, "path", sys.path.copy()), patch.object(self.driver, "execute", self.execute),
              patch.object(self.driver, "parse", self.parse), contextlib.redirect_stdout(io.StringIO())):
            status = self.driver.main()
        return status, json.loads(self.cp.read_text(encoding="utf-8"))

    def test_branch_disagreement_stops_graph_after_current_block(self):
        self.failure = "branches"
        status, document = self.run_driver()
        self.assertEqual(status, 1)
        self.assertEqual(self.calls, ["youtube"] * 6 + ["actors"] * 12)
        problem = document["blocks"]["youtube"][0]["validation"]
        self.assertIn("vector_et_tg/compact_et_tg", problem)
        self.assertTrue(problem.startswith("FAIL"))

    def test_missing_st_rss_stops_before_following_runs(self):
        self.failure = "rss"
        status, document = self.run_driver()
        self.assertEqual(status, 1)
        self.assertEqual(self.calls, ["youtube"] + ["actors"] * 12)
        self.assertIn("peak RSS", document["failed_datasets"]["youtube"])

    def test_legacy_untrusted_block_replaced_but_later_block_preserved(self):
        status, original = self.run_driver()
        self.assertEqual(status, 0)
        original["blocks"]["youtube"][0]["jobs"][0]["branches"] = 999
        self.cp.write_text(json.dumps(original), encoding="utf-8")
        status, repaired = self.run_driver()
        self.assertEqual(status, 0)
        self.assertEqual(self.calls, ["youtube"] * 6)
        self.assertEqual(original["blocks"]["youtube"][1], repaired["blocks"]["youtube"][1])
        self.assertEqual(original["blocks"]["actors"], repaired["blocks"]["actors"])

    def test_single_baseline_allows_original_reporting_contract(self):
        jobs = [{"mode": mode, "status": "OK", "ms": 20.0, "count": 41,
                 "fp": [1, 2] if mode.startswith("new_") else None}
                for mode in self.driver.block_sequence("single", 1234)]
        self.assertIsNone(self.driver.block_problem(jobs, "single", 41))


if __name__ == "__main__":
    unittest.main()
