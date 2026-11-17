#!/usr/bin/env python3
"""Validate native checkpoints and generate LaTeX rows for Tables III–VI."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import geometric_mean, median
import sys

from summarize_pure_csv import ROOT, geometric_means_without_each_graph, records, speedup


CANDIDATE = ("v63_inline_st", "v63_core_st", "v63_core_d")
CANDIDATE_ADDITIONS = {
    "cursor_after_inline": CANDIDATE[:2],
    "prefork_after_cursor": CANDIDATE[1:],
    "both_after_inline": (CANDIDATE[0], CANDIDATE[2]),
}
CR = ("flat_cr", "inline_no_cr", "inline_cr")
DOUBLE = ("vector_st", "compact_st", "vector_et_tg", "compact_et_tg")
GUIDED = ("one_et", "one_et_tg", "two_et", "two_et_tg_compact")
DIRECT_GUIDANCE = {"single": GUIDED[:2], "double": GUIDED[2:]}
CHECKPOINTS = {
    "iii": "diagnostics/V63_CHECKPOINT.json",
    "iv": "MBE_ST_CR_2X2_20261108/diagnostics/MBE_ST_CR_2X2_CHECKPOINT.json",
    "v": "MBE_NEW_P0_20261109/diagnostics/P0_DOUBLE_CHECKPOINT.json",
    "vi": "diagnostics/MBE_CORRECTED_MAIN_CHECKPOINT.json",
}
PROGRAMS = {
    "iv": "MBE_RESULT_CHILD_LAYOUT_X_CR_20261108",
    "v": "MBE_NEW_P0_20261109_V1",
    "vi": "MBE_2026_CORRECT_HEADER_BITMAP_CAP_1",
}
CONTRASTS = {
    "iii": ("inline/map", "inline_cursor/map", "inline_cursor_prefork/map"),
    "iv": ("flat_cr/flat_no_cr", "inline_no_cr/flat_no_cr",
           "inline_cr/flat_no_cr", "inline_cr/flat_cr", "inline_cr/inline_no_cr"),
    "v": ("compact_st/vector_st", "compact_et_tg/vector_et_tg",
          "vector_et_tg/vector_st", "compact_et_tg/compact_st"),
    "vi": ("single_et/st", "single_et_prefix/st", "double_et/st", "double_et_pivot/st"),
}


def positive(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"expected a positive finite measurement, got {value!r}")
    return result


def require_digest(value):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("invalid binary SHA-256")
    return value


def check_fingerprint(group, signature, expected_count, fingerprints):
    count, first, second = signature
    if type(count) is not int or count != expected_count:
        raise ValueError(f"expected {expected_count} bicliques, got {count!r}")
    if any(type(value) is not int or not 0 <= value < 2**64 for value in (first, second)):
        raise ValueError(f"invalid fingerprint in {group}")
    if tuple(signature) != fingerprints.setdefault(group, tuple(signature)):
        raise ValueError(f"fingerprint disagreement in {group}")


def interpolate(first, last, weight):
    if not 0 <= weight <= 1:
        raise ValueError("variant outside its two reference runs")
    return first + (last - first) * weight


def paired_summary(ratios):
    return {"block_ratios": ratios, "median_ratio": median(ratios)}


def contrast_over_graphs(contrasts):
    medians = [contrast["median_ratio"] for contrast in contrasts]
    paired = [ratio for contrast in contrasts for ratio in contrast["block_ratios"]]
    return {"geometric_mean_ratio": geometric_mean(medians),
            "positive_median_graphs": sum(ratio > 1 for ratio in medians),
            "positive_blocks": sum(ratio > 1 for ratio in paired),
            "negative_blocks": sum(ratio < 1 for ratio in paired),
            "equal_blocks": paired.count(1)}


def candidate_blocks(entry, modes, runs, count):
    raw = entry["blocks"]
    if set(raw) != {str(index) for index in range(runs)}:
        raise ValueError(f"expected exactly {runs} Candidate Tree blocks")
    fingerprints = {}
    paired = []
    additions = {name: [] for name in CANDIDATE_ADDITIONS}
    expected = (set(modes) - {"st_only"}) | {"st_begin", "st_end"}
    for index in range(runs):
        block = raw[str(index)]
        if set(block) != expected:
            raise ValueError("missing or unexpected Candidate Tree mode")
        for job in block.values():
            check_fingerprint("single", job["signature"], count, fingerprints)
        start, end = (positive(block[key]["clock"]) for key in ("st_begin", "st_end"))
        elapsed = positive(end - start)
        begin_ms, end_ms = (positive(block[key]["ms"]) for key in ("st_begin", "st_end"))
        measured = {mode: positive(block[mode]["ms"]) for mode in CANDIDATE}
        paired.append([
            interpolate(begin_ms, end_ms, (positive(block[mode]["clock"]) - start) / elapsed) / measured[mode]
            for mode in CANDIDATE
        ])
        for name, (control, variant) in CANDIDATE_ADDITIONS.items():
            additions[name].append(measured[control] / measured[variant])
    contrasts = {name: paired_summary(values) for name, values in additions.items()}
    return paired, {"incremental_contrasts": contrasts}, fingerprints


def native_jobs(block, anchors, variants, table):
    if block["completed"] is not True or not block["validation"].startswith("PASS"):
        raise ValueError("block did not complete with output validation")
    jobs = block["jobs"]
    modes = tuple(row["mode"] for row in jobs)
    size = len(anchors)
    first = ("flat_no_cr_begin",) if table == "iv" else anchors
    last = ("flat_no_cr_end",) if table == "iv" else anchors[::-1]
    if modes[:size] != first or modes[-size:] != last or Counter(modes[size:-size]) != Counter(variants):
        raise ValueError("block run order or mode coverage differs from the experiment")
    if any(row["status"] != "OK" for row in jobs):
        raise ValueError("non-successful native run in a completed block")
    for row in jobs:
        positive(row["ms"])
    return jobs


def anchored_ratios(jobs, anchors, variants, time_key):
    positions = {mode: i for i, mode in enumerate(row["mode"] for row in jobs)}
    times = [positive(row[time_key]) for row in jobs]

    def at(anchor, position):
        start = anchors.index(anchor)
        end = len(jobs) - start - 1
        return interpolate(times[start], times[end], (position - start) / (end - start))

    if anchors == ("one_st", "two_st"):
        return [at(anchors[index // 2], positions[mode]) / times[positions[mode]]
                for index, mode in enumerate(variants)]
    midpoint = (len(jobs) - 1) / 2
    vector, compact = anchors
    return [at(vector, midpoint) / at(compact, midpoint),
            times[positions[variants[0]]] / times[positions[variants[1]]],
            at(vector, positions[variants[0]]) / times[positions[variants[0]]],
            at(compact, positions[variants[1]]) / times[positions[variants[1]]]]


def other_blocks(raw, table, runs, count):
    if len(raw) != runs:
        raise ValueError(f"expected exactly {runs} completed blocks")
    anchors, variants = {
        "iv": (("flat_no_cr",), CR),
        "v": (DOUBLE[:2], DOUBLE[2:]),
        "vi": (("one_st", "two_st"), GUIDED),
    }[table]
    fingerprints = {}
    paired = []
    direct_modes = DIRECT_GUIDANCE if table == "vi" else {}
    direct = {framework: [] for framework in direct_modes}
    st_midpoints = {framework: [] for framework in direct_modes}
    cr_interaction = []
    wall = []
    rss = {mode: [] for mode in anchors}
    for block in raw:
        jobs = native_jobs(block, anchors, variants, table)
        timings = {job["mode"]: job["ms"] for job in jobs}
        for job in jobs:
            mode = job["mode"]
            if table == "v":
                group = "double"
                first, second = job["fp"]
                if mode in rss:
                    rss[mode].append(positive(job["rss_kb"]) / 1024)
            else:
                if table == "iv":
                    group = "cr" if mode in ("flat_cr", "inline_cr") else "no_cr"
                else:
                    group = {"one": "single", "two": "double"}[mode.split("_")[0]]
                first, second = job["xor"], job["sum"]
            check_fingerprint(group, (job["count"], first, second), count, fingerprints)

        if table == "iv":
            reference = (timings["flat_no_cr_begin"] + timings["flat_no_cr_end"]) / 2
            ratios = [reference / timings[mode] for mode in CR]
            inline_cr_gain = timings["inline_no_cr"] / timings["inline_cr"]
            paired.append([*ratios, timings["flat_cr"] / timings["inline_cr"], inline_cr_gain])
            cr_interaction.append(inline_cr_gain / ratios[0])
        else:
            paired.append(anchored_ratios(jobs, anchors, variants, "ms"))
        for framework, (control, variant) in direct_modes.items():
            direct[framework].append(timings[control] / timings[variant])
        if table == "vi":
            for position, framework in enumerate(direct_modes):
                begin = positive(jobs[position]["ms"])
                end = positive(jobs[-position - 1]["ms"])
                st_midpoints[framework].append((begin + end) / 2)
        if table == "v":
            wall.append(anchored_ratios(jobs, anchors, variants, "wall_s"))
            for vector, compact in ((DOUBLE[0], DOUBLE[1]), (DOUBLE[2], DOUBLE[3])):
                branches = {job["branches"] for job in jobs if job["mode"] in (vector, compact)}
                if len(branches) != 1 or type(next(iter(branches))) is not int or min(branches) <= 0:
                    raise ValueError(f"branch work changed between {vector} and {compact}")

    if table == "iv":
        return paired, {"cr_layout_interaction": paired_summary(cr_interaction)}, fingerprints
    if table == "v":
        return paired, {"median_peak_rss_mib": {mode: median(values) for mode, values in rss.items()},
                        "block_wall_ratios": wall,
                        "median_wall_ratios": [median(values) for values in zip(*wall)]}, fingerprints
    return paired, {
        "median_st_ms": {framework: median(values) for framework, values in st_midpoints.items()},
        "direct_guidance": {framework: paired_summary(values) for framework, values in direct.items()},
    }, fingerprints


def guidance_sensitivity(graphs):
    minimum_st_ms = 1000
    longer = [graph for graph in graphs if min(graph["median_st_ms"].values()) >= minimum_st_ms]
    result = {}
    for framework in DIRECT_GUIDANCE:
        medians = {graph["graph"]: graph["direct_guidance"][framework]["median_ratio"]
                   for graph in graphs}
        paired = [ratio for graph in graphs for ratio in graph["direct_guidance"][framework]["block_ratios"]]
        result[framework] = {
            "faster_blocks": sum(ratio > 1 for ratio in paired),
            "slower_blocks": sum(ratio < 1 for ratio in paired),
            "equal_blocks": paired.count(1),
            "geometric_mean_ratio_filtered": geometric_mean(medians[graph["graph"]] for graph in longer)
            if longer else None,
            "geometric_mean_ratio_without_graph": geometric_means_without_each_graph(medians),
        }
    return {"minimum_st_ms_in_both_frameworks": minimum_st_ms,
            "filtered_graphs": [graph["graph"] for graph in longer], "frameworks": result}


def verified_inputs(document, table, runs):
    if table == "iii":
        expected = {"st_only", *CANDIDATE}
        modes = document["modes"]
        if not expected.issubset(modes) or len(set(modes)) != len(modes):
            raise ValueError("Candidate Tree modes are incomplete or duplicated")
        return None, {"combined": require_digest(document["release_sha256"])}

    meta = document["meta"]
    if meta["program"] != PROGRAMS[table] or meta["runs"] != runs:
        raise ValueError("checkpoint program or repeat count does not match")
    if table in ("v", "vi") and meta["expected_count_check"] is not True:
        raise ValueError("checkpoint was measured with reference count checks disabled")
    if table == "v" and meta["kind"] != "double":
        raise ValueError("expected the Double representation checkpoint")
    if table == "vi" and tuple(meta["modes"]) != GUIDED:
        raise ValueError("checkpoint differs from the six-mode experiment")
    binary_key = "bins" if table == "vi" else "binaries"
    binary_modes = set(DOUBLE) if table == "v" else (
        {"flat_no_cr", *CR} if table == "iv" else {"one_st", "two_st", *GUIDED})
    if set(meta[binary_key]) != binary_modes:
        raise ValueError("missing or unexpected native binary identity")
    binaries = {mode: require_digest(value) for mode, value in meta[binary_key].items()}
    input_key = "input" if table == "vi" else "inputs"
    return meta[input_key], binaries


def summarize(suite, table, stats, runs, *, include_signatures=False):
    path = suite / CHECKPOINTS[table]
    raw = path.read_bytes()
    document = json.loads(raw)
    checkpoints = document["datasets" if table == "iii" else "blocks"]
    inputs, binaries = verified_inputs(document, table, runs)
    source = {row["graph"]: row for row in records(ROOT / "data/COLLECTED_INPUT_SHA256.csv")}
    columns = CONTRASTS[table]
    graphs = []
    for stat in stats:
        graph = stat["graph"]
        identity = source[graph]
        count = int(stat["reference_bicliques"])
        try:
            if table == "iii":
                entry = checkpoints[graph]
                expected = identity["candidate_edge_list_sha256"]
                if entry["graph_sha256"] != expected:
                    raise ValueError("normalized Candidate Tree input does not match")
                paired, extra, fingerprints = candidate_blocks(entry, document["modes"], runs, count)
            else:
                declared = inputs[graph] if table == "iv" else inputs[graph]["sha256"]
                if declared != identity["sha256"]:
                    raise ValueError("recorded input SHA-256 does not match the canonical graph")
                paired, extra, fingerprints = other_blocks(checkpoints[graph], table, runs, count)
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError(f"{graph}: {error}") from error
        if include_signatures:
            extra["output_signatures"] = {
                group: dict(zip(("count", "xor", "sum"), signature)) for group, signature in fingerprints.items()
            }
        graphs.append({
            "graph": graph, "label": stat["paper_label"], "count": count,
            "input_sha256": identity["sha256"], "block_ratios": paired,
            "median_ratios": [median(values) for values in zip(*paired)], **extra,
        })

    summary = {
        "table": table.upper(), "runs": runs, "columns": columns,
        "checkpoint_sha256": hashlib.sha256(raw).hexdigest(), "binaries": binaries,
        "graphs": graphs,
        "geometric_mean_ratios": [geometric_mean(g["median_ratios"][i] for g in graphs)
                                  for i in range(len(columns))],
    }
    if table == "iii":
        summary["incremental_contrasts"] = {
            name: contrast_over_graphs([graph["incremental_contrasts"][name] for graph in graphs])
            for name in CANDIDATE_ADDITIONS
        }
    if table == "iv":
        summary["cr_layout_interaction"] = contrast_over_graphs([graph["cr_layout_interaction"] for graph in graphs])
    if table == "v":
        summary["geometric_mean_wall_ratios"] = [
            geometric_mean(graph["median_wall_ratios"][i] for graph in graphs)
            for i in range(len(columns))
        ]
    if table == "vi":
        summary["direct_guidance_geometric_mean_ratios"] = {
            framework: geometric_mean(g["direct_guidance"][framework]["median_ratio"] for g in graphs)
            for framework in DIRECT_GUIDANCE
        }
        summary["direct_guidance_sensitivity"] = guidance_sensitivity(graphs)
    return summary


def latex_rows(summary, table):
    groups = {"iii": ((0, 1, 2),), "iv": ((0, 1, 2),), "v": (), "vi": ()}

    def cells(values):
        best = {max(group, key=values.__getitem__) for group in groups[table]}
        return [rf"\textbf{{{speedup(value)}}}" if index in best else speedup(value)
                for index, value in enumerate(values)]

    output = []
    for graph in summary["graphs"]:
        row = [graph["label"], *cells(graph["median_ratios"])]
        if table == "v":
            values = list(graph["median_peak_rss_mib"].values())
            best = min(range(len(values)), key=values.__getitem__)
            row += [rf"\textbf{{{value:.1f}}}" if i == best else f"{value:.1f}"
                    for i, value in enumerate(values)]
        output.append(" & ".join(row) + r" \\")
    tail = [r"\textbf{GM}", *cells(summary["geometric_mean_ratios"])]
    if table == "v":
        tail += ["--", "--"]
    output.append(" & ".join(tail) + r" \\")
    return "\n".join(output) + "\n"


def main():
    stats = {row["graph"]: row for row in records(ROOT / "data/GRAPH_STATISTICS.csv")}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("table", choices=CHECKPOINTS)
    parser.add_argument("out", type=Path)
    parser.add_argument("--graphs", nargs="+", choices=stats, help="Check an explicit subset")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("runs must be positive")
    selected = set(args.graphs or stats)
    try:
        summary = summarize(args.suite, args.table, [stat for graph, stat in stats.items() if graph in selected], args.runs)
        args.out.mkdir(parents=True, exist_ok=True)
        base = args.out / f"table_{args.table}"
        base.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        base.with_suffix(".tex").write_text(latex_rows(summary, args.table), encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL Table {args.table.upper()}: {error}", file=sys.stderr)
        return 1
    print(f"PASS Table {args.table.upper()}: {len(selected)}/{len(stats)} graphs x {args.runs} validated blocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
