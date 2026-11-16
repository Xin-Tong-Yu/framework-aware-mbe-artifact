#!/usr/bin/env python3
"""Package the Double gate controls alongside the archived pure runner."""

import argparse
from pathlib import Path
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runners/MBE_PURE_ET1_ET2.zip"
SOURCE = ROOT / "src/pure_et1_et2"
OVERLAYS = ("__main__.py", "engine/two/ips.hpp")


def package(output):
    if output.resolve() == BASE.resolve():
        raise ValueError("Choose a separate output path for the gate experiment.")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = {name: (SOURCE / name).read_bytes().replace(b"\r\n", b"\n") for name in OVERLAYS}
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip.tmp", delete=False) as temp:
        archive = Path(temp.name)
    try:
        with ZipFile(BASE) as base, ZipFile(archive, "w") as result:
            if not set(files).issubset(base.namelist()):
                raise ValueError("Archived runner is missing the sources to overlay.")
            for entry in base.infolist():
                payload = files[entry.filename] if entry.filename in files else base.read(entry)
                result.writestr(entry, payload)
        with ZipFile(archive) as result:
            invalid = result.testzip()
            if invalid:
                raise ValueError(f"Package verification failed for {invalid}")
        archive.replace(output)
    finally:
        archive.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    package(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
