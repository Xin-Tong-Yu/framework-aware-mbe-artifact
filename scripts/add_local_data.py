#!/usr/bin/env python3
"""Prepare chunked GitHub-ready graph input parts from an existing cleaned-data folder.

This is for the lightweight repository ZIP, which does not include the graph bytes.
It checks each input SHA-256 against the verified clean input manifest before
staging any data parts. Does not alter the source input files.
"""
import argparse
import csv
import hashlib
import json
import pathlib
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

def file_hash(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):
            h.update(b)
    return h.hexdigest()

def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('--input',required=True,help='Folder containing the 13 canonical cleaned graph TXT files')
    a=pa.parse_args()
    inp=pathlib.Path(a.input).expanduser().resolve()
    ref=list(csv.DictReader((ROOT/'data/COLLECTED_INPUT_SHA256.csv').open(newline='')))
    if len(ref)!=13:raise SystemExit('ERROR: expected 13 reference graphs')
    for row in ref:
        file=inp/row['file_name']
        if not file.is_file() or file.stat().st_size!=int(row['bytes']) or file_hash(file)!=row['sha256']:
            raise SystemExit('ERROR: wrong or missing cleaned graph file: '+str(file))
    parts=ROOT/'data/parts'
    parts.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mbe_zip_parts_') as td:
        archive=pathlib.Path(td)/'CLEANED_GRAPH_FILES.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for row in ref:
                info=zipfile.ZipInfo('data_clean/'+row['file_name'],date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o644 << 16
                with z.open(info,'w',force_zip64=True) as dst, (inp/row['file_name']).open('rb') as src:
                    while True:
                        chunk=src.read(1<<20)
                        if not chunk:break
                        dst.write(chunk)
        old=list(parts.glob('graph_data_*.part'))
        for item in old:item.unlink()
        objs=[];step=20*1024*1024
        with archive.open('rb') as f:
            index=0
            while True:
                data=f.read(step)
                if not data:break
                name=f'graph_data_{index:03d}.part'
                (parts/name).write_bytes(data)
                objs.append({'file':'parts/'+name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
                index+=1
        meta={'archive_name':'CLEANED_GRAPH_FILES.zip','archive_bytes':archive.stat().st_size,
              'archive_sha256':file_hash(archive),'chunk_size_bytes':step,'parts':objs}
        (ROOT/'data/ARCHIVE_PARTS.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('PASS: staged',len(objs),'pieces (maximum 20 MiB each) from 13 verified cleaned graphs')
    print('Next: python3 scripts/prepare_data.py --check-only')
    print('Then inspect rights and run git add . to include the parts.')

if __name__=='__main__':main()
