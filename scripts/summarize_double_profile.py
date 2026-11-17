#!/usr/bin/env python3
"""Validate paired Double profiling runs and summarize sampled phase times."""

import argparse
from contextlib import nullcontext
from hashlib import sha256 as digest
import json
import math
from pathlib import Path
import random
import re
from statistics import median
import sys
from zipfile import BadZipFile, ZipFile

from compare_pure_replay import compare_work
from rebuild_archived_tables import read_csv, read_pure_rows
from summarize_pure_csv import BLOCKS, ROOT, records, sha256, verify_manifest


BASE = ("double_compact_st", "double_compact_et1", "double_compact_et2")
SAMPLED = tuple(mode + "_profile" for mode in BASE)
PHASES = ("gate", "setup", "build", "decompose", "generate", "emit", "fallback")
WORK = ("branch_calls", "et_attempt", "et_hit", "et_degree2_hit", "et_output_count")
SAMPLE_INTERVAL = 64


def search_time(row):
    seconds = float(row["time_s"])
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("invalid search time")
    return seconds


def projected(milliseconds, population, sample_count):
    if not population:
        return 0.0
    return milliseconds * population / sample_count if sample_count else None


def check_pair(control, sampled):
    if any(control[key] != sampled[key] for key in WORK):
        raise ValueError("profiling changed branch or solver counters")
    if control["et_profile_interval"] or int(sampled["et_profile_interval"]) != SAMPLE_INTERVAL:
        raise ValueError("unexpected profile sampling configuration")

    gates, gate_samples, passes, calls, samples, fallbacks = (
        int(sampled["et_" + key]) for key in
        ("gate_calls", "gate_samples", "gate_passes", "terminal_calls", "terminal_samples", "fallbacks")
    )
    branches, attempts, hits = (int(sampled[key]) for key in WORK[:3])
    terminal_enabled = sampled["mode"] != SAMPLED[0]
    if (not 0 <= gate_samples <= gates <= branches or not 0 <= passes <= gates
            or passes != attempts or not 0 <= samples <= calls or not 0 <= hits <= calls
            or fallbacks != calls - hits or calls != (passes if terminal_enabled else 0)):
        raise ValueError("invalid profiler call or sample counts")

    measured = {phase: float(sampled[f"et_{phase}_ms"]) for phase in PHASES}
    profiled_time = search_time(sampled)
    # Emit and fallback are contained in the generate and setup/build phases.
    tolerance_ms = 0.00001
    if (any(not math.isfinite(value) or value < 0 for value in measured.values())
            or sum(measured[phase] for phase in PHASES[:5]) > 1000 * profiled_time + tolerance_ms
            or measured["emit"] > measured["generate"] + tolerance_ms
            or measured["fallback"] > measured["setup"] + measured["build"] + tolerance_ms
            or (not gate_samples and measured["gate"])
            or (not samples and any(measured[phase] for phase in PHASES[1:]))):
        raise ValueError("invalid sampled phase times")

    estimates = {phase: projected(measured[phase], calls, samples) for phase in PHASES[1:]}
    estimates["gate"] = projected(measured["gate"], gates, gate_samples)
    terminal_parts = {
        "successful_setup_and_complement": max(0.0, measured["setup"] + measured["build"] - measured["fallback"]),
        "failed_setup_and_complement": measured["fallback"],
        "component_decomposition": measured["decompose"],
        "enumeration_without_callback": max(0.0, measured["generate"] - measured["emit"]),
        "terminal_output_callback": measured["emit"],
    }
    exclusive = {"eligibility": estimates["gate"], **{
        phase: projected(value, calls, samples) for phase, value in terminal_parts.items()
    }}
    control_time = search_time(control)
    return {"control_search_ms": 1000 * control_time, "profiled_search_ms": 1000 * profiled_time,
            "profile_to_control_time_ratio": profiled_time / control_time,
            "eligibility_calls": gates, "eligibility_samples": gate_samples,
            "terminal_calls": calls, "terminal_samples": samples, "terminal_fallbacks": fallbacks,
            "measured_ms": measured, "estimated_ms": estimates, "exclusive_estimated_ms": exclusive}


def observed_range(values):
    observed = [value for value in values if value is not None]
    if not observed:
        return {"available_blocks": 0, "median": None, "range": None}
    return {"available_blocks": len(observed), "median": median(observed),
            "range": [min(observed), max(observed)]}


def compare_terminals(et1, et2):
    if not et1["blocks"] or len(et1["blocks"]) != len(et2["blocks"]):
        raise ValueError("ET1 and ET2 profile block counts differ or are empty")
    paired = []
    for first, second in zip(et1["blocks"], et2["blocks"]):
        if first["block"] != second["block"] or first["profile_seed"] != second["profile_seed"]:
            raise ValueError("ET1 and ET2 profile blocks or seeds differ")
        earlier, later = first["exclusive_estimated_ms"], second["exclusive_estimated_ms"]
        if earlier.keys() != later.keys():
            raise ValueError("ET1 and ET2 phase definitions differ")
        changes = {phase: later[phase] - value if value is not None and later[phase] is not None else None
                   for phase, value in earlier.items()}
        ordinary_change = second["control_search_ms"] - first["control_search_ms"]
        profiled_change = second["profiled_search_ms"] - first["profiled_search_ms"]
        phase_total_change = None
        profiled_change_outside_estimates = None
        if all(change is not None for change in changes.values()):
            phase_total_change = sum(changes.values())
            profiled_change_outside_estimates = profiled_change - phase_total_change
        paired.append({"block": first["block"], "profile_seed": first["profile_seed"],
                       "ordinary_search_change_ms": ordinary_change,
                       "ordinary_search_speed_ratio": first["control_search_ms"] / second["control_search_ms"],
                       "profiled_search_change_ms": profiled_change,
                       "profiled_search_speed_ratio": first["profiled_search_ms"] / second["profiled_search_ms"],
                       "profiled_minus_ordinary_change_ms": profiled_change - ordinary_change,
                       "estimated_phase_total_change_ms": phase_total_change,
                       "profiled_change_minus_estimated_phases_ms": profiled_change_outside_estimates,
                       "estimated_phase_changes_ms": changes})
    metrics = ("ordinary_search_change_ms", "ordinary_search_speed_ratio", "profiled_search_change_ms",
               "profiled_search_speed_ratio", "profiled_minus_ordinary_change_ms",
               "estimated_phase_total_change_ms", "profiled_change_minus_estimated_phases_ms")
    return {"blocks": paired,
            **{metric: observed_range(block[metric] for block in paired) for metric in metrics},
            "estimated_phase_changes_ms": {
                phase: observed_range(block["estimated_phase_changes_ms"][phase] for block in paired)
                for phase in paired[0]["estimated_phase_changes_ms"]}}


def compare_original_work(original, measurements, controls):
    original = [row for row in original if row["mode"] in controls]
    ordinary = [row for row in measurements if row["mode"] in controls]
    profiled = [{**row, "mode": row["mode"].removesuffix("_profile")}
                for row in measurements if row["mode"] not in controls]
    matches = {"ordinary": compare_work(original, ordinary), "profiled": compare_work(original, profiled)}
    times = {(int(row["block"]), row["mode"]): 1000 * search_time(row) for row in original}
    changes = [times[block, controls[2]] - times[block, controls[1]] for block in BLOCKS]
    return {"matched_search_work": matches, "original_et2_minus_et1_ms": observed_range(changes)}


def summarize_graph(path, stat, identity, runner_sha, framework, controls, pair_check, original=None):
    profiled_modes = tuple(mode + "_profile" for mode in controls)
    modes = (*controls, *profiled_modes)
    raw = path.read_bytes()
    csv_sha, protocol = verify_manifest(path, identity, runner_sha, modes, csv_sha=digest(raw).hexdigest())
    if protocol.get("matrix") != framework + "-profile":
        raise ValueError(f"{path}: expected the {framework}-profile matrix")
    seeds = protocol.get("profile_seeds")
    if seeds is not None and (not isinstance(seeds, list) or len(seeds) != len(BLOCKS)
                            or any(not isinstance(seed, str) or not re.fullmatch(r"[0-9]{1,20}", seed)
                                   or int(seed) >= 2**64 for seed in seeds)
                            or len(set(seeds)) != len(BLOCKS)):
        raise ValueError(f"{path}: expected one distinct 64-bit profiling seed per block")
    rows = read_csv(raw)
    by_block = {(int(row["block"]), row["mode"]): row for row in rows}
    expected = {(block, mode) for block in BLOCKS for mode in modes}
    if len(rows) != len(expected) or set(by_block) != expected:
        raise ValueError(f"{path}: incomplete or duplicated block/mode entries")
    orders = {block: [row["mode"] for row in rows if int(row["block"]) == block] for block in BLOCKS}
    order_design = protocol.get("order_design")
    if order_design == "paired-reversal-v1":
        rng = random.Random(protocol["seed"])
        for first in BLOCKS[::2]:
            shuffled = list(modes)
            rng.shuffle(shuffled)
            if orders[first] != shuffled:
                raise ValueError(f"{path}: block {first} differs from its seeded execution order")
        for first, second in zip(BLOCKS[::2], BLOCKS[1::2]):
            if orders[second] != orders[first][::-1]:
                raise ValueError(f"{path}: blocks {first} and {second} do not reverse execution order")
    elif order_design is not None:
        raise ValueError(f"{path}: unexpected profiling order design")

    count = int(stat["reference_bicliques"])
    fingerprints = {row["fingerprint"] for row in rows}
    if (len(fingerprints) != 1 or not re.fullmatch(r"\d+\|\d+", next(iter(fingerprints)))
            or {int(row["count"]) for row in rows} != {count}):
        raise ValueError(f"{path}: incompatible fingerprints or reference counts")
    if any(row["kind"] != framework or row["tg"].lower() not in {"0", "false"}
           or row["graph"] != identity["file_name"] for row in rows):
        raise ValueError(f"{path}: invalid graph, framework, or guidance metadata")

    result = {}
    for control, profiled in zip(controls, profiled_modes):
        blocks = []
        for block in BLOCKS:
            control_row, sampled_row = by_block[block, control], by_block[block, profiled]
            seed = seeds[block - 1] if seeds is not None else ""
            if control_row.get("profile_seed", "") or sampled_row.get("profile_seed", "") != seed:
                raise ValueError(f"{path} block {block} {profiled}: profiling seed differs from the manifest")
            try:
                pair = pair_check(control_row, sampled_row)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"{path} block {block} {control}: {error}") from error
            blocks.append({"block": block, "profile_seed": seed or None, **pair})
        result[control] = {"blocks": blocks, "median_profile_to_control_time_ratio": median(
            pair["profile_to_control_time_ratio"] for pair in blocks)}
    terminal_comparison = compare_terminals(result[controls[1]], result[controls[2]])
    summary = {"graph": stat["graph"], "label": stat["paper_label"], "count": count,
               "input_sha256": identity["sha256"], "csv_sha256": csv_sha, "profiles": result,
               "et2_minus_et1": terminal_comparison, "mode_order_by_block": orders}
    if original is not None:
        archive, historical_runner_sha = original
        try:
            original_rows, original_csv_sha = read_pure_rows(archive, historical_runner_sha, stat["graph"], identity)
            comparison = compare_original_work(original_rows, rows, controls)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path}: original measurement comparison: {error}") from error
        summary["original_campaign"] = {"csv_sha256": original_csv_sha, **comparison}
    return summary, protocol


def profile_main(description, framework, controls, pair_check):
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    identities = {row["graph"]: row for row in records(ROOT / "data/COLLECTED_INPUT_SHA256.csv")}
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--graphs", nargs="+", choices=stats, default=("github", "dblp", "twitter"))
    parser.add_argument("--original-archive", type=Path, help="Original per-run Table VII evidence ZIP")
    parser.add_argument("--original-runner", type=Path, help="Original Bitmap Guard runner ZIP")
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    if (args.original_archive is None) != (args.original_runner is None):
        parser.error("--original-archive and --original-runner must be supplied together")
    sources = [args.runner, args.original_archive, args.original_runner]
    for graph in args.graphs:
        measurements = args.run_directory / f"{graph}.csv"
        sources.extend((measurements, measurements.with_suffix(".csv.manifest.json")))
    if args.json.resolve() in {path.resolve() for path in sources if path is not None}:
        parser.error("--json needs a separate output path")
    try:
        runner_sha = sha256(args.runner)
        historical_runner_sha = sha256(args.original_runner) if args.original_runner else None
        graphs = []
        protocol = None
        source = ZipFile(args.original_archive) if args.original_archive else nullcontext()
        with source as archive:
            original = (archive, historical_runner_sha) if archive is not None else None
            for graph in dict.fromkeys(args.graphs):
                result, current = summarize_graph(args.run_directory / f"{graph}.csv", stats[graph],
                                                  identities[graph], runner_sha, framework, controls, pair_check, original)
                if protocol is not None and current != protocol:
                    raise ValueError(f"{graph}: execution settings differ from the other graphs")
                protocol = current
                graphs.append(result)
        document = {"protocol": protocol, "framework": framework,
                    "sample_interval": SAMPLE_INTERVAL, "graphs": graphs}
        if historical_runner_sha is not None:
            document["original_runner_sha256"] = historical_runner_sha
        args.json.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (BadZipFile, OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(graphs)} graphs x {len(BLOCKS)} validated profile blocks")
    if protocol.get("profile_seeds"):
        print(f"[PROFILE_SEEDS] {len(protocol['profile_seeds'])} distinct seeds verified across paired blocks")
    for graph in graphs:
        comparison = graph["et2_minus_et1"]
        gain = 100 * (comparison["ordinary_search_speed_ratio"]["median"] - 1)
        profiled_gain = 100 * (comparison["profiled_search_speed_ratio"]["median"] - 1)
        timing_shift = comparison["profiled_minus_ordinary_change_ms"]["median"]
        available = {phase: item["available_blocks"] for phase, item in comparison["estimated_phase_changes_ms"].items()}
        print(f"[PAIRED_PHASES] {graph['graph']} {framework}: ordinary ET2/ET1 gain {gain:+.2f}%, "
              f"profiled gain {profiled_gain:+.2f}%, change in ET2 minus ET1 time {timing_shift:+.3f} ms, "
              f"estimated phase pairs {available}")
        if "original_campaign" in graph:
            work = graph["original_campaign"]["matched_search_work"]
            print(f"[ORIGINAL_WORK] {graph['graph']} {framework}: {work['ordinary']} ordinary and "
                  f"{work['profiled']} profiled observations match Table VII")
        for mode, profile in graph["profiles"].items():
            blocks = profile["blocks"]
            eligibility = sum(block["eligibility_samples"] for block in blocks)
            terminals = sum(block["terminal_samples"] for block in blocks)
            print(f"[SAMPLES] {graph['graph']} {mode}: eligibility={eligibility}, terminals={terminals}")
    return 0


if __name__ == "__main__":
    sys.exit(profile_main(__doc__, "double", BASE, check_pair))
