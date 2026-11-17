#!/usr/bin/env python3
"""Compare archived and replayed Table VII runs after checking search work."""

import argparse
from hashlib import sha256 as digest
import json
from pathlib import Path
import sys
from zipfile import BadZipFile, ZipFile

from compare_native_replay import ratio_change
from rebuild_archived_tables import read_pure_rows
from summarize_pure_csv import (COMPARISONS, FAMILIES, ROOT, load_rows, pure_summary,
                                records, sha256, summarize_graph_rows)


COMMON_COUNTERS = ("count", "et_attempt", "et_hit", "et_degree2_hit")
DOUBLE_COUNTERS = ("branch_calls", "et_output_count")


def search_work(rows):
    result = {}
    for row in rows:
        block = int(row["block"])
        mode = row["mode"]
        fields = COMMON_COUNTERS + (DOUBLE_COUNTERS if row["kind"] == "double" else ())
        values = {name: int(row[name]) for name in fields}
        fingerprint = tuple(map(int, row["fingerprint"].split("|")))
        if min(values.values()) < 0 or any(not 0 <= field < 2**64 for field in fingerprint):
            raise ValueError(f"block {block} {mode}: invalid counter or fingerprint")
        values["fingerprint"] = fingerprint
        enabled = row["et"].strip().lower()
        accepted = {"0", "false"} if mode.endswith("_st") else {"1", "true"}
        if enabled not in accepted or row.get("et_pattern_components") not in (None, "", "0"):
            raise ValueError(f"block {block} {mode}: unexpected ET or pattern-reuse setting")
        result[block, mode] = values
    return result


def compare_work(original, replay):
    before, after = search_work(original), search_work(replay)
    if before.keys() != after.keys():
        raise ValueError("different Table VII block/mode coverage")
    for (block, mode), original_values in before.items():
        replay_values = after[block, mode]
        changed = [field for field, value in original_values.items() if replay_values.get(field) != value]
        if changed:
            raise ValueError(f"block {block} {mode}: replay changed {', '.join(changed)}")
    return len(before)


def native_sources(path):
    with ZipFile(path) as archive:
        members = {name: digest(archive.read(name)).hexdigest() for name in archive.namelist()
                   if name.startswith("engine/") and name.endswith((".cpp", ".hpp"))}
    if not members:
        raise ValueError(f"{path}: missing native source members")
    return members


def compare(archived, historical_runner, replay_directory, replay_runner, stats):
    identities = {row["graph"]: row for row in records(ROOT / "data/COLLECTED_INPUT_SHA256.csv")}
    old_sha = sha256(historical_runner)
    new_sha = sha256(replay_runner)
    old_graphs, new_graphs, report = [], [], []
    replay_protocol = None
    with ZipFile(archived) as archive:
        for stat in stats:
            graph = stat["graph"]
            identity = identities[graph]
            try:
                old_rows, old_csv = read_pure_rows(archive, old_sha, graph, identity)
                new_rows, new_csv, protocol = load_rows(replay_directory / f"{graph}.csv", identity, new_sha)
                if replay_protocol is not None and protocol != replay_protocol:
                    raise ValueError("replay execution settings differ from the other graphs")
                replay_protocol = protocol
                matched = compare_work(old_rows, new_rows)
                before = summarize_graph_rows(old_rows, identity, stat, old_csv)
                after = summarize_graph_rows(new_rows, identity, stat, new_csv)
            except (OSError, ValueError, TypeError, KeyError) as error:
                raise ValueError(f"{graph}: {error}") from error
            comparisons = {framework: {name: ratio_change(
                before["frameworks"][framework]["comparisons"][name]["median_ratio"],
                after["frameworks"][framework]["comparisons"][name]["median_ratio"])
                for name in COMPARISONS} for framework in FAMILIES}
            old_graphs.append(before)
            new_graphs.append(after)
            report.append({"graph": graph, "input_sha256": identity["sha256"], "archived_csv_sha256": old_csv,
                           "replayed_csv_sha256": new_csv, "matched_run_records": matched, "comparisons": comparisons})
    old_sources, new_sources = native_sources(historical_runner), native_sources(replay_runner)
    older = pure_summary(old_graphs, None)["geometric_mean_ratios"]
    newer = pure_summary(new_graphs, replay_protocol)["geometric_mean_ratios"]
    geometric_means = {framework: {name: ratio_change(older[framework][name], newer[framework][name])
                                   for name in COMPARISONS} for framework in FAMILIES}
    return {"table": "VII", "archived_zip_sha256": sha256(archived), "archived_runner_sha256": old_sha,
            "replay_protocol": replay_protocol, "matched_native_sources": sorted(
                name for name, value in old_sources.items() if new_sources.get(name) == value),
            "different_native_sources": sorted(name for name in old_sources.keys() | new_sources.keys()
                                               if old_sources.get(name) != new_sources.get(name)),
            "compared_graphs": len(report), "matched_run_records": sum(row["matched_run_records"] for row in report),
            "graphs": report, "geometric_means_over_compared_graphs": geometric_means}


def main():
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="historical results ZIP with per-graph input and runner hashes")
    parser.add_argument("historical_runner", type=Path)
    parser.add_argument("replay_directory", type=Path)
    parser.add_argument("replay_runner", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--graphs", nargs="+", choices=stats, help="explicit subset of complete replay graphs")
    args = parser.parse_args()
    selected = set(args.graphs or stats)
    inputs = [args.archive, args.historical_runner, args.replay_runner]
    for graph in selected:
        inputs.extend(args.replay_directory / f"{graph}.{suffix}" for suffix in ("csv", "csv.manifest.json"))
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("use a separate path for the comparison report")
    try:
        report = compare(args.archive, args.historical_runner, args.replay_directory, args.replay_runner,
                         [row for graph, row in stats.items() if graph in selected])
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, BadZipFile, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS Table VII: {report['compared_graphs']} graphs, {report['matched_run_records']} matching work records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
