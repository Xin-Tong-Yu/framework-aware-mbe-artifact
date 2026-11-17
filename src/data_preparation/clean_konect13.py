#!/usr/bin/env python3
"""Convert 13 KONECT out.* bipartite edge lists to graph benchmark files.

Output: data_clean/<dataset>.txt
    <num_L> <num_R> <unique_edges>
    <zero_based_left_id> <zero_based_right_id>
    ...

No external Python dependencies. GNU sort used if available; a bounded-memory
pure-Python external sorter is used otherwise. All original files are unchanged.
"""
from __future__ import annotations

import argparse
import contextlib
import heapq
import os
import shutil
import subprocess
import sys
import tempfile
from array import array
from pathlib import Path

# SIGMOD 2026 Table 1: name, raw KONECT filename, |L|, |R|, |E|.
DATASETS = {
    'forum':         ('out.opsahl-ucforum',                     522,     899,    7089),
    'ukwiki':        ('out.edit-ukwikiquote',                        779,   16699,   32615),
    'escorts':       ('out.escorts',                           6625,   10107,   39044),
    'youtube':       ('out.youtube-groupmemberships',          30087,   94238,  293360),
    'github':        ('out.github',                            56519,  120867,  440237),
    'bkcrossing':    ('out.bookcrossing_full-rating_full-rating', 105278, 340523, 1149739),
    'stackoverflow': ('out.stackexchange-stackoverflow',       96678,  545195, 1301942),
    'actors':        ('out.actor-movie',                      127823,  383640, 1470404),
    'twitter':       ('out.munmun_twitterex_ut',              175214,  530418, 1890661),
    'bibsonomy':     ('out.bibsonomy-2ti',                    204673,  767447, 2499057),
    'imdb':          ('out.actor2',                           303617,  896302, 3782463),
    'amazon':        ('out.amazon-ratings',                  1230915, 2146057, 5743258),
    'dblp':          ('out.dblp-author',                     1953085, 5624219,12282059),
}


def numeric_edge_lines(source: Path):
    with source.open('r', encoding='utf-8', errors='replace', buffering=1024*1024) as f:
        for no, text in enumerate(f, 1):
            s = text.strip()
            if not s or s.startswith(('%', '#', '//')):
                continue
            parts = s.split()
            if len(parts) < 2:
                raise ValueError(f'{source.name}:{no}: expected at least two vertex IDs: {s[:100]}')
            try:
                x, y = int(parts[0]), int(parts[1])
            except ValueError as e:
                raise ValueError(f'{source.name}:{no}: invalid vertex IDs: {s[:100]}') from e
            # Columns 3+ are edge attributes (weights/timestamps), not vertices.
            yield x, y


def extract_edges(source: Path, raw: Path):
    count = 0
    low_x = low_y = high_x = high_y = None
    with raw.open('w', encoding='ascii', buffering=1024*1024) as out:
        for x, y in numeric_edge_lines(source):
            out.write(f'{x}\t{y}\n')
            if count == 0:
                low_x = high_x = x
                low_y = high_y = y
            else:
                if x < low_x: low_x = x
                if x > high_x: high_x = x
                if y < low_y: low_y = y
                if y > high_y: high_y = y
            count += 1
    if count == 0:
        raise ValueError(f'{source.name}: no edges were found')
    return count, (low_x, high_x), (low_y, high_y)


def can_use_gnu_sort():
    cmd = shutil.which('sort')
    if not cmd:
        return False
    try:
        p = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=5)
        return p.returncode == 0 and 'GNU coreutils' in p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def gnu_sort_unique(raw: Path, dest: Path, tmpdir: Path, mem: str):
    command = [shutil.which('sort'), '-u', '-t', '\t', '-k1,1n', '-k2,2n',
               '-S', mem, '--parallel=2', '-T', str(tmpdir), str(raw)]
    with dest.open('wb') as out:
        proc = subprocess.run(command, stdout=out, stderr=subprocess.PIPE,
                              env={**os.environ, 'LC_ALL': 'C'})
    if proc.returncode:
        raise RuntimeError(f'GNU sort failed: {proc.stderr.decode(errors="replace")[-1500:]}')


def python_sort_unique(raw: Path, dest: Path, tmpdir: Path, chunk_size: int):
    """External sort for native Windows or machines without GNU sort."""
    parts = []
    batch = []

    def save_chunk():
        if not batch: return
        batch.sort()
        chunk = tmpdir / f'part_{len(parts):05d}.txt'
        with chunk.open('w', encoding='ascii', buffering=1024*1024) as out:
            prev = None
            for pair in batch:
                if pair != prev:
                    out.write(f'{pair[0]}\t{pair[1]}\n')
                    prev = pair
        parts.append(chunk)
        batch.clear()

    with raw.open('r', encoding='ascii', buffering=1024*1024) as inp:
        for line in inp:
            x, y = line.split()
            batch.append((int(x), int(y)))
            if len(batch) >= chunk_size: save_chunk()
    save_chunk()

    with contextlib.ExitStack() as stack, dest.open('w', encoding='ascii', buffering=1024*1024) as out:
        inputs = [stack.enter_context(p.open('r', encoding='ascii', buffering=1024*1024)) for p in parts]
        heap = []
        for i, f in enumerate(inputs):
            line = f.readline()
            if line:
                a, b = line.split()
                heapq.heappush(heap, (int(a), int(b), i))
        prev = None
        while heap:
            x, y, i = heapq.heappop(heap)
            if (x, y) != prev:
                out.write(f'{x}\t{y}\n')
                prev = (x, y)
            line = inputs[i].readline()
            if line:
                a, b = line.split()
                heapq.heappush(heap, (int(a), int(b), i))


class IdCompressor:
    """Exact dense 0-based compaction. Use cheap int arrays for compact source IDs."""
    def __init__(self, bounds, expected_count):
        self.low, high = bounds
        span = high - self.low + 1
        if span <= 30_000_000 and span <= max(1_000_000, expected_count * 8):
            self.index = array('i', [-1]) * span  # compact: four bytes per source ID
            self.offset = self.low
            self.d = None
        else:
            self.index = None
            self.offset = 0
            self.d = {}
        self.count = 0

    def get(self, original):
        if self.index is not None:
            slot = original - self.offset
            value = self.index[slot]
            if value != -1: return value
            value = self.count
            self.index[slot] = value
            self.count += 1
            return value
        value = self.d.get(original)
        if value is not None: return value
        value = self.count
        self.d[original] = value
        self.count += 1
        return value


def prepare_compact(sorted_edges: Path, compact: Path, x_bounds, y_bounds, exp_l, exp_r):
    # Original sides may be reversed. Assign internal IDs independently on each side.
    left = IdCompressor(x_bounds, max(exp_l, exp_r))
    right = IdCompressor(y_bounds, max(exp_l, exp_r))
    count = 0
    with sorted_edges.open('r', encoding='ascii', buffering=1024*1024) as inp, \
         compact.open('w', encoding='ascii', buffering=1024*1024) as out:
        for text in inp:
            u, v = text.split()
            u0 = left.get(int(u))
            v0 = right.get(int(v))
            out.write(f'{u0}\t{v0}\n')
            count += 1
    swap = left.count > right.count
    return left.count, right.count, count, swap


def create_output(compact: Path, output: Path, a: int, b: int, edges: int, swap: bool):
    l, r = (b, a) if swap else (a, b)
    with output.open('w', encoding='ascii', buffering=1024*1024) as out, \
         compact.open('r', encoding='ascii', buffering=1024*1024) as inp:
        out.write(f'{l} {r} {edges}\n')
        if not swap:
            shutil.copyfileobj(inp, out, length=1024*1024)
        else:
            for line in inp:
                u, v = line.split()
                out.write(f'{v}\t{u}\n')
    return l, r


def clean_one(name, src_dir, dst_dir, args):
    filename, exp_l, exp_r, exp_edges = DATASETS[name]
    src = src_dir / filename
    if not src.is_file():
        raise FileNotFoundError(f'not found: {src}')
    print(f'\n[{name}] Reading: {src}', flush=True)
    # Work files are on output drive, and automatically removed per dataset.
    with tempfile.TemporaryDirectory(prefix=f'.clean_{name}_', dir=dst_dir) as temp:
        temp = Path(temp)
        raw, sorted_edges = temp / 'raw.tsv', temp / 'sorted.tsv'
        compact, output = temp / 'compact.tsv', temp / 'output.txt'
        raw_count, xb, yb = extract_edges(src, raw)
        method = 'gnu' if args.sorter == 'auto' and can_use_gnu_sort() else args.sorter
        if method == 'auto': method = 'python'
        print(f'[{name}] Raw edges={raw_count:,}; sorting/deduplicating ({method}) ...', flush=True)
        if method == 'gnu':
            if not can_use_gnu_sort(): raise RuntimeError('GNU sort is unavailable; use --sorter python')
            gnu_sort_unique(raw, sorted_edges, temp, args.sort_memory)
        else:
            python_sort_unique(raw, sorted_edges, temp, args.chunk_size)
        raw.unlink()  # free disk before preparing mappings
        a, b, e, swapped = prepare_compact(sorted_edges, compact, xb, yb, exp_l, exp_r)
        sorted_edges.unlink()
        l, r = (b, a) if swapped else (a, b)
        expected = (exp_l, exp_r, exp_edges)
        # KONECT edge files contain only vertices incident to an edge. Some
        # reported dimensions may additionally count zero-degree vertices.
        # Padding is opt-in, restricted to two *exact* known discrepancies,
        # and never changes, invents, or discards an edge.
        allowed_padding = {
            'escorts': (1, 1),   # observed 6,624 x 10,106; table 6,625 x 10,107
            'ukwiki': (0, 20),   # observed 779 x 16,679; table 779 x 16,699
        }
        missing_l, missing_r = exp_l - l, exp_r - r
        pad_isolates = (
            args.pad_isolates
            and name in allowed_padding
            and e == exp_edges
            and (missing_l, missing_r) == allowed_padding[name]
        )
        if pad_isolates:
            print(f'[{name}] ISOLATE-PADDING: observed L={l:,},R={r:,}; '
                  f'output L={exp_l:,},R={exp_r:,}; '
                  f'padding {missing_l} left and {missing_r} right zero-degree '
                  'vertices based on published dimensions (not verified from '
                  'the edge list). No edges added.', flush=True)
            l, r = exp_l, exp_r
        actual = (l, r, e)
        label = ('PASS_PADDED' if pad_isolates else 'PASS') if actual == expected else 'MISMATCH'
        print(f'[{name}] {label}: L={l:,} R={r:,} E={e:,} '
              f'(paper: {exp_l:,}/{exp_r:,}/{exp_edges:,}); '
              f'duplicates_removed={raw_count-e:,}; swapped={swapped}', flush=True)
        if actual != expected and not args.allow_mismatch:
            raise ValueError(f'{name}: dataset statistics differ from SIGMOD 2026 Table 1; '
                             'the output is NOT installed. Use --allow-mismatch only after investigation.')
        # Dense 0-based IDs in the compacted edge file remain unchanged. Any
        # padded vertex receives the next unused ID and has degree zero.
        if pad_isolates:
            final_a, final_b = (r, l) if swapped else (l, r)
        else:
            final_a, final_b = a, b
        create_output(compact, output, final_a, final_b, e, swapped)
        os.replace(output, dst_dir / (name + '.txt'))
    return label, actual, raw_count - e, filename


def main():
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description='Clean 13 SIGMOD 2026 KONECT datasets into data_clean/*.txt')
    ap.add_argument('--root', type=Path, default=root,
                    help='MBE-Modular-Suite-v2 project directory (default: directory of this script)')
    ap.add_argument('--src', type=Path, help='Override source data directory (default: ROOT/data)')
    ap.add_argument('--dst', type=Path, help='Override output directory (default: ROOT/data_clean)')
    ap.add_argument('--only', nargs='+', choices=list(DATASETS),
                    help='Clean only these datasets (default: all 13)')
    ap.add_argument('--sorter', choices=['auto','gnu','python'], default='auto')
    ap.add_argument('--sort-memory', default='256M', help='GNU sort memory budget per process')
    ap.add_argument('--chunk-size', type=int, default=300000, help='Pairs per Python external-sort chunk')
    ap.add_argument('--pad-isolates', action='store_true',
                    help='For escorts and ukwiki ONLY, when their precise known '
                         'edge-count/dimension discrepancies match the paper, '
                         'pad zero-degree vertices; never add edges')
    ap.add_argument('--allow-mismatch', action='store_true',
                    help='Write files even if graph sizes differ from published statistics')
    args = ap.parse_args()
    src_dir = (args.src or args.root / 'data').resolve()
    dst_dir = (args.dst or args.root / 'data_clean').resolve()
    if not src_dir.is_dir(): ap.error(f'data directory does not exist: {src_dir}')
    dst_dir.mkdir(parents=True, exist_ok=True)
    names = args.only or list(DATASETS)
    report = []
    failures = 0
    print(f'Input:  {src_dir}\nOutput: {dst_dir}\nTargets: {", ".join(names)}', flush=True)
    for name in names:
        try:
            label, stats, duplicate_count, src = clean_one(name, src_dir, dst_dir, args)
            report.append((name, src, label, *stats, duplicate_count))
        except (OSError, RuntimeError, ValueError) as ex:
            failures += 1
            report.append((name, DATASETS[name][0], 'ERROR', '', '', '', ''))
            print(f'[{name}] ERROR: {ex}', file=sys.stderr, flush=True)
    # A manifest is useful for validating the exact source mapping and graph sizes.
    manifest = dst_dir / 'konect13_manifest.tsv'
    # Preserve prior rows if a subset is rerun; overwrite only the selected
    # datasets' entries in the cumulative manifest.
    if args.only and manifest.is_file():
        old = {}
        with manifest.open('r', encoding='utf-8') as inp:
            for line in inp:
                cols = line.rstrip('\n').split('\t')
                if len(cols) == 7 and cols[0] in DATASETS:
                    old[cols[0]] = tuple(cols)
        for name0, row in old.items():
            if name0 not in names:
                report.append(row)
        report.sort(key=lambda r: list(DATASETS).index(r[0]))
    with manifest.open('w', encoding='utf-8') as out:
        out.write('name\tsource\tstatus\tL\tR\tE\tduplicates_removed\n')
        for row in report:
            out.write('\t'.join(map(str, row)) + '\n')
    print(f'\nFinished this run: {len(names)-failures}/{len(names)} succeeded. Manifest: {manifest}', flush=True)
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
