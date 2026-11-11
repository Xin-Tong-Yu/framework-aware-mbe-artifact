#!/usr/bin/env python3
"""Install the source-only manuscript ablation suite under ignored outputs/."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "src/paper_ablations/MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip"
EXPECTED_SHA256 = "c6d1d8586cb5dff16ed3b87f35379e0c77e13a6533eb53774c26f6798ecb8995"
OUTPUT = ROOT / "outputs/paper_suite"
SUITE = OUTPUT / "framework_ablations"
REQUIRED = [
    "run_experiments.sh",
    "V63_MBET_CORE_SELECT/v63_run.py",
    "MBE_ST_CR_2X2_20261108/bench.py",
    "MBE_NEW_P0_20261109/bench.py",
    "MBE_CORRECTED_13DATA/bench.py",
    "IPS_ST_ABLATION_13DATA/run_ips_ablation.py",
    "IPS_ST_13DATA_2026/run_ips13.py",
]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="check archive without extracting anything")
    args = parser.parse_args()

    if not BUNDLE.is_file():
        raise SystemExit(
            "Missing source bundle: " + str(BUNDLE) +
            "\nUpload the supplied source-only ZIP to src/paper_ablations/"
        )
    if digest(BUNDLE) != EXPECTED_SHA256:
        raise SystemExit("Source-bundle SHA-256 does not match the pinned release.")
    with zipfile.ZipFile(BUNDLE) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        if not names or not all(name.startswith("framework_ablations/") for name in names):
            raise SystemExit("Unexpected source archive root.")
        for name in names:
            parts = Path(name).parts
            if name.startswith("/") or ".." in parts or "\\" in name:
                raise SystemExit("Unsafe archive path: " + name)
        missing = [
            item for item in REQUIRED
            if ("framework_ablations/" + item) not in names
        ]
        if missing:
            raise SystemExit("Missing required source files: " + ", ".join(missing))
        print("PASS: pinned source archive and required campaign files")
        if args.check_only:
            return 0
        OUTPUT.mkdir(parents=True, exist_ok=True)
        archive.extractall(OUTPUT)

    data = ROOT / "data_clean"
    if not data.is_dir():
        raise SystemExit("Restore inputs first: python3 scripts/prepare_data.py")
    link = SUITE / "data_clean"
    if link.is_symlink():
        if link.resolve() != data.resolve():
            raise SystemExit("Existing data_clean symlink points elsewhere.")
    elif link.exists():
        raise SystemExit("Refusing to overwrite a real data_clean directory inside suite.")
    else:
        link.symlink_to(data.resolve(), target_is_directory=True)

    print("PASS: source suite staged at", SUITE)
    print("Next: bash scripts/run_paper_ablations.sh check-source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
