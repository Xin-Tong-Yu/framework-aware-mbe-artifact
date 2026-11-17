#!/usr/bin/env python3
"""Check Table III output sets and exercise both Candidate Tree fork shortcuts."""

from collections import Counter
from pathlib import Path
import random
import re
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from setup_paper_ablations import BUNDLE, EXPECTED_SHA256, digest


SOURCE = "framework_ablations/V63_MBET_CORE_SELECT/"
MODES = ("st_only", "v63_inline_st", "v63_core_st", "v63_core_d")


def instrument(code):
    edits = {
        "        if(config_.v56_prefork) {": "        {",
        "        if(v56_empty_fork) {++stats_.v56_pre_fork_skips;}": (
            "        const bool guard_would_skip = v56_empty_fork;\n"
            "        v56_empty_fork = guard_would_skip && config_.v56_prefork;\n"
            "        if(v56_empty_fork) {++stats_.v56_pre_fork_skips;}"
        ),
        "              if (stack[si]->prev != nullptr) {": (
            "              if (si > 0 && stack[si]->prev == nullptr)\n"
            '                std::cerr << "[FORK_CHECK] cursor-skip\\n";\n'
            "              if (stack[si]->prev != nullptr) {"
        ),
        "        if (!nbr_tree_root->children.empty()) {": (
            "        if (guard_would_skip) {\n"
            "          if (!nbr_tree_root->children.empty())\n"
            '            throw std::logic_error("Pre-fork guard admitted a nonempty ordinary fork");\n'
            '          std::cerr << "[FORK_CHECK] empty\\n";\n'
            "        }\n"
            "        if (!nbr_tree_root->children.empty()) {\n"
            '          std::cerr << "[FORK_CHECK] retained\\n";'
        ),
    }
    for original, annotated in edits.items():
        if code.count(original) != 1:
            raise ValueError("Table III source has changed; inspect the fork checks")
        code = code.replace(original, annotated)
    return code


def archived_pipeline(root):
    if digest(BUNDLE) != EXPECTED_SHA256:
        raise ValueError("unexpected ablation source bundle")
    with ZipFile(BUNDLE) as archive:
        members = ("source/CMakeLists.txt", "source/common/bigraph.hpp", "source/common/timer.hpp",
                   "source/main.cpp", "source/src/MBET.hpp", "v57_run.py", "v63_run.py", "verify_oracle.py")
        for name in members:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(SOURCE + name))
    header = root / "source/src/MBET.hpp"
    header.write_text(instrument(header.read_text(encoding="utf-8")), encoding="utf-8")
    sys.path.insert(0, str(root))
    try:
        return runpy.run_path(str(root / "v63_run.py"))
    finally:
        sys.path.pop(0)


def fixtures():
    small = [(u, v) for u in range(3) for v in range(3)]
    for mask in range(1, 1 << len(small)):
        yield f"small{mask}", 3, 3, [edge for i, edge in enumerate(small) if mask & (1 << i)]
    for degree in (1, 2):
        yield f"defect{degree}", 7, 7, [(u, v) for u in range(7) for v in range(7) if (v-u) % 7 >= degree]
    rng = random.Random(756019)
    for index in range(14):
        nl, nr = (7, 8) if index % 2 == 0 else (8, 7)
        density = (0.25, 0.50, 0.76)[index % 3]
        edges = [(u, v) for u in range(nl) for v in range(nr) if rng.random() < density]
        yield f"random{index+1}", nl, nr, edges or [(0, 0)]


def check(mode, graph, builds, pipeline, expected):
    base = pipeline["base"]
    exe, _ = builds[pipeline["MODE_BUILD"][mode]]
    flags = pipeline["MODES"][mode]
    command = [str(exe), "-f", str(graph), *base.COMMON, *flags, "--emit", "stdout"]
    run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    label = f"{graph.stem}/{mode}"
    if run.returncode:
        raise RuntimeError(f"{label}: native exit {run.returncode}\n{run.stderr[-2300:]}")
    rows = base.parse_emitted(run.stdout)
    count = int(re.search(r"^Count: (\d+)$", run.stdout, re.MULTILINE)[1])
    if count != len(expected) or len(rows) != count or set(rows) != expected:
        raise ValueError(f"{label}: exact outputs differ from the closure oracle")
    checks = Counter(re.findall(r"^\[FORK_CHECK\] (\S+)$", run.stderr, re.MULTILINE))
    checks["skipped"] = int(re.search(r"^V56_PreFork_Skips: (\d+)$", run.stdout, re.MULTILINE)[1])
    return checks


def main():
    totals = {mode: Counter() for mode in MODES}
    with TemporaryDirectory(prefix="mbe-candidate-forks-") as scratch:
        root = Path(scratch)
        pipeline = archived_pipeline(root)
        builds = pipeline["build"]()
        oracle = pipeline["base"].oracle_set
        cases = 0
        for name, nl, nr, edges in fixtures():
            cases += 1
            graph = root / f"{name}.txt"
            graph.write_text(f"{nl} {nr} {len(edges)}\n" + "".join(f"{u} {v}\n" for u, v in edges), encoding="ascii")
            expected = oracle(edges)
            map_layout, inline, cursor, prefork = (check(mode, graph, builds, pipeline, expected) for mode in MODES)
            if any(control["skipped"] for control in (map_layout, inline, cursor)) or prefork["empty"]:
                raise ValueError(f"{name}: Pre-fork settings did not activate as expected")
            if prefork["skipped"] != cursor["empty"] or prefork["retained"] != cursor["retained"]:
                raise ValueError(f"{name}: Pre-fork changed which nonempty forks were processed")
            for mode, result in zip(MODES, (map_layout, inline, cursor, prefork)):
                totals[mode].update(result)
    if not totals["v63_core_st"]["cursor-skip"] or not totals["v63_core_d"]["skipped"] or not totals["v63_core_d"]["retained"]:
        raise ValueError("fixtures failed to cover the Cursor shortcut, skipped forks, and nonempty forks")
    for mode, counts in totals.items():
        print(f"PASS {mode}: {cases} exact-set checks, {counts['cursor-skip']} Cursor skips, "
              f"{counts['skipped']} Pre-fork skips, {counts['empty']} shadow-checked empty forks, "
              f"{counts['retained']} retained forks")


if __name__ == "__main__":
    main()
