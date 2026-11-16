#!/usr/bin/env python3
"""Rebuild the pure ET1/ET2 table from verified paired-block records."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

from validate_pure_csv import EXPECTED, MODE_KIND, validate

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = sorted({block for block, _ in EXPECTED})
FAMILIES = {"single": "single", "double": "double_compact"}
COMPARISONS = {"ET1/ST": ("st", "et1"), "ET2/ST": ("st", "et2"),
               "ET2/ET1": ("et1", "et2")}


def records(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(path, input_info, runner_sha, modes):
    manifest = path.with_suffix(".csv.manifest.json")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if metadata["csv_sha256"] != sha256(path):
        raise ValueError(f"{path}: CSV SHA-256 does not match its run manifest")
    params = metadata["parameters"]
    required = {"graph": input_info["file_name"], "input_sha256": input_info["sha256"],
                "runner_sha256": runner_sha, "modes": list(modes), "repeats": len(BLOCKS),
                "min_left": 1, "min_right": 1}
    mismatched = [key for key, val in required.items() if params.get(key) != val]
    if mismatched:
        raise ValueError(f"{manifest}: mismatched {'/'.join(mismatched)}")
    binaries = params["executables"]
    if (set(binaries) != set(modes)
            or any(not re.fullmatch(r"[0-9a-f]{64}", digest) for digest in binaries.values())):
        raise ValueError(f"{manifest}: invalid executable identities")
    protocol = {key: value for key, value in params.items() if key not in {"graph", "input_sha256"}}
    return metadata["csv_sha256"], protocol


def load_graph(path, input_info, stat, runner_sha):
    errors = validate(path, input_info["file_name"])
    if errors:
        raise ValueError(f"{path}: {'; '.join(errors)}")
    csv_sha, protocol = verify_manifest(path, input_info, runner_sha, MODE_KIND)
    return summarize_graph_rows(records(path), input_info, stat, csv_sha), protocol


def summarize_graph_rows(rows, input_info, stat, csv_sha):
    expected_count = int(stat["reference_bicliques"])
    if {int(row["count"]) for row in rows} != {expected_count}:
        raise ValueError(f"{stat['graph']}: count differs from the reference {expected_count}")
    times = {(int(row["block"]), row["mode"]): float(row["time_s"]) for row in rows}
    result = {"graph": stat["graph"], "label": stat["paper_label"], "input_sha256": input_info["sha256"],
              "csv_sha256": csv_sha, "count": expected_count, "frameworks": {}}
    for framework, prefix in FAMILIES.items():
        comparisons = {}
        for label, (reference, variant) in COMPARISONS.items():
            ratios = [times[block, f"{prefix}_{reference}"] / times[block, f"{prefix}_{variant}"]
                      for block in BLOCKS]
            comparisons[label] = {"block_ratios": ratios, "median_ratio": statistics.median(ratios)}
        result["frameworks"][framework] = {
            "median_st_s": statistics.median(times[block, f"{prefix}_st"] for block in BLOCKS),
            "comparisons": comparisons,
        }

    return result


def summarize(directory, stats, runner):
    inputs = {row["graph"]: row for row in records(ROOT / "data/COLLECTED_INPUT_SHA256.csv")}
    runner_sha = sha256(runner)
    graphs = []
    protocol = None
    for stat in stats:
        graph = stat["graph"]
        result, current = load_graph(directory / f"{graph}.csv", inputs[graph], stat, runner_sha)
        if protocol is None:
            protocol = current
        elif current != protocol:
            raise ValueError(f"{graph}: execution settings differ from the other graphs")
        graphs.append(result)

    return pure_summary(graphs, protocol)


def pure_summary(graphs, protocol):
    gm = {}
    for framework in FAMILIES:
        gm[framework] = {
            label: statistics.geometric_mean(g["frameworks"][framework]["comparisons"][label]["median_ratio"]
                                             for g in graphs)
            for label in COMPARISONS
        }
    return {"protocol": protocol, "graphs": graphs, "geometric_mean_ratios": gm}


def speedup(ratio):
    percent = round(100 * (ratio - 1), 1)
    return (f"{percent:+.1f}" if percent else "0.0") + r"\%"


def latex_rows(summary):
    lines = []
    for graph in summary["graphs"]:
        cells = [graph["label"]]
        for framework in FAMILIES:
            result = graph["frameworks"][framework]
            cells.append(f'{result["median_st_s"]:.3f}')
            cells.extend(speedup(result["comparisons"][label]["median_ratio"]) for label in COMPARISONS)
        lines.append(" & ".join(cells) + r" \\")
    tail = [rf'\textbf{{GM$_{{{len(summary["graphs"])}}}$}}']
    for framework in FAMILIES:
        tail.append("--")
        tail.extend(speedup(summary["geometric_mean_ratios"][framework][label]) for label in COMPARISONS)
    lines.append(" & ".join(tail) + r" \\")
    return "\n".join(lines) + "\n"


def main():
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--runner", type=Path, default=ROOT / "runners/MBE_PURE_ET1_ET2.zip")
    parser.add_argument("--graphs", nargs="+", choices=stats, help="Verify a named subset. Default: all 13.")
    parser.add_argument("--json", type=Path, help="Write pairing, provenance, and per-graph ratios.")
    parser.add_argument("--latex", type=Path, help="Write table rows. Default: print to stdout.")
    args = parser.parse_args()
    selected = set(args.graphs) if args.graphs else set(stats)
    try:
        summary = summarize(args.run_directory, [row for key, row in stats.items() if key in selected],
                            args.runner)
        table = latex_rows(summary)
        if args.json:
            args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        if args.latex:
            args.latex.write_text(table, encoding="utf-8")
        else:
            print(table, end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(summary['graphs'])}/{len(stats)} graphs, {len(EXPECTED)} records per graph", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
