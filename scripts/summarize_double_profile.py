#!/usr/bin/env python3
"""Validate paired Double profiling runs and summarize sampled phase times."""

import argparse
import json
import math
from pathlib import Path
import re
from statistics import median
import sys

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
    return {"profile_to_control_time_ratio": profiled_time / search_time(control),
            "eligibility_calls": gates, "eligibility_samples": gate_samples,
            "terminal_calls": calls, "terminal_samples": samples, "terminal_fallbacks": fallbacks,
            "measured_ms": measured, "estimated_ms": estimates}


def summarize_graph(path, stat, identity, runner_sha, framework, controls, pair_check):
    profiled_modes = tuple(mode + "_profile" for mode in controls)
    modes = (*controls, *profiled_modes)
    csv_sha, protocol = verify_manifest(path, identity, runner_sha, modes)
    if protocol.get("matrix") != framework + "-profile":
        raise ValueError(f"{path}: expected the {framework}-profile matrix")
    seeds = protocol.get("profile_seeds")
    if seeds is not None and (not isinstance(seeds, list) or len(seeds) != len(BLOCKS)
                            or any(not isinstance(seed, str) or not re.fullmatch(r"[0-9]{1,20}", seed)
                                   or int(seed) >= 2**64 for seed in seeds)
                            or len(set(seeds)) != len(BLOCKS)):
        raise ValueError(f"{path}: expected one distinct 64-bit profiling seed per block")
    rows = records(path)
    by_block = {(int(row["block"]), row["mode"]): row for row in rows}
    expected = {(block, mode) for block in BLOCKS for mode in modes}
    if len(rows) != len(expected) or set(by_block) != expected:
        raise ValueError(f"{path}: incomplete or duplicated block/mode entries")

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
    return {"graph": stat["graph"], "label": stat["paper_label"], "count": count,
            "input_sha256": identity["sha256"], "csv_sha256": csv_sha, "profiles": result}, protocol


def profile_main(description, framework, controls, pair_check):
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    identities = {row["graph"]: row for row in records(ROOT / "data/COLLECTED_INPUT_SHA256.csv")}
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--graphs", nargs="+", choices=stats, default=("github", "dblp", "twitter"))
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    try:
        runner_sha = sha256(args.runner)
        graphs = []
        protocol = None
        for graph in dict.fromkeys(args.graphs):
            result, current = summarize_graph(args.run_directory / f"{graph}.csv", stats[graph],
                                              identities[graph], runner_sha, framework, controls, pair_check)
            if protocol is not None and current != protocol:
                raise ValueError(f"{graph}: execution settings differ from the other graphs")
            protocol = current
            graphs.append(result)
        document = {"protocol": protocol, "framework": framework,
                    "sample_interval": SAMPLE_INTERVAL, "graphs": graphs}
        args.json.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(graphs)} graphs x {len(BLOCKS)} validated profile blocks")
    if protocol.get("profile_seeds"):
        print(f"[PROFILE_SEEDS] {len(protocol['profile_seeds'])} distinct seeds verified across paired blocks")
    for graph in graphs:
        for mode, profile in graph["profiles"].items():
            blocks = profile["blocks"]
            eligibility = sum(block["eligibility_samples"] for block in blocks)
            terminals = sum(block["terminal_samples"] for block in blocks)
            print(f"[SAMPLES] {graph['graph']} {mode}: eligibility={eligibility}, terminals={terminals}")
    return 0


if __name__ == "__main__":
    sys.exit(profile_main(__doc__, "double", BASE, check_pair))
