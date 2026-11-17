#!/usr/bin/env python3
"""Rebuild Tables IV and VI from the original graph-level paired medians."""

import argparse
from hashlib import sha256 as digest
import json
from pathlib import Path
from statistics import geometric_mean
import sys
from zipfile import BadZipFile, ZipFile

from rebuild_archived_tables import read_csv, write_snapshot
from summarize_pure_csv import ROOT, records, sha256
from summarize_state_and_guidance import CONTRASTS, latex_rows, positive


ORIGINAL_ARCHIVE = "MBE_20261109_RESULTS_FOR_OVERLEAF.zip"
ARCHIVE_SHA256 = "94d1d811e7f3e873828405e8c61130a513db3a79345df2ad5a7bf0bec358fe03"
CSV_ENTRY = "combined_13_graph_metrics.csv"
CSV_SHA256 = "982d023a8141044d40ec1d4b7d88863375e8a77e880c9fc86c6f70e2b68a72a8"
ARCHIVE_COLUMNS = {
    "iv": ("cr_gain_flat", "inline_gain_no_cr", "inline_cr", "inline_gain_cr", "cr_gain_inline"),
    "vi": ("one_et", "one_et_tg", "two_et", "two_et_tg_compact"),
}
GUIDANCE_COLUMNS = {"single": "one_et_tg_vs_one_et", "double": "two_et_tg_compact_vs_two_et"}
EVIDENCE_README = """# Original aggregate evidence for Tables IV and VI

This package preserves the exact CSV entry from `MBE_20261109_RESULTS_FOR_OVERLEAF.zip`.
It contains graph-level paired medians from the original campaigns. The results
in `expected/` are reconstructed rows and geometric means from those medians.
The two per-block timing histories require the original raw checkpoints or a replay.

Check the extracted package with `sha256sum -c SHA256SUMS`, then run this
command from the artifact repository root:

```sh
python3 scripts/rebuild_archived_aggregate_tables.py \\
  /path/to/combined_13_graph_metrics.csv outputs/archived_aggregates
```
"""


def load_source(path):
    if path.suffix.lower() == ".csv":
        raw = path.read_bytes()
    else:
        if sha256(path) != ARCHIVE_SHA256:
            raise ValueError("original aggregate archive SHA-256 does not match")
        with ZipFile(path) as archive:
            raw = archive.read(CSV_ENTRY)
    if digest(raw).hexdigest() != CSV_SHA256:
        raise ValueError("original aggregate CSV SHA-256 does not match")
    return raw


def rebuild(raw):
    stats = records(ROOT / "data/GRAPH_STATISTICS.csv")
    rows = read_csv(raw)
    by_graph = {row["graph"]: row for row in rows}
    if len(rows) != len(stats) or set(by_graph) != {item["graph"] for item in stats}:
        raise ValueError("missing, extra, or duplicate archived graphs")

    output = {"evidence_type": "archived_graph_level_paired_medians",
              "source": {"original_archive": ORIGINAL_ARCHIVE, "archive_sha256": ARCHIVE_SHA256,
                         "csv_entry": CSV_ENTRY, "csv_sha256": CSV_SHA256}}
    for table, columns in ARCHIVE_COLUMNS.items():
        graphs = []
        for stat in stats:
            row = by_graph[stat["graph"]]
            graphs.append({"graph": stat["graph"], "label": stat["paper_label"],
                           "median_ratios": [positive(row[column]) for column in columns]})
        output[f"table_{table}"] = {
            "columns": CONTRASTS[table], "archive_columns": columns, "graphs": graphs,
            "geometric_mean_ratios": [geometric_mean(values)
                                      for values in zip(*(graph["median_ratios"] for graph in graphs))],
        }

    guidance = output["table_vi"]
    guidance["direct_guidance_archive_columns"] = GUIDANCE_COLUMNS
    for graph in guidance["graphs"]:
        row = by_graph[graph["graph"]]
        graph["direct_guidance"] = {framework: {"median_ratio": positive(row[column])}
                                    for framework, column in GUIDANCE_COLUMNS.items()}
    guidance["direct_guidance_geometric_mean_ratios"] = {
        framework: geometric_mean(graph["direct_guidance"][framework]["median_ratio"]
                                  for graph in guidance["graphs"])
        for framework in GUIDANCE_COLUMNS
    }
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Original aggregate ZIP or its exact CSV entry")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--evidence-zip", type=Path, help="Export the exact CSV and reconstructed tables")
    args = parser.parse_args()
    if args.evidence_zip and args.evidence_zip.resolve() == args.source.resolve():
        parser.error("--evidence-zip must use a separate output path")
    try:
        raw = load_source(args.source)
        summary = rebuild(raw)
        files = {"summary.json": json.dumps(summary, indent=2, allow_nan=False) + "\n"}
        files.update({f"table_{table}.tex": latex_rows(summary[f"table_{table}"], table)
                      for table in ARCHIVE_COLUMNS})
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (args.output_dir / name).write_bytes(content.encode("utf-8"))
        if args.evidence_zip:
            entries = {f"expected/{name}": content.encode("utf-8") for name, content in files.items()}
            entries.update({CSV_ENTRY: raw, "README.md": EVIDENCE_README.encode("utf-8")})
            write_snapshot(args.evidence_zip, entries)
    except (BadZipFile, OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS Tables IV and VI: {len(summary['table_iv']['graphs'])} archived graph medians per contrast")
    return 0


if __name__ == "__main__":
    sys.exit(main())
