#!/usr/bin/env python3
"""Compare independently validated native replays with original measurements."""

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


def load_archive(path, table, stats):
    if path.is_dir():
        original = summarize(path, table, stats, 5, include_signatures=True)
        return {"evidence_type": "archived_native_checkpoints",
                "source": {"checkpoint_sha256": original["checkpoint_sha256"],
                           "binaries": original["binaries"], "blocks_per_graph": original["runs"]},
                f"table_{table}": original}
    if table not in ARCHIVE_COLUMNS:
        raise ValueError(f"Table {table.upper()} requires the original checkpoint directory")
    return rebuild(load_source(path))


def compare(archive, replay, table):
    historical = archive[f"table_{table}"]
    columns = tuple(historical["columns"])
    if tuple(replay["columns"]) != columns:
        raise ValueError("archive and replay contrasts differ")
    has_original_runs = "checkpoint_sha256" in historical
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
        if has_original_runs:
            if (original["input_sha256"], original["count"]) != (observed["input_sha256"], observed["count"]):
                raise ValueError(f"{observed['graph']}: original input or reference count differs")
            result["archived_input_sha256"] = original["input_sha256"]
            saved_signatures = original["output_signatures"]
            fresh_signatures = observed["output_signatures"]
            if saved_signatures.keys() != fresh_signatures.keys():
                raise ValueError(f"{observed['graph']}: fingerprint groups differ")
            for group, signature in saved_signatures.items():
                if signature != fresh_signatures[group]:
                    raise ValueError(f"{observed['graph']}: original and replayed {group} fingerprints differ")
            result["matched_output_signatures"] = fresh_signatures
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
    if has_original_runs:
        output["binary_sha256_matches"] = {mode: identity == historical["binaries"][mode]
                                          for mode, identity in replay["binaries"].items()}
        output["matched_output_signature_count"] = sum(len(graph["matched_output_signatures"]) for graph in graphs)
    if table == "vi":
        output["direct_guidance_geometric_means_over_compared_graphs"] = {
            framework: paired_gm("direct_guidance", framework) for framework in GUIDANCE_COLUMNS
        }
    return output


def main():
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Original checkpoint directory or aggregate ZIP/CSV")
    parser.add_argument("suite", type=Path, help="Native replay framework_ablations directory")
    parser.add_argument("table", choices=CHECKPOINTS)
    parser.add_argument("output", type=Path, help="Comparison JSON path")
    parser.add_argument("--graphs", nargs="+", choices=stats, help="Compare only these fully replayed graphs")
    args = parser.parse_args()
    archive_input = args.archive / CHECKPOINTS[args.table] if args.archive.is_dir() else args.archive
    inputs = (archive_input, args.suite / CHECKPOINTS[args.table])
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("Use a separate output path for the comparison report")
    selected = set(args.graphs or stats)
    try:
        archived = load_archive(args.archive, args.table, list(stats.values()))
        replay = summarize(args.suite, args.table, [stat for name, stat in stats.items() if name in selected], 5,
                           include_signatures=args.archive.is_dir())
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
