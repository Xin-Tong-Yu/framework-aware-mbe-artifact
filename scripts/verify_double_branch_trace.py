#!/usr/bin/env python3
"""Check the branch sequence of the two Table V representations on small graphs."""

from collections import Counter
import os
from pathlib import Path
import random
import re
import runpy
import shlex
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from setup_paper_ablations import BUNDLE, EXPECTED_SHA256, ROOT, digest


SOURCE = "framework_ablations/MBE_CORRECTED_13DATA/two_source"
BUILD = "framework_ablations/MBE_NEW_P0_20261109/build.sh"

TRACE = r'''
    void traceSet(const char *name, int side, std::vector<int32_t> ids) {
        for (auto &id : ids) id = g->old_lables[side][id];
        std::sort(ids.begin(), ids.end());
        fprintf(stderr, " %s%d=", name, side);
        for (auto id : ids) fprintf(stderr, "%d,", id);
    }

    void traceBranch(int32_t depth) {
        fprintf(stderr, "[TRACE] B %d", depth);
        for (int side = 0; side < 2; ++side) {
            auto begin = S[side].begin();
            traceSet("S", side, currentResult[side]);
            traceSet("C", side, std::vector<int32_t>(begin + S[side].c, begin + S[side].r));
            traceSet("X", side, std::vector<int32_t>(begin + S[side].x, begin + S[side].c));
        }
        fputc('\n', stderr);
    }

'''


def trace_header(code):
    changes = {
        "    void branch(int32_t deep) {\n": TRACE + "    void branch(int32_t deep) {\n        traceBranch(deep);\n",
        "                if (validMatching) {\n": (
            '                if (validMatching) {\n'
            '                    fprintf(stderr, "[TRACE] M %zu\\n", pairs.size());\n'
        ),
        "        bool isPivotInX = (S[t].x <= min_pos && min_pos < S[t].c);\n": (
            "        bool isPivotInX = (S[t].x <= min_pos && min_pos < S[t].c);\n"
            '        fprintf(stderr, "[TRACE] P %d %d %d\\n", t, g->old_lables[t][pivot], isPivotInX);\n'
        ),
    }
    for original, traced in changes.items():
        if code.count(original) != 1:
            raise ValueError("Table V source has changed; inspect the trace insertion points")
        code = code.replace(original, traced)
    return code


def build_variants(root):
    if digest(BUNDLE) != EXPECTED_SHA256:
        raise ValueError("Unexpected ablation source bundle")
    source = root / "source"
    source.mkdir()
    with ZipFile(BUNDLE) as archive:
        command = archive.read(BUILD).decode("utf-8")
        flags = shlex.split(re.search(r"^COMMON=\(([^\n]+)\)", command, re.MULTILINE)[1])
        for member in archive.namelist():
            if member.startswith(SOURCE + "/") and not member.endswith("/"):
                (source / Path(member).name).write_bytes(archive.read(member))
    ips = source / "ips.hpp"
    ips.write_text(trace_header(ips.read_text(encoding="utf-8")), encoding="utf-8")
    compiler = os.environ.get("CXX", "g++")
    builds = {}
    for terminal in ("st", "et_tg"):
        terminal_flags = ["-DIPS_CLASSIC_PIVOT", "-DIPS_DISABLE_ET"] if terminal == "st" else []
        for storage in ("vector", "compact"):
            storage_flags = ["-DIPS_ST_V24_SINGLE_DEFECT"] if storage == "compact" else []
            program = root / f"{storage}_{terminal}"
            subprocess.run([compiler, *flags, *terminal_flags, *storage_flags, "-I", str(source),
                            str(source / "main.cpp"), "-o", str(program)], check=True)
            builds[storage, terminal] = program
    return builds


def fixtures():
    yield "matching", 7, 7, {(i, j) for i in range(7) for j in range(7) if i != j}, 1, 1
    yield "cycle", 7, 7, {(i, j) for i in range(7) for j in range(7) if j not in (i, (i + 1) % 7)}, 2, 3
    rng = random.Random(391709)
    for index in range(10):
        probability = (0.22, 0.53, 0.81)[index % 3]
        edges = {(i, j) for i in range(7) for j in range(9) if rng.random() < probability}
        yield f"random{index + 1}", 7, 9, edges or {(0, 0)}, 2, 1


def run_trace(program, graph, limits, output, expected, compare_result):
    left, right = map(str, limits)
    run = subprocess.run([str(program), "-f", str(graph), "-d", "two", "-l", left, "-r", right,
                          "-o", str(output)], capture_output=True, text=True, timeout=30)
    if run.returncode:
        raise RuntimeError(f"{graph.stem}/{program.name} exited {run.returncode}\n{run.stderr[-1000:]}")
    compare_result(output.read_text(encoding="utf-8"), expected, f"{graph.stem}/{program.name}")
    events = [line for line in run.stderr.splitlines() if line.startswith("[TRACE] ")]
    counts = Counter(line.split()[1] for line in events)
    branches = int(re.search(r"^Branch_Calls: (\d+)", run.stdout, re.MULTILINE)[1])
    accepted = int(re.search(r"^ET_Used / TT = (\d+)", run.stdout, re.MULTILINE)[1])
    if counts["B"] != branches or counts["M"] != accepted:
        raise ValueError(f"Incomplete trace for {graph.stem}/{program.name}")
    return events, counts


def main():
    oracle = runpy.run_path(str(ROOT / "runners/MBE_PURE_ET1_ET2.zip"))
    totals = {"st": Counter(), "et_tg": Counter()}
    with TemporaryDirectory(prefix="mbe-double-branch-oracle-") as directory:
        root = Path(directory)
        builds = build_variants(root)
        for name, nl, nr, edges, left, right in fixtures():
            graph = root / f"{name}.clean"
            graph.write_text(f"{nl} {nr} {len(edges)}\n" +
                             "".join(f"{u} {v}\n" for u, v in sorted(edges)), encoding="ascii")
            expected = oracle["oracle"](nl, nr, edges, left, right)
            for mode, total in totals.items():
                vector, counts = run_trace(builds["vector", mode], graph, (left, right), root / "vector.txt",
                                           expected, oracle["compare_result"])
                compact, _ = run_trace(builds["compact", mode], graph, (left, right), root / "compact.txt",
                                       expected, oracle["compare_result"])
                if vector != compact:
                    first = next((i for i, pair in enumerate(zip(vector, compact), 1) if pair[0] != pair[1]),
                                 min(len(vector), len(compact)) + 1)
                    raise ValueError(f"{name}/{mode}: Vector and Compact first disagree at trace event {first}")
                total.update(counts)
                print(f"PASS {name}/{mode}: {counts['B']} states, {counts['P']} pivots, "
                      f"{counts['M']} matching terminals, {len(expected)} exact bicliques", flush=True)
    if not totals["st"]["P"] or totals["st"]["M"] or not totals["et_tg"]["P"] or not totals["et_tg"]["M"]:
        raise ValueError("Fixtures did not cover the expected pivots and terminals")
    for mode, total in totals.items():
        print(f"PASS {mode}: {total['B']} identical branch states, {total['P']} identical pivots, "
              f"{total['M']} identical matching terminals")


if __name__ == "__main__":
    main()
