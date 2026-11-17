#!/usr/bin/env python3
"""Check Table II tuple output and checksum-only reporting on multiword completions."""

import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "runners/MBE_FAIR_MBET_2024.zip"
MODES = ("mbet", "mbetm", "st_nocr", "st_cr")
CHECKSUM_FIELDS = ("count", "checksum_xor", "checksum_sum")
MASK = (1 << 64) - 1


def mix(value):
    value = (value + 0x9e3779b97f4a7c15) & MASK
    value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & MASK
    value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & MASK
    return value ^ (value >> 31)


def side_checksum(vertices):
    added = 0x243f6a8885a308d3
    rotated = 0x13198a2e03707344
    for vertex in vertices:
        contribution = mix(vertex + 0x100000001b3)
        shift = vertex & 31
        added += contribution
        rotated ^= ((contribution << shift) | (contribution >> ((-shift) & 63))) & MASK
    return mix((added & MASK) ^ mix(rotated + len(vertices)))


def signature(bicliques):
    xor = total = 0
    for left, right in bicliques:
        value = mix(mix(side_checksum(left) + 0x6a09e667f3bcc909) ^
                    mix(side_checksum(right) + 0xbb67ae8584caa73b))
        xor ^= value
        total += value
    return len(bicliques), xor, total & MASK


def fixture(path, transpose, *, force_header=False):
    edges = {(u, v) for u in range(6) for v in range(7) if u != v and (u, v) != (0, 1)}
    if transpose:
        edges = {(v, u) for u, v in edges}
    nl, nr = (7, 6) if transpose else (6, 7)
    # Every class expands to 13 vertices with the same neighbors. Maximality
    # requires all twins of a selected vertex, so closure on the quotient is exact.
    def labels(group):
        start = 13 * group + int(transpose)
        return tuple(range(start, start + 13))

    expanded = [(u, v) for a, b in sorted(edges) for u in labels(a) for v in labels(b)]
    header = ""
    if force_header or not transpose:
        offset = int(transpose)
        header = f"{13 * nl + offset} {13 * nr + offset} {len(expanded)}\n"
    path.write_text(header + "".join(f"{u} {v}\n" for u, v in expanded), encoding="ascii")
    result = set()
    for mask in range(1, 1 << nl):
        subset = [a for a in range(nl) if mask & (1 << a)]
        right = [b for b in range(nr) if all((a, b) in edges for a in subset)]
        if right:
            left = [a for a in range(nl) if all((a, b) in edges for b in right)]
            result.add((tuple(u for a in left for u in labels(a)), tuple(v for b in right for v in labels(b))))
    if max(len(left) if not transpose else len(right) for left, right in result) <= 64:
        raise ValueError("fixture does not cover a multiword completion in the smaller search side")
    return result


def run(mode, graph, dump=None):
    command = [sys.executable, str(RUNNER), "run", mode, str(graph), "--timeout", "30"]
    if dump is not None:
        command.extend(("--dump", str(dump)))
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if proc.returncode:
        raise RuntimeError(f"{graph.stem}/{mode} failed\n{proc.stdout}\n{proc.stderr}")
    matches = re.findall(r"^\[FAIR_RUN\] (.+)$", proc.stdout, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f"{graph.stem}/{mode}: expected one runner summary")
    return tuple(json.loads(matches[0])[key] for key in CHECKSUM_FIELDS)


def tuples(path):
    rows = []
    for line in path.read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"\[([0-9,]+)\]\s*\|?\s*\[([0-9,]+)\]", line)
        if match is None:
            raise ValueError(f"malformed emitted tuple {line!r}")
        rows.append(tuple(tuple(sorted(map(int, side.split(",")))) for side in match.groups()))
    return rows


def main():
    with TemporaryDirectory(prefix="mbe-fair-reporting-") as directory:
        root = Path(directory)
        dump = root / "dump.txt"
        for name, transpose in (("header3", False), ("swapped-edge2", True)):
            graph = root / f"{name}.txt"
            expected = fixture(graph, transpose)
            target = signature(expected)
            for mode in MODES:
                dump.unlink(missing_ok=True)
                with_tuples = run(mode, graph, dump)
                rows = tuples(dump)
                if len(rows) != len(expected) or set(rows) != expected or with_tuples != target:
                    raise ValueError(f"{name}/{mode}: emitted tuples or their summary differ from the oracle")
                if run(mode, graph) != target:
                    raise ValueError(f"{name}/{mode}: checksum-only summary differs from the oracle")
                print(f"PASS {name}/{mode}: {len(expected)} exact tuples and checksum-only signature", flush=True)


if __name__ == "__main__":
    main()
