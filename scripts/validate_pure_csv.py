#!/usr/bin/env python3
"""Validate a six-mode, five-block pure ET1/ET2 benchmark CSV.

This checks coverage and within-framework result agreement. It does not
establish that a particular implementation enumerates the mathematically
correct answer set, nor does it benchmark any algorithm.
"""
import argparse
import csv
import math
import sys
from pathlib import Path

MODE_KIND = {
    "single_st": "single",
    "single_et1": "single",
    "single_et2": "single",
    "double_compact_st": "double",
    "double_compact_et1": "double",
    "double_compact_et2": "double",
}
EXPECTED = {(block, mode) for block in range(1, 6) for mode in MODE_KIND}
REQUIRED = {"graph", "block", "mode", "kind", "time_s", "count", "fingerprint", "tg"}


def validate(path, expected_graph=None):
    errors = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
                return ["missing required CSV columns: " + ", ".join(sorted(REQUIRED - set(reader.fieldnames or [])))]
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return [str(exc)]

    if len(rows) != 30:
        errors.append(f"expected 30 rows, found {len(rows)}")
    seen = set()
    counts = set()
    graphs = set()
    fingerprints = {"single": set(), "double": set()}
    for lineno, row in enumerate(rows, start=2):
        try:
            block = int(row["block"])
            mode = row["mode"].strip()
            kind = row["kind"].strip()
            graph = row["graph"].strip()
            count = int(row["count"])
            time_s = float(row["time_s"])
            fp = row["fingerprint"].strip()
            tg = row["tg"].strip().lower()
            if mode not in MODE_KIND:
                raise ValueError("unexpected mode " + mode)
            if kind != MODE_KIND[mode]:
                raise ValueError("mode/kind mismatch")
            if block not in range(1, 6):
                raise ValueError("block out of range")
            if not graph:
                raise ValueError("missing graph name")
            if count <= 0 or not math.isfinite(time_s) or time_s < 0:
                raise ValueError("invalid count or time")
            if not fp or "|" not in fp:
                raise ValueError("invalid fingerprint")
            if tg not in ("0", "false"):
                raise ValueError("pure ablation must have TG disabled")
            key = (block, mode)
            if key in seen:
                errors.append(f"duplicate block/mode at line {lineno}: {key}")
            seen.add(key)
            counts.add(count)
            graphs.add(graph)
            fingerprints[kind].add(fp)
        except (TypeError, ValueError, AttributeError) as exc:
            errors.append(f"line {lineno}: {exc}")

    missing = EXPECTED - seen
    unexpected = seen - EXPECTED
    if missing:
        errors.append(f"missing {len(missing)} block/mode combinations: {sorted(missing)}")
    if unexpected:
        errors.append(f"unexpected combinations: {sorted(unexpected)}")
    if len(graphs) != 1:
        errors.append(f"mixed graph names: {sorted(graphs)}")
    if expected_graph is not None and graphs != {expected_graph}:
        errors.append(f"graph field must equal {expected_graph!r}, found {sorted(graphs)}")
    if len(counts) != 1:
        errors.append(f"inconsistent result counts: {sorted(counts)}")
    for kind, values in fingerprints.items():
        if len(values) != 1:
            errors.append(f"inconsistent {kind} fingerprints: {len(values)} distinct values")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--graph", help="expected graph filename, for example youtube.txt")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    errors = validate(args.csv_file, args.graph)
    if errors:
        if not args.quiet:
            for issue in errors:
                print("FAIL:", issue, file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"PASS: {args.csv_file}: six modes x five blocks; counts and fingerprints consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
