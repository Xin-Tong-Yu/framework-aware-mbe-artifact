"""Reject internally consistent pure runs that disagree with the paper."""
import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_pure_csv", ROOT / "scripts/validate_pure_csv.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class PureCsvValidationTests(unittest.TestCase):
    def validate_rows(self, *, count=16261, time_s="0.01", graph="forum.txt"):
        fields = sorted(VALIDATOR.REQUIRED)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for block in range(1, 6):
                    for mode, kind in VALIDATOR.MODE_KIND.items():
                        writer.writerow(dict(graph=graph, block=block, mode=mode, kind=kind,
                                             time_s=time_s, count=count, fingerprint="1|2", tg=False))
            return VALIDATOR.validate(path, graph)

    def test_complete_reference_count_passes(self):
        self.assertEqual(self.validate_rows(), [])

    def test_identical_wrong_count_is_rejected(self):
        self.assertTrue(any("expected Table I count 16261" in error
                            for error in self.validate_rows(count=16260)))

    def test_zero_and_nonfinite_times_are_rejected(self):
        for value in ("0", "-0.01", "nan", "inf"):
            with self.subTest(time_s=value):
                self.assertTrue(any("invalid count or time" in error
                                    for error in self.validate_rows(time_s=value)))

    def test_unknown_fixture_keeps_internal_consistency_validation(self):
        self.assertEqual(self.validate_rows(graph="fixture.txt", count=7), [])


if __name__ == "__main__":
    unittest.main()
