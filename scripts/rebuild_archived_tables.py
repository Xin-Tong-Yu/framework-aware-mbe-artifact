#!/usr/bin/env python3
"""Rebuild Tables II and VII from the original benchmark CSV archive."""

import argparse
import csv
from hashlib import sha256 as digest
from io import StringIO
import json
import math
from pathlib import Path
import re
from statistics import geometric_mean, median
import sys
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from summarize_pure_csv import (BLOCKS, ROOT, latex_rows, pure_summary, records, sha256,
                                speedup, summarize_graph_rows)
from validate_pure_csv import MODE_KIND, validate_rows

FAIR_MODES = ("mbet", "mbetm", "st_nocr", "st_cr")
FAIR_PREFIX = "results/mbet_fair_headerfix"
PURE_PREFIX = "results/pure_et1_et2"
FAIR_COMPARISONS = FAIR_MODES[:-1]
FAIR_SETTINGS = ("runner_version", "input_format", "seed", "stack_mb", "cpu")
EVIDENCE_README = """# Original measurements for Tables II and VII

These CSVs are byte-for-byte copies of the four-mode MBET-family and six-mode
unguided ET experiments. The directory `expected/` contains their reconstructed
LaTeX rows and the paired ratios from all thirteen graphs. Check the extracted
files with `sha256sum -c SHA256SUMS`.

Run the following command from the artifact repository root with Python 3.9 or later.

```sh
python3 scripts/rebuild_archived_tables.py MBE_Archived_Table_II_VII.zip outputs/archived_tables \\
  --recorded-runner-sha256 {runner_sha}
```

The original Bitmap Guard ZIP was verified when this evidence was packaged.
The rebuild command uses its recorded hash and reads the CSVs directly. The JSON
identifies the original archive and its runner hash. The independently replayed
experiments have their own manifests.
"""


def read_csv(data):
    return list(csv.DictReader(StringIO(data.decode("utf-8-sig"), newline="")))


def fair_comparisons(timings):
    return {ref: [timings[block, ref] / timings[block, "st_cr"] for block in BLOCKS]
            for ref in FAIR_COMPARISONS}


def read_fair_graph(raw, stat, expected_sha):
    graph = stat["graph"]
    rows = read_csv(raw)
    count = int(stat["reference_bicliques"])
    expected = {(block, mode) for block in BLOCKS for mode in FAIR_MODES}
    if len(rows) != len(expected):
        raise ValueError(f"{graph}: expected {len(expected)} four-mode measurements")

    search_times = {}
    wall_times = {}
    signatures = set()
    builds = {}
    protocols = set()
    for row in rows:
        mode = row["mode"]
        key = int(row["block"]), mode
        if key not in expected or key in search_times:
            raise ValueError(f"{graph}: unknown or duplicate record {key}")
        if row["graph"] != graph or row["input_sha256"] != expected_sha:
            raise ValueError(f"{graph}: four-mode input identity differs from the canonical graph")
        for field, timings in (("search_s", search_times), ("wall_s", wall_times)):
            value = float(row[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{graph}: invalid {field} in {key}")
            timings[key] = value
        signatures.add(tuple(int(row[field]) for field in ("count", "checksum_xor", "checksum_sum")))
        build = row["exe_sha256"], row["compile_flags"]
        if not re.fullmatch(r"[0-9a-f]{64}", build[0]) or not build[1]:
            raise ValueError(f"{graph}: invalid binary identity for {mode}")
        if build != builds.setdefault(mode, build):
            raise ValueError(f"{graph}: inconsistent binary identity for {mode}")
        protocols.add(tuple(row[field] for field in FAIR_SETTINGS))

    if len(signatures) != 1 or next(iter(signatures))[0] != count:
        raise ValueError(f"{graph}: wrong reference count or inconsistent fingerprints")
    if len(protocols) != 1 or next(iter(protocols))[1] != "auto-header3-or-edge2":
        raise ValueError(f"{graph}: wrong or inconsistent four-mode execution settings")

    paired = fair_comparisons(search_times)
    paired_wall = fair_comparisons(wall_times)
    summary = {
        "graph": graph, "label": stat["paper_label"], "count": count,
        "input_sha256": expected_sha, "csv_sha256": digest(raw).hexdigest(),
        "median_search_s": {mode: median(search_times[block, mode] for block in BLOCKS) for mode in FAIR_MODES},
        "median_wall_s": {mode: median(wall_times[block, mode] for block in BLOCKS) for mode in FAIR_MODES},
        "block_ratios": paired,
        "block_wall_ratios": paired_wall,
        "median_ratios": {mode: median(values) for mode, values in paired.items()},
    }
    protocol = dict(zip(FAIR_SETTINGS, next(iter(protocols))))
    protocol["builds"] = {mode: {"exe_sha256": sha, "compile_flags": flags}
                          for mode, (sha, flags) in builds.items()}
    return summary, protocol


def read_pure_graph(archive, runner_sha, stat, identity):
    graph = stat["graph"]
    checksums = f"{PURE_PREFIX}/checksums/{graph}"
    declared_input = archive.read(f"{checksums}.sha256").decode("ascii").strip()
    declared_runner = archive.read(f"{checksums}.zipsha256").decode("ascii").strip()
    if declared_input != identity["sha256"] or declared_runner != runner_sha:
        raise ValueError(f"{graph}: declared input or Bitmap Guard runner hash does not match")
    raw = archive.read(f"{PURE_PREFIX}/{graph}_pure.csv")
    rows = read_csv(raw)
    errors = validate_rows(rows, identity["file_name"])
    if errors:
        raise ValueError(f"{graph}: {'; '.join(errors)}")
    return summarize_graph_rows(rows, identity, stat, digest(raw).hexdigest())


def fair_latex(summary):
    lines = []
    for graph in summary["graphs"]:
        times = graph["median_search_s"]
        best = min(times, key=times.get)
        cells = [graph["label"], f'{graph["count"]:,}']
        for mode, value in times.items():
            cells.append(rf"\textbf{{{value:.3f}}}" if mode == best else f"{value:.3f}")
        cells.extend(speedup(graph["median_ratios"][mode]) for mode in FAIR_COMPARISONS[:2])
        lines.append(" & ".join(cells) + r" \\")
    tail = [r"\textbf{GM speedup (\%)}", *(["--"] * 5)]
    for mode in FAIR_COMPARISONS[:2]:
        tail.append(r"\textbf{" + speedup(summary["geometric_mean_ratios"][mode]) + "}")
    lines.append(" & ".join(tail) + r" \\")
    return "\n".join(lines) + "\n"


def rebuild(archive_path, runner_sha, verified_runner_file):
    inputs = {row["graph"]: row for row in records(ROOT / "data/COLLECTED_INPUT_SHA256.csv")}
    fair = []
    pure = []
    protocol = None
    with ZipFile(archive_path) as archive:
        for stat in records(ROOT / "data/GRAPH_STATISTICS.csv"):
            graph = stat["graph"]
            identity = inputs[graph]
            raw = archive.read(f"{FAIR_PREFIX}/{graph}.csv")
            row, current = read_fair_graph(raw, stat, identity["sha256"])
            if protocol is None:
                protocol = current
            elif protocol != current:
                raise ValueError(f"{graph}: four-mode execution settings differ between graphs")
            fair.append(row)
            pure.append(read_pure_graph(archive, runner_sha, stat, identity))

    fair_gm = {mode: geometric_mean(graph["median_ratios"][mode] for graph in fair)
               for mode in FAIR_COMPARISONS}
    fair_wall_gm = {mode: geometric_mean(median(graph["block_wall_ratios"][mode]) for graph in fair)
                    for mode in FAIR_COMPARISONS}
    pure_protocol = {"declared_runner_sha256": runner_sha, "verified_runner_file": verified_runner_file}
    non_subsecond = [graph for graph in pure
                     if all(family["median_st_s"] >= 1.0 for family in graph["frameworks"].values())]
    return {
        "archive_sha256": sha256(archive_path),
        "table_ii": {"protocol": protocol, "graphs": fair, "geometric_mean_ratios": fair_gm,
                     "geometric_mean_wall_ratios": fair_wall_gm},
        "table_vii": pure_summary(pure, pure_protocol),
        "table_vii_sensitivity": {
            "min_median_st_s_in_each_framework": 1.0,
            "graphs": [graph["graph"] for graph in non_subsecond],
            "geometric_mean_ratios": pure_summary(non_subsecond, pure_protocol)["geometric_mean_ratios"],
        },
    }


def write_evidence(archive_path, destination, outputs, summary):
    """Copy only the original records and input/runner checksums."""
    entries = {f"expected/{name}": content.encode("utf-8") for name, content in outputs.items()}
    runner_sha = summary["table_vii"]["protocol"]["declared_runner_sha256"]
    entries["README.md"] = EVIDENCE_README.format(runner_sha=runner_sha).encode("utf-8")
    pure_graphs = {item["graph"]: item for item in summary["table_vii"]["graphs"]}
    with ZipFile(archive_path) as source:
        for result in summary["table_ii"]["graphs"]:
            graph = result["graph"]
            checksum_base = f"{PURE_PREFIX}/checksums/{graph}"
            for name, expected in ((f"{FAIR_PREFIX}/{graph}.csv", result["csv_sha256"]),
                                   (f"{PURE_PREFIX}/{graph}_pure.csv", pure_graphs[graph]["csv_sha256"])):
                content = source.read(name)
                if digest(content).hexdigest() != expected:
                    raise ValueError(f"{name}: original records changed before export")
                entries[name] = content
            for suffix, expected in ((".sha256", result["input_sha256"]), (".zipsha256", runner_sha)):
                name = checksum_base + suffix
                content = source.read(name)
                if content.decode("ascii").strip() != expected:
                    raise ValueError(f"{name}: original checksums changed before export")
                entries[name] = content
    entries["SHA256SUMS"] = "".join(
        f"{digest(entries[name]).hexdigest()}  {name}\n" for name in sorted(entries)
    ).encode("ascii")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, suffix=".zip.tmp", delete=False) as temporary:
        package = Path(temporary.name)
    try:
        with ZipFile(package, "w") as output:
            for name in sorted(entries):
                output.writestr(ZipInfo(name), entries[name], compress_type=ZIP_DEFLATED)
        package.replace(destination)
    finally:
        package.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Original code-and-results ZIP or evidence ZIP")
    parser.add_argument("bitmap_guard_zip", type=Path, nargs="?", help="Original Bitmap Guard runner ZIP")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--recorded-runner-sha256", help="Use the recorded runner hash when the runner ZIP is unavailable")
    parser.add_argument("--evidence-zip", type=Path, help="Export the original measurement CSVs and their reconstructed tables")
    args = parser.parse_args()
    if bool(args.bitmap_guard_zip) == bool(args.recorded_runner_sha256):
        parser.error("provide either the original Bitmap Guard ZIP or its recorded SHA-256")
    if args.recorded_runner_sha256 and not re.fullmatch(r"[0-9a-f]{64}", args.recorded_runner_sha256):
        parser.error("--recorded-runner-sha256 must be a lowercase SHA-256 digest")
    if args.evidence_zip:
        if args.bitmap_guard_zip is None:
            parser.error("--evidence-zip requires the original Bitmap Guard runner ZIP")
        if args.evidence_zip.resolve() in (args.archive.resolve(), args.bitmap_guard_zip.resolve()):
            parser.error("--evidence-zip must use a new output path")
    try:
        runner_sha = sha256(args.bitmap_guard_zip) if args.bitmap_guard_zip else args.recorded_runner_sha256
        summary = rebuild(args.archive, runner_sha, verified_runner_file=bool(args.bitmap_guard_zip))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        outputs = {
            "summary.json": json.dumps(summary, indent=2) + "\n",
            "table_ii.tex": fair_latex(summary["table_ii"]),
            "table_vii.tex": latex_rows(summary["table_vii"]),
        }
        for name, output in outputs.items():
            with (args.output_dir / name).open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(output)
        if args.evidence_zip:
            write_evidence(args.archive, args.evidence_zip, outputs, summary)
    except (BadZipFile, OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    for number, modes in (("ii", FAIR_MODES), ("vii", MODE_KIND)):
        graphs = len(summary[f"table_{number}"]["graphs"])
        print(f"PASS Table {number.upper()}: {graphs} graphs, {graphs * len(BLOCKS) * len(modes)} measurements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
