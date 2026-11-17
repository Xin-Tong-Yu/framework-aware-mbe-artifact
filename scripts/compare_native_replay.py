#!/usr/bin/env python3
"""Compare archived paired medians with independently verified native replays."""

import argparse
import json
from pathlib import Path
from statistics import geometric_mean
import sys
from zipfile import BadZipFile

from rebuild_archived_aggregate_tables import ARCHIVE_COLUMNS, GUIDANCE_COLUMNS, load_source, rebuild
from summarize_pure_csv import ROOT, records
from summarize_state_and_guidance import CHECKPOINTS, summarize


def ratio_change(archived, replayed):
    return {"archived_ratio": archived, "replayed_ratio": replayed,
            "speedup_shift_percentage_points": 100 * (replayed - archived)}


def compare(archive, replay, table):
    historical = archive[f"table_{table}"]
    columns = tuple(historical["columns"])
    if tuple(replay["columns"]) != columns:
        raise ValueError("archive and replay contrasts differ")
    by_graph = {graph["graph"]: graph for graph in historical["graphs"]}
    graphs = []
    for observed in replay["graphs"]:
        original = by_graph[observed["graph"]]
        if original["label"] != observed["label"]:
            raise ValueError(f"{observed['graph']}: graph labels differ")
        result = {"graph": observed["graph"], "label": observed["label"],
                  "replayed_input_sha256": observed["input_sha256"],
                  "contrasts": {column: ratio_change(before, after) for column, before, after in
                                zip(columns, original["median_ratios"], observed["median_ratios"])}}
        if table == "vi":
            result["direct_guidance"] = {
                framework: ratio_change(original["direct_guidance"][framework]["median_ratio"],
                                        observed["direct_guidance"][framework]["median_ratio"])
                for framework in GUIDANCE_COLUMNS
            }
        graphs.append(result)

    def paired_gm(key, name):
        return ratio_change(
            geometric_mean(graph[key][name]["archived_ratio"] for graph in graphs),
            geometric_mean(graph[key][name]["replayed_ratio"] for graph in graphs),
        )

    output = {"table": replay["table"], "archived_evidence_type": archive["evidence_type"],
              "archived_source": archive["source"], "replayed_checkpoint_sha256": replay["checkpoint_sha256"],
              "replayed_binaries": replay["binaries"], "replayed_blocks_per_graph": replay["runs"],
              "archived_graphs": len(by_graph), "compared_graphs": len(graphs), "graphs": graphs,
              "geometric_means_over_compared_graphs": {column: paired_gm("contrasts", column)
                                                       for column in columns}}
    if table == "vi":
        output["direct_guidance_geometric_means_over_compared_graphs"] = {
            framework: paired_gm("direct_guidance", framework) for framework in GUIDANCE_COLUMNS
        }
    return output


def main():
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Original aggregate ZIP or its exact CSV entry")
    parser.add_argument("suite", type=Path, help="Native replay framework_ablations directory")
    parser.add_argument("table", choices=ARCHIVE_COLUMNS)
    parser.add_argument("output", type=Path, help="Comparison JSON path")
    parser.add_argument("--graphs", nargs="+", choices=stats, help="Compare only these fully replayed graphs")
    args = parser.parse_args()
    inputs = (args.archive, args.suite / CHECKPOINTS[args.table])
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("Use a separate output path for the comparison report")
    selected = set(args.graphs or stats)
    try:
        archived = rebuild(load_source(args.archive))
        replay = summarize(args.suite, args.table, [stat for name, stat in stats.items() if name in selected], 5)
        result = compare(archived, replay, args.table)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (BadZipFile, OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"Compared Table {result['table']} on {result['compared_graphs']}/{result['archived_graphs']} graphs with five verified replay blocks each")
    return 0


if __name__ == "__main__":
    sys.exit(main())
