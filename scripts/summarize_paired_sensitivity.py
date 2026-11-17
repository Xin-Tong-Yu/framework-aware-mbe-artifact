#!/usr/bin/env python3
"""Measure how the published estimates respond to omitting paired blocks or graphs."""

import argparse
import json
from math import isfinite
from pathlib import Path
from statistics import geometric_mean, median

from summarize_pure_csv import geometric_means_without_each_graph


TABLES = ("ii", "iii", "iv", "v", "vi", "vii")


def block_ratios(table, columns, graph):
    if table == "ii":
        paired = graph["block_ratios"]
        ratios = {f"ST+CR/{reference}": series for reference, series in paired.items()}
        # Cancelling each block's ST+CR time yields the direct materialized
        # comparison. A ratio of independently summarized medians would not.
        for reference in ("mbet", "mbetm"):
            ratios[f"ST-noCR/{reference}"] = [a / b for a, b in zip(paired[reference], paired["st_nocr"])]
        return ratios
    if table == "vii":
        return {f"{framework}:{contrast}": values["block_ratios"]
                for framework, results in graph["frameworks"].items()
                for contrast, values in results["comparisons"].items()}

    rows = graph["block_ratios"]
    if any(len(row) != len(columns) for row in rows):
        raise ValueError(f"unexpected search contrast count for Table {table.upper()}")
    ratios = dict(zip(columns, zip(*rows)))
    if table == "iii":
        ratios.update({key: value["block_ratios"] for key, value in graph["incremental_contrasts"].items()})
    if table == "iv":
        ratios["cr_layout_interaction"] = graph["cr_layout_interaction"]["block_ratios"]
    if table == "v":
        wall = graph["block_wall_ratios"]
        if any(len(row) != len(columns) for row in wall):
            raise ValueError("unexpected wall-time contrast count for Table V")
        ratios.update({f"wall:{key}": value for key, value in zip(columns, zip(*wall))})
    if table == "vi":
        ratios.update({f"policy:{key}": value["block_ratios"] for key, value in graph["direct_guidance"].items()})
    return ratios


def graph_sensitivity(ratios):
    if len(ratios) != 5 or any(not isfinite(value) or value <= 0 for value in ratios):
        raise ValueError("expected five positive finite paired ratios")
    omitted = [median(ratios[:index] + ratios[index + 1:]) for index in range(len(ratios))]
    return {"median_ratio": median(ratios), "omit_one_median_ratio_range": [min(omitted), max(omitted)],
            "omit_one_median_ratios_by_block": omitted, "faster_blocks": sum(value > 1 for value in ratios),
            "slower_blocks": sum(value < 1 for value in ratios), "equal_blocks": ratios.count(1)}


def contrast_sensitivity(by_graph):
    results = {graph: graph_sensitivity(ratios) for graph, ratios in by_graph.items()}
    medians = {graph: result["median_ratio"] for graph, result in results.items()}
    without_graph = geometric_means_without_each_graph(medians)
    graph_range = [min(without_graph.values()), max(without_graph.values())] if without_graph else None
    lower, upper = zip(*(r["omit_one_median_ratio_range"] for r in results.values()))
    # Each graph can omit a different block, so the suite extrema are attained
    # by simultaneously taking the minimum or maximum attainable median per graph.
    return {"geometric_mean_ratio": geometric_mean(medians.values()),
            "geometric_mean_ratio_without_graph": without_graph,
            "omit_one_graph_geometric_mean_ratio_range": graph_range,
            "omit_one_per_graph_geometric_mean_ratio_range": [geometric_mean(lower), geometric_mean(upper)],
            "graphs_positive_under_every_omission": sum(value > 1 for value in lower),
            "graphs_negative_under_every_omission": sum(value < 1 for value in upper),
            "faster_blocks": sum(r["faster_blocks"] for r in results.values()),
            "slower_blocks": sum(r["slower_blocks"] for r in results.values()),
            "equal_blocks": sum(r["equal_blocks"] for r in results.values()),
            "graphs": results}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(reconstructed):
    archived = read_json(reconstructed / "raw" / "summary.json")
    results = {}
    reference_graphs = None
    for table in TABLES:
        if table in ("ii", "vii"):
            summary = archived[f"table_{table}"]
        else:
            summary = read_json(reconstructed / "native" / f"table_{table}.json")
            if summary["table"] != table.upper() or summary["runs"] != 5:
                raise ValueError(f"unexpected native summary for Table {table.upper()}")
        graphs = summary["graphs"]
        identities = {g["graph"]: g["input_sha256"] for g in graphs}
        if len(graphs) != 13 or len(identities) != 13:
            raise ValueError(f"Table {table.upper()} must have 13 distinct graphs")
        if reference_graphs is None:
            reference_graphs = identities
        if identities != reference_graphs:
            raise ValueError(f"input identity differs for Table {table.upper()}")
        by_graph = {g["graph"]: block_ratios(table, summary.get("columns"), g) for g in graphs}
        keys = tuple(next(iter(by_graph.values())))
        if any(set(row) != set(keys) for row in by_graph.values()):
            raise ValueError(f"contrast coverage differs within Table {table.upper()}")
        results[table.upper()] = {key: contrast_sensitivity({name: row[key] for name, row in by_graph.items()})
                                  for key in keys}
    return {"description": "Sensitivity to deleting one paired block per graph or omitting one entire graph.",
            "input_sha256": reference_graphs, "tables": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reconstructed", type=Path, help="reconstructed directory produced by the archive verifier")
    parser.add_argument("output", type=Path, help="destination JSON file")
    args = parser.parse_args()
    report = build_report(args.reconstructed)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS paired-block and graph sensitivity for {sum(map(len, report['tables'].values()))} contrasts")


if __name__ == "__main__":
    main()
