#!/usr/bin/env python3
"""Validate and summarize the paired Double eligibility-scan experiment."""

import argparse
import json
import math
from pathlib import Path
import re
import statistics
import sys

from summarize_pure_csv import BLOCKS, ROOT, records, sha256, verify_manifest

OFF, GATE1, GATE2, ET1, ET2 = ("double_compact_st_no_gate", "double_compact_st_gate1", "double_compact_st",
                              "double_compact_et1", "double_compact_et2")
MODES = (OFF, GATE1, GATE2, ET1, ET2)
CONTRASTS = {"gate1/off": (GATE1, OFF), "gate2/off": (GATE2, OFF),
             "gate1/et1": (GATE1, ET1), "gate2/et2": (GATE2, ET2),
             "off/et1": (OFF, ET1), "off/et2": (OFF, ET2), "et1/et2": (ET1, ET2)}


def summarize_graph(path, input_info, stat, runner_sha):
    csv_sha, protocol = verify_manifest(path, input_info, runner_sha, MODES)
    rows = records(path)
    keyed = {(int(row["block"]), row["mode"]): row for row in rows}
    expected = {(block, mode) for block in BLOCKS for mode in MODES}
    if len(rows) != len(expected) or set(keyed) != expected:
        raise ValueError(f"{path}: missing or duplicated block/mode entries")

    count = int(stat["reference_bicliques"])
    if {int(row["count"]) for row in rows} != {count}:
        raise ValueError(f"{path}: counts differ from the reference {count}")
    fingerprints = {row["fingerprint"] for row in rows}
    if len(fingerprints) != 1 or not re.fullmatch(r"[0-9]+\|[0-9]+", next(iter(fingerprints))):
        raise ValueError(f"{path}: inconsistent or invalid fingerprints")
    for row in rows:
        if (row["graph"] != input_info["file_name"] or row["kind"] != "double"
                or row["tg"].lower() not in {"0", "false"}):
            raise ValueError(f"{path}: invalid graph, framework, or guidance metadata")
    times = {key: float(row["time_s"]) for key, row in keyed.items()}
    if any(not math.isfinite(time) or time <= 0 for time in times.values()):
        raise ValueError(f"{path}: invalid search times")

    for block in BLOCKS:
        controls = [keyed[block, mode] for mode in (OFF, GATE1, GATE2)]
        if len({row["branch_calls"] for row in controls}) != 1 or not controls[0]["branch_calls"]:
            raise ValueError(f"{path}: different ST branch counts in block {block}")
        off, gate1, gate2 = (int(row["et_attempt"]) for row in controls)
        if off or gate1 > gate2 or any(int(row["et_hit"]) for row in controls):
            raise ValueError(f"{path}: invalid eligibility or solver counts in block {block}")

    contrasts = {}
    for name, (numerator, denominator) in CONTRASTS.items():
        ratios = [times[block, numerator] / times[block, denominator] for block in BLOCKS]
        contrasts[name] = {"block_ratios": ratios, "median_ratio": statistics.median(ratios)}
    result = {"graph": stat["graph"], "label": stat["paper_label"], "count": count,
              "input_sha256": input_info["sha256"], "csv_sha256": csv_sha, "contrasts": contrasts,
              "off_median_s": statistics.median(times[block, OFF] for block in BLOCKS)}
    return result, protocol


def main():
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    inputs = {row["graph"]: row for row in records(ROOT / "data/COLLECTED_INPUT_SHA256.csv")}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--graphs", nargs="+", choices=stats, default=("youtube", "github", "dblp"))
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    try:
        runner_sha = sha256(args.run_directory / "MBE_PURE_ET_GATE.zip")
        results = []
        protocol = None
        for graph in dict.fromkeys(args.graphs):
            result, current = summarize_graph(args.run_directory / f"{graph}.csv", inputs[graph],
                                              stats[graph], runner_sha)
            if protocol is None:
                protocol = current
            elif current != protocol:
                raise ValueError(f"{graph}: execution settings differ from the other graphs")
            results.append(result)
        args.json.write_text(json.dumps({"protocol": protocol, "graphs": results}, indent=2) + "\n",
                             encoding="utf-8")
        print("Graph\tNo-scan ST (s)\t" + "\t".join(CONTRASTS))
        for result in results:
            ratios = "\t".join(f'{row["median_ratio"]:.4f}' for row in result["contrasts"].values())
            print(f'{result["label"]}\t{result["off_median_s"]:.3f}\t{ratios}')
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
