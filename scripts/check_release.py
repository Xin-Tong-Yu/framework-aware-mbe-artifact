#!/usr/bin/env python3
"""Read-only pre-publication checks: content size, accidental personal paths, checksums."""
from pathlib import Path
import re, sys, json, hashlib
ROOT=Path(__file__).resolve().parent.parent
ignored={'CLEANED_GRAPH_FILES.zip'}
patterns={
 'home_paths':re.compile(r'(?i)(/mnt/c/users/|C:\\Users\\|/home/[a-zA-Z0-9_.-]+/)'),
 'access_tokens':re.compile(r'(?i)(gh[pousr]_[A-Za-z0-9_]{18,}|github_pat_[A-Za-z0-9_]{18,})'),
 'private_keys':re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
}
issues=[]; files=0
for f in ROOT.rglob('*'):
 if not f.is_file() or '.git' in f.parts or f.name in ignored or 'data_clean' in f.parts or '.mbet_fair_build_cache' in f.parts: continue
 files+=1
 if f.stat().st_size>25*1024*1024: issues.append('File >25 MiB: '+str(f.relative_to(ROOT)))
 if f.suffix.lower() not in {'.py','.cpp','.hpp','.h','.md','.txt','.csv','.json','.sh','.yml','.yaml','.gitignore'}:continue
 if f.name.endswith('.txt') and 'data_clean' in f.parts:continue
 if f.name=='check_release.py':continue
 try: s=f.read_text(encoding='utf-8')
 except UnicodeDecodeError:continue
 for k,p in patterns.items():
  if p.search(s):issues.append(f'{k}: {f.relative_to(ROOT)}')
manifest=json.loads((ROOT/'data/ARCHIVE_PARTS.json').read_text())
for part in manifest['parts']:
 f=ROOT/'data'/part['file']
 if hashlib.sha256(f.read_bytes()).hexdigest()!=part['sha256']:issues.append('Bad data part: '+part['file'])
print(f'Checked {files} repository files and {len(manifest["parts"])} data parts')
if issues:
 for issue in issues: print('REVIEW:',issue)
 sys.exit(1)
print('PASS: no matches for selected sensitive path/token patterns and all committed files under 25 MiB')
print('NOTE: this scan cannot confirm third-party redistributability or cover all secrets.')
