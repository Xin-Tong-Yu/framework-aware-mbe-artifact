#!/usr/bin/env python3
"""Check exact Single outputs on graphs that reach the prefix solver."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

SIZE = 17
MODES = ("one_st", "one_et", "one_et_tg")
BICLIQUE = re.compile(r"^\[([0-9, ]+)\]\[([0-9, ]+)\]$", re.MULTILINE)
COUNTERS = ("TG2_Prefix_Hits", "TG2_Nonmatching_Hits", "TG2_Deferred_Paths",
            "TG2_Cap_Rejections")


def neighborhoods(defect_degree):
    full = (1 << SIZE) - 1
    return [full ^ sum(1 << ((i + offset) % SIZE) for offset in range(defect_degree))
            for i in range(SIZE)]


def exact_bicliques(neighbors):
    """Enumerate left subsets and retain pairs equal to their two closures."""
    intersections = [(1 << len(neighbors)) - 1] * (1 << len(neighbors))
    expected = set()
    for left in range(1, len(intersections)):
        low = left & -left
        right = intersections[left ^ low] & neighbors[low.bit_length() - 1]
        intersections[left] = right
        if not right:
            continue
        closure = sum(1 << i for i, row in enumerate(neighbors) if row & right == right)
        if closure == left:
            expected.add((left, right))
    return expected


def vertex_mask(vertices):
    ids = [int(vertex) for vertex in vertices.split(",")]
    if len(ids) != len(set(ids)) or any(not 0 <= vertex < SIZE for vertex in ids):
        raise ValueError(f"Invalid vertices in emitted biclique: {vertices}")
    return sum(1 << vertex for vertex in ids)


def verify(launcher, graph, expected, mode, *, nonmatching=False, capped=False):
    budget = ["--et2-max-mis", "1"] if capped else []
    command = ["bash", str(launcher), mode, str(graph), "--emit", "stdout", *budget]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    label = f"{graph.stem}/{mode}" + ("/capped" if capped else "")
    if proc.returncode:
        raise RuntimeError(f"{label}: native exit {proc.returncode}\n{proc.stderr[-2000:]}")

    output = [(vertex_mask(match[1]), vertex_mask(match[2])) for match in BICLIQUE.finditer(proc.stdout)]
    actual = set(output)
    if actual != expected or len(output) != len(actual):
        raise ValueError(f"{label}: {len(expected - actual)} missing, {len(actual - expected)} extra, "
                         f"{len(output) - len(actual)} duplicate bicliques")
    counters = dict(re.findall(r"^(TG2_\w+):\s*(\d+)$", proc.stdout, re.MULTILINE))
    if not set(COUNTERS).issubset(counters):
        raise ValueError(f"{label}: missing native counters {sorted(set(COUNTERS) - counters.keys())}")
    prefix, degree_two, deferred, rejections = (int(counters[name]) for name in COUNTERS)
    if capped:
        if rejections == 0 or prefix or degree_two or deferred:
            raise ValueError(f"{label}: required budget fallback was not exercised")
    elif mode == "one_et_tg":
        if prefix == 0 or deferred == 0 or (degree_two > 0) != nonmatching:
            raise ValueError(f"{label}: observed the wrong prefix-solver behavior")
    elif prefix or degree_two or deferred:
        raise ValueError(f"{label}: prefix solving was active in the control")
    print(f"PASS {label}: {len(actual)} exact results, {prefix} prefix hits, "
          f"{degree_two} nonmatching hits, {deferred} deferred paths, {rejections} budget rejections",
          flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("launcher", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory() as tmp:
        for case, degree in (("crown17", 1), ("cycle17", 2)):
            graph = Path(tmp) / f"{case}.txt"
            neighbors = neighborhoods(degree)
            graph.write_text("".join(f"{i} {j}\n" for i, row in enumerate(neighbors)
                                     for j in range(SIZE) if row >> j & 1), encoding="ascii")
            expected = exact_bicliques(neighbors)
            for mode in MODES:
                verify(args.launcher, graph, expected, mode, nonmatching=(degree == 2))
            if degree == 2:
                verify(args.launcher, graph, expected, "one_et_tg", capped=True)


if __name__ == "__main__":
    main()
