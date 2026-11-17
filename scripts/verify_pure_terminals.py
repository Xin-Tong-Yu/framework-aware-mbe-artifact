#!/usr/bin/env python3
"""Exercise terminal and fallback paths in the distributed pure ET runner."""

from pathlib import Path
import re
import runpy
import subprocess
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "runners/MBE_PURE_ET1_ET2.zip"
CASES = (
    ("mixed", (3, 3), (2, 2), (1, 1)),
    ("paths", (), (3, 3, 3), (2, 3)),
    ("cycles", (4, 4), (), (2, 3)),
)


def graph_with_missing_components(cycles, paths):
    size = 2 + sum(cycles) + sum(paths)
    missing = set()
    start = 0
    for width in cycles:
        for i in range(width):
            missing.add((start + i, start + i))
            missing.add((start + i, start + (i + 1) % width))
        start += width
    for width in paths:
        missing.update((start + i, start + i) for i in range(width))
        missing.update((start + i, start + i + 1) for i in range(width - 1))
        start += width
    return size, {(left, right) for left in range(size) for right in range(size)} - missing


def counter(output, name):
    match = re.search(rf"^{re.escape(name)}:\s*(\d+)$", output, re.MULTILINE)
    if match is None:
        raise ValueError(f"Missing native counter {name}")
    return int(match[1])


def verify_run(runner, mode, executable, graph_paths, thresholds, expected,
               output, case, has_cycles, *, capped=False):
    label = f"{case}/{mode}" + ("/capped" if capped else "")
    kind = runner["MODES"][mode][0]
    destination = "stdout" if kind == "single" else output
    command = runner["command"](mode, executable, *graph_paths, *thresholds, destination)
    if capped:
        command[command.index("--et2-max-mis") + 1] = "1"
    run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if run.returncode:
        raise RuntimeError(f"{label}: native exit {run.returncode}\n{run.stderr[-1000:]}")

    emitted = run.stdout if kind == "single" else output.read_text(encoding="utf-8")
    runner["compare_result"](emitted, expected, label)
    if int(runner["parse_stats"](kind, run.stdout)["count"]) != len(expected):
        raise ValueError(f"{label}: reported count disagrees with the closure oracle")

    detail = ""
    if capped:
        rejections = counter(run.stdout, "ET2_Fallback_Cap")
        if rejections == 0:
            raise ValueError(f"{label}: expected a budget rejection followed by ordinary search")
        detail = f", {rejections} budget rejections"
    elif mode == "single_et2":
        hits = counter(run.stdout, "ET2_Nonmatching_Hits")
        if hits == 0:
            raise ValueError(f"{label}: expected a nonmatching terminal")
        detail = f", {hits} nonmatching terminal hits"
    elif mode == "double_compact_et2":
        hits = counter(run.stdout, "2Biplex_Degree2_Hits")
        paths = counter(run.stdout, "2Biplex_Path_Components")
        cycles = counter(run.stdout, "2Biplex_Cycle_Components")
        if hits == 0 or paths == 0 or bool(cycles) != has_cycles:
            raise ValueError(f"{label}: unexpected terminal component coverage")
        detail = f", {hits} degree-two hits, {paths} path and {cycles} cycle components"
    print(f"PASS {label}: {len(expected)} exact bicliques{detail}", flush=True)


def main():
    runner = runpy.run_path(str(ARCHIVE))
    with TemporaryDirectory(prefix="mbe-pure-oracle-") as directory:
        root = Path(directory)
        cache = root / "cache"
        binaries = {mode: runner["build"](mode, cache, ARCHIVE) for mode in runner["PURE_1V2_MATRIX"]}
        for name, cycles, paths, thresholds in CASES:
            size, edges = graph_with_missing_components(cycles, paths)
            graph = root / f"{name}.clean"
            graph.write_text(f"{size} {size} {len(edges)}\n" +
                             "".join(f"{left} {right}\n" for left, right in sorted(edges)), encoding="ascii")
            graph_paths = runner["graph_variants"](graph, cache)
            expected = runner["oracle"](size, size, edges, *thresholds)
            for mode, executable in binaries.items():
                output = root / f"{name}-{mode}.txt"
                verify_run(runner, mode, executable, graph_paths, thresholds, expected,
                           output, name, bool(cycles))
                if mode == "single_et2":
                    verify_run(runner, mode, executable, graph_paths, thresholds, expected,
                               output, name, bool(cycles), capped=True)


if __name__ == "__main__":
    main()
