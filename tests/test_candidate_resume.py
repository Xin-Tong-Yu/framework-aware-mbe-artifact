"""Exercise Candidate Tree checkpoints under simulated native runs."""

import contextlib
from hashlib import sha256
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
SOURCE = ROOT / "src/paper_ablations/single_candidate_tree/v63_run.py"
GRAPHS = ("youtube", "actors")


@unittest.skipUnless(sys.platform == "linux", "the native driver runs on Linux or WSL")
class CandidateResumeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        driver = self.root / "V63_MBET_CORE_SELECT/v63_run.py"
        driver.parent.mkdir()
        shutil.copyfile(SOURCE, driver)
        data = self.root / "data_clean"
        data.mkdir()
        for graph in GRAPHS:
            (data / f"{graph}.txt").write_text(graph, encoding="ascii")

        base = ModuleType("v57_run")
        base.BINARY_MODES = {m: [] for m in ("st_only", "d_prefork", "b_ref")}
        base.COMPILER = ["-O3"]
        base.KNOWN_COUNT = dict.fromkeys(GRAPHS, 5)
        base.execute = self.execute
        base.digest = lambda path: sha256(path.read_bytes()).hexdigest()

        def prepare(source, target):
            shutil.copyfile(source, target)
            return 1

        base.cleanup_graph = prepare
        spec = importlib.util.spec_from_file_location("candidate_bench", driver)
        self.driver = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"v57_run": base}):
            spec.loader.exec_module(self.driver)
        self.calls = []
        self.invalid_count = False

    def execute(self, executable, data, mode, *args):
        graph = data.read_text(encoding="ascii")
        self.calls.append(graph)
        count = 4 if self.invalid_count and graph == "youtube" else 5
        return {"Count": count, "Checksum_XOR": 2, "Checksum_SUM": 3,
                "Search_Time_ms": 1.0, "rss_mib": 1.0, "V56_Hits": 0,
                "V56_Outputs": 0, "V56_PreFork_Skips": 0}

    def run_driver(self, *options, exit_code=0):
        self.calls.clear()
        d = self.driver
        args = ["v63_run.py", "--datasets", *GRAPHS, "--runs", "2", "--timeout", "1200",
                "--min-completed", "2", "--cpu", "none", "--skip-oracle", "--modes", "st_only",
                "v63_inline_st", "v63_core_st", "v63_core_d", *options]
        builds = {mode: (self.root / mode, f"sha_{mode}") for mode in ("map", "inline", "core")}
        with (patch.object(sys, "argv", args), patch.object(d, "build", return_value=builds) as build,
              patch.object(d.resource, "getrlimit", return_value=(256 << 20, d.resource.RLIM_INFINITY)),
              patch.object(d.resource, "setrlimit") as set_stack, contextlib.redirect_stdout(io.StringIO()),
              contextlib.redirect_stderr(io.StringIO())):
            if exit_code:
                with self.assertRaises(SystemExit) as error:
                    d.main()
                self.assertEqual(error.exception.code, exit_code)
            else:
                d.main()
            set_stack.assert_not_called()
        return json.loads(d.CACHE.read_text(encoding="utf-8")), build.call_count

    def test_changed_settings_reject_before_build_and_preserve_files(self):
        self.run_driver()
        d = self.driver
        original = (d.CACHE.read_bytes(), d.REPORT.read_bytes())
        _, builds = self.run_driver("--timeout", "900", exit_code=2)
        self.assertEqual(builds, 0)
        self.assertEqual((d.CACHE.read_bytes(), d.REPORT.read_bytes()), original)

    def test_invalid_reference_count_does_not_poison_the_resume_signature(self):
        self.invalid_count = True
        failed, _ = self.run_driver(exit_code=2)
        self.assertEqual(self.calls, ["youtube"] + ["actors"] * 10)
        self.assertIsNone(failed["datasets"]["youtube"]["signature"])
        self.run_driver(exit_code=2)
        self.assertEqual(self.calls, [])

        self.invalid_count = False
        recovered, _ = self.run_driver("--retry-failed")
        self.assertEqual(self.calls, ["youtube"] * 10)
        self.assertEqual(recovered["datasets"]["youtube"]["signature"], [5, 2, 3])
        self.assertEqual(recovered["datasets"]["actors"], failed["datasets"]["actors"])

    def test_changed_graph_cannot_be_reported_using_stale_saved_results(self):
        baseline, _ = self.run_driver()
        (self.root / "data_clean/youtube.txt").write_text("youtube_changed", encoding="ascii")
        after, _ = self.run_driver(exit_code=2)
        self.assertEqual(self.calls, [])
        self.assertEqual(after["datasets"]["youtube"], baseline["datasets"]["youtube"])

    def test_legacy_checkpoint_is_preserved_for_reconstruction(self):
        self.run_driver()
        d = self.driver
        original = json.loads(d.CACHE.read_text(encoding="utf-8"))
        del original["protocol"]
        d.CACHE.write_text(json.dumps(original), encoding="utf-8")
        payload = d.CACHE.read_bytes()
        _, builds = self.run_driver(exit_code=2)
        self.assertEqual(builds, 0)
        self.assertEqual(d.CACHE.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
