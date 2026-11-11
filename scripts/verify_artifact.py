#!/usr/bin/env python3
"""Validate input archive parts, extracted graph hashes and graph-header statistics.

This results-free edition does not require archived experiment CSV files.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-scan', action='store_true', help='also scan every edge for counts and valid vertex IDs')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'data/ARCHIVE_PARTS.json').read_text())
    problems = []
    for record in manifest['parts']:
        part = ROOT / 'data' / record['file']
        if not part.is_file() or part.stat().st_size != record['bytes'] or sha256(part) != record['sha256']:
            problems.append('missing/corrupt archive part: ' + record['file'])
    rows = list(csv.DictReader((ROOT / 'data/COLLECTED_INPUT_SHA256.csv').open(newline='')))
    stats = {r['graph']: r for r in csv.DictReader((ROOT / 'data/GRAPH_STATISTICS.csv').open(newline=''))}
    if len(rows) != 13 or len(stats) != 13:
        problems.append('expected exactly 13 graphs in both manifests')
    verified = 0
    for record in rows:
        name = record['graph']
        path = ROOT / 'data_clean' / record['file_name']
        if not path.is_file():
            problems.append('missing extracted graph: ' + name)
            continue
        if path.stat().st_size != int(record['bytes']) or sha256(path) != record['sha256']:
            problems.append('input SHA-256/size mismatch: ' + name)
            continue
        try:
            with path.open('r', encoding='utf-8') as f:
                header = f.readline().split()
                if len(header) != 3:
                    raise ValueError('expected nL nR m header')
                nl, nr, ne = map(int, header)
                info = stats[name]
                if (nl, nr, ne) != (int(info['left_vertices']), int(info['right_vertices']), int(info['edges'])):
                    raise ValueError('header mismatch with graph statistics')
                if args.full_scan:
                    count = 0
                    for lineno, line in enumerate(f, start=2):
                        parts = line.split()
                        if len(parts) != 2:
                            raise ValueError('malformed edge at line ' + str(lineno))
                        l, r = map(int, parts)
                        if not (0 <= l < nl and 0 <= r < nr):
                            raise ValueError('out-of-range edge at line ' + str(lineno))
                        count += 1
                    if count != ne:
                        raise ValueError(f'expected {ne} edges, observed {count}')
        except (OSError, ValueError, KeyError) as e:
            problems.append(f'invalid graph {name}: {e}')
            continue
        verified += 1
    print(f'Validated input graphs: {verified}/13; archive parts: {len(manifest["parts"])}')
    print('Results-free release: no precomputed experiment CSV files are required.')
    if problems:
        for p in problems:
            print('ERROR:', p)
        return 1
    print('PASS: all input hashes and graph headers agree with the metadata.' + (' Edge records checked.' if args.full_scan else ''))
    return 0

if __name__ == '__main__':
    sys.exit(main())
