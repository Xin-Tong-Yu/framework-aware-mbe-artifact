#!/usr/bin/env python3
"""Check the four Table IV builds against exact sets and independent checksums."""

from pathlib import Path
import re
import runpy
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from setup_paper_ablations import BUNDLE, EXPECTED_SHA256, digest
from verify_fair_reporting import fixture, signature, tuples


SOURCE = "MBE_FAST_FOUR_MODES/one/source/"
STUDY = "MBE_ST_CR_2X2_20261108/bench.py"
PREPARE = "MBE_CORRECTED_13DATA/prepare_corrected.py"
FILES = ("CMakeLists.txt", "common/bigraph.hpp", "common/timer.hpp", "main.cpp", "src/MBET.hpp")
SUMMARY = ("Count", "Checksum_XOR", "Checksum_SUM")


def extract(root):
    if digest(BUNDLE) != EXPECTED_SHA256:
        raise ValueError("unexpected ablation source bundle")
    with ZipFile(BUNDLE) as archive:
        for name in (STUDY, PREPARE, *(SOURCE + path for path in FILES)):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read("framework_ablations/" + name))


def native_signature(exe, graph, common, dump=None):
    command = [str(exe), "-f", str(graph), *common]
    if dump is not None:
        command.extend(("--emit", str(dump)))
    run = subprocess.run(command, text=True, capture_output=True, timeout=30)
    if run.returncode:
        raise RuntimeError(f"{exe.parent.name}/{graph.name}: native exit {run.returncode}\n{run.stderr[-1800:]}")
    values = dict(re.findall(r"^(\w+): (\d+)$", run.stdout, re.MULTILINE))
    return tuple(int(values[name]) for name in SUMMARY)


def main():
    with TemporaryDirectory(prefix="mbe-result-layout-") as scratch:
        root = Path(scratch)
        extract(root)
        prepare = runpy.run_path(str(root / PREPARE))["prepare_corrected"]
        driver = runpy.run_path(str(root / STUDY))
        here = root / Path(STUDY).parent
        driver["build"](root, here)
        raw, graph, two, meta, dump = (root / name for name in ("input.clean", "edges.txt", "double.clean", "input.json", "tuples.txt"))
        for orientation, transpose in (("input-left-upper", False), ("input-right-upper", True)):
            expected = fixture(raw, transpose, force_header=True)
            prepare(raw, graph, two, meta)
            target = signature(expected)
            for mode in driver["MODES"]:
                exe = here / "build" / mode / "mbet_fast"
                dump.unlink(missing_ok=True)
                with_output = native_signature(exe, graph, driver["COMMON"], dump)
                rows = tuples(dump)
                if len(rows) != len(expected) or set(rows) != expected or with_output != target:
                    raise ValueError(f"{orientation}/{mode}: tuple output or its summary differs from the oracle")
                if native_signature(exe, graph, driver["COMMON"]) != target:
                    raise ValueError(f"{orientation}/{mode}: checksum-only summary differs from the oracle")
                print(f"PASS {orientation}/{mode}: {len(expected)} exact tuples and checksum-only signature", flush=True)


if __name__ == "__main__":
    main()
