"""Regression checks for interruption and recovery of pure ET matrices."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODES = ["single_st", "double_compact_st"]


@unittest.skipUnless(sys.platform == "linux", "native runners use Linux resource and file locks")
class PureResumeTests(unittest.TestCase):
    def setUp(self):
        source = ROOT / "src/pure_et1_et2/__main__.py"
        spec = importlib.util.spec_from_file_location("pure_runner", source)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.graph = self.root / "graph.txt"
        self.graph.write_text("1 1 1\n0 0\n", encoding="ascii")
        self.archive = self.root / "runner.zip"
        self.archive.write_bytes(b"runner snapshot")
        self.output = self.root / "runs.csv"
        self.checkpoint = self.root / "runs.csv.checkpoint.json"
        self.manifest = self.root / "runs.csv.manifest.json"
        self.args = SimpleNamespace(graph=self.graph, repeats=3, seed=761, timeout=30,
                                    min_left=1, min_right=1, modes="pure", resume=True)
        self.calls = []

        for name, returns in (("build", self.archive), ("compiler_identity", ("fake compiler",)),
                              ("graph_variants", (self.graph, self.graph))):
            patcher = patch.object(self.runner, name, return_value=returns)
            patcher.start()
            self.addCleanup(patcher.stop)

    def result(self, mode, *args, **kwargs):
        self.calls.append(mode)
        kind, flags = self.runner.MODES[mode]
        row = dict.fromkeys(self.runner.MATRIX_FIELDS, "")
        row.update(graph=self.graph.name, mode=mode, kind=kind, count="1", et=flags["et"],
                   tg=flags["tg"], et_hit="0", fingerprint="12|34" if kind == "single" else "56|78",
                   time_s=float(len(self.calls)), wall_s=float(len(self.calls)) + 0.01)
        return row, ""

    def run_stub(self, execute):
        with patch.object(self.runner, "execute", side_effect=execute):
            self.runner.run_matrix(self.args, self.root, self.archive, MODES, self.output)

    def test_mid_block_interruption_recovers_only_finished_blocks(self):
        def interrupt(mode, *args, **kwargs):
            if len(self.calls) == 3:
                raise KeyboardInterrupt
            return self.result(mode, *args, **kwargs)

        with self.assertRaises(KeyboardInterrupt):
            self.run_stub(interrupt)
        self.assertFalse(self.output.exists())
        complete = self.checkpoint.read_bytes()
        saved = json.loads(complete)
        self.assertEqual(len(saved["blocks"]), 1)
        original_times = [row["time_s"] for row in saved["blocks"][0]]

        self.args.seed += 1
        with self.assertRaises(SystemExit):
            self.run_stub(self.result)
        self.args.seed -= 1
        saved["blocks"][0][0]["time_s"] = 99.0
        self.checkpoint.write_text(json.dumps(saved), encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_stub(self.result)
        self.checkpoint.write_bytes(complete)

        self.calls.clear()
        self.run_stub(self.result)
        self.assertEqual(len(self.calls), 4)
        with self.output.open(newline="", encoding="utf-8") as stream:
            actual = list(csv.DictReader(stream))
        self.assertEqual(len(actual), 6)
        self.assertEqual([row["mode"] for row in actual[2:]], self.calls)
        self.assertEqual([float(row["time_s"]) for row in actual[:2]], original_times)
        self.assertFalse(self.checkpoint.exists())
        self.assertEqual(json.loads(self.manifest.read_text())["csv_sha256"],
                         self.runner.sha256(self.output))

    def test_interruption_between_final_csv_and_manifest_recovers(self):
        replace = Path.replace

        def interrupt_before_manifest(path, target):
            if target == self.manifest:
                raise KeyboardInterrupt
            return replace(path, target)

        with patch.object(Path, "replace", interrupt_before_manifest):
            with self.assertRaises(KeyboardInterrupt):
                self.run_stub(self.result)
        original = self.output.read_bytes()
        self.assertTrue(self.checkpoint.exists())
        self.assertFalse(self.manifest.exists())
        self.calls.clear()
        self.run_stub(self.result)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.output.read_bytes(), original)
        self.assertTrue(self.manifest.exists())
        self.assertFalse(self.checkpoint.exists())

        self.output.write_bytes(original + b"corrupt")
        with self.assertRaises(SystemExit):
            self.run_stub(self.result)

    def test_profile_blocks_preserve_distinct_seeds_on_resume(self):
        self.args.modes = "single-profile"
        modes = self.runner.SINGLE_PROFILE_MATRIX

        def recorded(mode, *args, **kwargs):
            row, stdout = self.result(mode, *args, **kwargs)
            row["profile_seed"] = kwargs.get("profile_seed") or ""
            return row, stdout

        def interrupted(mode, *args, **kwargs):
            if len(self.calls) == len(modes) + 1:
                raise KeyboardInterrupt
            return recorded(mode, *args, **kwargs)

        with patch.object(self.runner, "execute", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.runner.run_matrix(self.args, self.root, self.archive, modes, self.output)

        checkpoint = json.loads(self.checkpoint.read_bytes())
        original = checkpoint["blocks"][0]
        seeds = checkpoint["parameters"]["profile_seeds"]
        self.assertEqual(len(set(seeds)), self.args.repeats)

        self.calls.clear()
        with patch.object(self.runner, "execute", side_effect=recorded):
            self.runner.run_matrix(self.args, self.root, self.archive, modes, self.output)
        self.assertEqual(len(self.calls), 2 * len(modes))
        with self.output.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            expected = seeds[int(row["block"]) - 1] if row["mode"].endswith("_profile") else ""
            self.assertEqual(row["profile_seed"], expected)
        self.assertEqual([float(row["time_s"]) for row in rows[:len(modes)]],
                         [row["time_s"] for row in original])


if __name__ == "__main__":
    unittest.main()
