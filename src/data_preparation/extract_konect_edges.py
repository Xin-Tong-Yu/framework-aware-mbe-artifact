#!/usr/bin/env python3
"""Verify local KONECT archives and extract only the pinned edge members."""

import argparse
import csv
from hashlib import sha256
from pathlib import Path, PurePosixPath
import sys
import tarfile
from tempfile import TemporaryDirectory


SOURCE_MAP = Path(__file__).resolve().parents[2] / "data/KONECT_SOURCE_MAP.csv"


def blocks(stream):
    return iter(lambda: stream.read(1 << 20), b"")


def extract(archive_dir, output_dir, record):
    name = record["raw_archive"]
    edge = record["raw_edge_member"]
    if not all(Path(value).name == value and value not in ("", ".", "..") for value in (name, edge)):
        raise ValueError("archive and member names must be basenames")
    with (archive_dir / name).open("rb") as source, TemporaryDirectory(dir=output_dir) as scratch:
        compressed_digest = sha256()
        for part in blocks(source):
            compressed_digest.update(part)
        if compressed_digest.hexdigest() != record["raw_archive_sha256"]:
            raise ValueError(f"archive SHA-256 differs for {name}")
        source.seek(0)
        pending = Path(scratch) / edge
        edges_digest = sha256()
        with tarfile.open(fileobj=source, mode="r|bz2") as archive:
            member = next((item for item in archive if PurePosixPath(item.name).name == edge), None)
            if member is None or not member.isfile():
                raise ValueError(f"missing regular edge member {edge} in {name}")
            with archive.extractfile(member) as source_edges, pending.open("wb") as output:
                for part in blocks(source_edges):
                    output.write(part)
                    edges_digest.update(part)
        if edges_digest.hexdigest() != record["raw_edge_sha256"]:
            raise ValueError(f"edge SHA-256 differs for {edge}")
        pending.replace(output_dir / edge)


def main():
    with SOURCE_MAP.open(encoding="utf-8-sig", newline="") as stream:
        sources = {row["graph"]: row for row in csv.DictReader(stream)}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_dir", type=Path, help="directory of locally obtained KONECT archives")
    parser.add_argument("output_dir", type=Path, help="destination for the verified out.* edge files")
    parser.add_argument("--graphs", nargs="+", choices=sources, help="verify a named subset of graphs")
    args = parser.parse_args()
    graphs = tuple(dict.fromkeys(args.graphs or sources))
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for graph in graphs:
            extract(args.archive_dir, args.output_dir, sources[graph])
            print(f"PASS {graph}: verified archive and edge SHA-256", flush=True)
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
