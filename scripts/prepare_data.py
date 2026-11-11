#!/usr/bin/env python3
"""Reassemble the canonical input archive and validate graph SHA-256 hashes.

This script only creates files ignored by Git. It does not download data or run any
enumeration experiment. Use --check-only to validate the committed parts without
writing or extracting the reconstructed archive.
"""
from pathlib import Path
import argparse, csv, hashlib, json, os, sys, zipfile, shutil
ROOT = Path(__file__).resolve().parent.parent

def stream_hash(path, block=1 << 20):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(block),b''): h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--check-only',action='store_true', help='validate binary parts without writing output files')
    p.add_argument('--no-extract',action='store_true',help='create only data/CLEANED_GRAPH_FILES.zip')
    args=p.parse_args()
    info=json.loads((ROOT/'data/ARCHIVE_PARTS.json').read_text())
    h=hashlib.sha256();size=0
    for obj in info['parts']:
        pth=ROOT/'data'/obj['file']
        if not pth.is_file() or pth.stat().st_size!=obj['bytes'] or stream_hash(pth)!=obj['sha256']:
            sys.exit(f'ERROR: missing or corrupted data part: {pth}')
        with pth.open('rb') as f:
            for chunk in iter(lambda:f.read(1<<20),b''):
                h.update(chunk);size+=len(chunk)
    if h.hexdigest()!=info['archive_sha256'] or size!=info['archive_bytes']:
        sys.exit('ERROR: combined archive checksum mismatch')
    print(f'PASS: all {len(info["parts"])} parts and complete archive hash match')
    if args.check_only:return
    archive=ROOT/'data'/info['archive_name']; temp=archive.with_suffix(archive.suffix+'.tmp')
    if not archive.is_file() or stream_hash(archive)!=info['archive_sha256']:
        with temp.open('wb') as dst:
            for obj in info['parts']:
                with (ROOT/'data'/obj['file']).open('rb') as src:shutil.copyfileobj(src,dst)
        os.replace(temp,archive)
    assert stream_hash(archive)==info['archive_sha256']
    if not args.no_extract:
        with zipfile.ZipFile(archive) as z:
            members=z.namelist()
            # Guard against unexpected paths when extracting the canonical archive.
            for name in members:
                parts=Path(name).parts
                if name.startswith('/') or '..' in parts or not name.startswith('data_clean/'):
                    sys.exit(f'ERROR: unexpected ZIP path {name}')
            z.extractall(ROOT)
        ref={r['graph']:r for r in csv.DictReader((ROOT/'data/COLLECTED_INPUT_SHA256.csv').open(newline=''))}
        assert len(ref)==13
        for g,row in ref.items():
            path=ROOT/'data_clean'/f'{g}.txt'
            if not path.exists() or stream_hash(path)!=row['sha256'] or path.stat().st_size!=int(row['bytes']):
                sys.exit('ERROR: graph checksum mismatch: '+g)
        print('PASS: 13 extracted cleaned graphs match their recorded input hashes')
    print('Ready. Run: python3 scripts/verify_artifact.py')

if __name__=='__main__':main()
