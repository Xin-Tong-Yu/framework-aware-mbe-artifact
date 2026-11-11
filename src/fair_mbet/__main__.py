#!/usr/bin/env python3
"""Zero-manual-extract unified per-biclique reporter for MBET / MBETM / Single-ST.
Run: python3 MBE_MBET_MBETM_FAIR_REPORT.zip --help
"""
import argparse, csv, hashlib, json, os, random, re, resource, shutil, statistics, subprocess, sys, tempfile, time, zipfile
from pathlib import Path

PACKAGE_VERSION = 'fair-output-v2-header-fix-20261111'
ALL_MODES = ('mbet','mbetm','st_nocr','st_cr')
GRAPH_NAMES = ('youtube','actors','stackoverflow','bibsonomy','dblp','forum','ukwiki','escorts','github','bkcrossing','twitter','imdb','amazon')
COLS = ('graph','block','mode','runner_version','input_format','input_sha256','seed','stack_mb','cpu','count','checksum_xor','checksum_sum','search_s','order_s','presort_s','engine_total_s','wall_s','exe_sha256','compile_flags')

def args_parse():
    p=argparse.ArgumentParser(description='MBET/MBETM/Singe-ST same per-output checksum and timing, runs from ZIP; uses g++ under WSL/Linux')
    sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('modes')
    sub.add_parser('build').add_argument('--modes',default='mbet,mbetm')
    st=sub.add_parser('selftest'); st.add_argument('--cases',type=int,default=20); st.add_argument('--modes',default='mbet,mbetm,st_nocr,st_cr')
    single=sub.add_parser('run'); single.add_argument('mode',choices=ALL_MODES); single.add_argument('graph'); single.add_argument('--dump',help='Exact canonical tuples for small graph validation (slow on large graphs)'); single.add_argument('--timeout',type=int,default=7200)
    for name in ('bench','batch'):
        s=sub.add_parser(name)
        if name=='bench':s.add_argument('graph')
        else:s.add_argument('--data-dir',default='data_clean');s.add_argument('--out-dir',default='mbet_fair_13_results')
        s.add_argument('--modes',default='mbet,mbetm,st_nocr,st_cr');s.add_argument('--repeats',type=int,default=5)
        s.add_argument('--seed',type=int,default=71213);s.add_argument('--timeout',type=int,default=7200)
        s.add_argument('--stack-mb',type=int,default=256)
        s.add_argument('--cpu',type=int,default=None,help='Optional CPU affinity, e.g. --cpu 0 in WSL2')
        s.add_argument('--out',default='mbet_fair_youtube.csv')
        s.add_argument('--resume',action='store_true',help='Append only missing (mode,block) records in same CSV')
    p.add_argument('--opt',choices=('O1','O2','O3'),default='O3')
    p.add_argument('--cache-dir',default='.mbet_fair_build_cache')
    return p.parse_args()

def modes(s):
    m=[x.strip().lower() for x in s.split(',') if x.strip()]
    if not m or len(set(m))!=len(m) or any(x not in ALL_MODES for x in m):raise ValueError('invalid modes, choose distinct from '+','.join(ALL_MODES))
    return m

def sha256(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(4*1024*1024),b''):h.update(c)
    return h.hexdigest()

def zip_members(mode):
    base='original/' if mode in ('mbet','mbetm') else 'optimized/'
    return [base+x for x in ('main.cpp','src/MBET.hpp','common/bigraph.hpp','common/timer.hpp')] + (['original/fair_report.hpp'] if base=='original/' else [])

def build(mode,opt,cache):
    members=zip_members(mode)
    flags=['-std=c++17',f'-{opt}','-DNDEBUG']
    if mode in ('mbet','mbetm'):
        flags+=['-DFAIR_REPORT']
        if mode=='mbetm':flags+=['-DMBETM']
    else:
        flags+=['-DMBE_V63_INLINE_CANDIDATE=1','-DMBE_V42_INLINE_RESULT=1','-DMBE_V30_SKIP_EMPTY_PREV=1']
        if mode=='st_cr':flags+=['-DMBE_V42_FAST_REPORT=1']
    cxx=os.environ.get('CXX','g++')
    with zipfile.ZipFile(sys.argv[0]) as z:
        content_hash=hashlib.sha256()
        content_hash.update((PACKAGE_VERSION+mode+opt+cxx+' '.join(flags)).encode())
        for fn in members:content_hash.update(z.read(fn))
        key=content_hash.hexdigest()[:20]
        dst=Path(cache).resolve()/f'{mode}_{key}'
        exe=dst/'engine'
        if exe.exists():return exe,flags
        dst.mkdir(parents=True,exist_ok=True)
        for fn in members:
            target=dst/fn;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(fn))
        source=('original' if mode in ('mbet','mbetm') else 'optimized')
        cmd=[cxx,*flags,'-I',str(dst/source),str(dst/source/'main.cpp'),'-o',str(exe)]
        print(f'[BUILD] {mode} compile_flags={" ".join(flags)}',flush=True)
        with open(dst/'compile.log','w') as log:
            r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
        if r.returncode:raise RuntimeError(f'Compilation failed: {dst/"compile.log"} (exit {r.returncode})')
        (dst/'build.json').write_text(json.dumps(dict(mode=mode,compiler=cxx,flags=flags,sha256=sha256(exe),source_hash=key),indent=2))
        print(f'[BUILD_OK] {mode} {exe}',flush=True)
        return exe,flags

def parse_line(mode,out):
    if mode in ('mbet','mbetm'):
        m=re.findall(r'^\[FAIR_RESULT\] (.+)$',out,re.M)
        if len(m)!=1:raise RuntimeError(f'Expected one FAIR_RESULT, got {len(m)}')
        return dict(kv.split('=',1) for kv in m[0].split() if '=' in kv)
    pairs={}
    for name,value in re.findall(r'^([A-Za-z_]+):\s*([^\n]+)$',out,re.M):pairs[name]=value.strip()
    needed={'Count','Checksum_XOR','Checksum_SUM','Search_Time_ms'}
    if not needed.issubset(pairs):raise RuntimeError(f'Optimized output missing: {needed-set(pairs)}')
    return {'count':pairs['Count'],'checksum_xor':pairs['Checksum_XOR'],'checksum_sum':pairs['Checksum_SUM'],
            'search_s':str(float(pairs['Search_Time_ms'])/1000),'order_s':'', 'presort_s':'','engine_total_s':''}

def make_preexec(mb,cpu):
    def setter():
        resource.setrlimit(resource.RLIMIT_STACK,(mb*1024*1024,mb*1024*1024))
        if cpu is not None: os.sched_setaffinity(0,{cpu})
    return setter

def execute(mode,graph,opt,cache,timeout,stack_mb=256,dump=None,cpu=None):
    graph=Path(graph).resolve()
    if not graph.is_file():raise FileNotFoundError(f'No input graph: {graph}')
    exe,flags=build(mode,opt,cache)
    cmd=([str(exe),str(graph)]+(['--dump',str(Path(dump).resolve())] if dump else [])) if mode in ('mbet','mbetm') else [str(exe),'-f',str(graph),'--st','on','--et','off','--tg','off','--orientation','auto-size','-l','1','-r','1']+(['--emit',str(Path(dump).resolve())] if dump else [])
    env=os.environ.copy()
    env.pop("ALLOW_SWAP",None) # preserve same auto-size orientation in all modes
    t0=time.perf_counter()
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,preexec_fn=make_preexec(stack_mb,cpu),env=env)
    except subprocess.TimeoutExpired as e:raise RuntimeError(f'{mode}: TIMEOUT after {timeout} s') from e
    elapsed=time.perf_counter()-t0
    if result.returncode:
        print(result.stdout[-2500:],file=sys.stderr)
        print(result.stderr[-2500:],file=sys.stderr)
        raise RuntimeError(f'{mode} returned {result.returncode}')
    p=parse_line(mode,result.stdout)
    vals={}
    for name in ('count','checksum_xor','checksum_sum'):vals[name]=int(p[name])
    for name in ('search_s','order_s','presort_s','engine_total_s'):vals[name]=float(p[name]) if p.get(name) else ''
    vals.update(wall_s=elapsed,exe_sha256=sha256(exe),compile_flags=' '.join(flags))
    return vals

def read_dump(p):
    rows=[]
    for line in Path(p).read_text().splitlines():
        line=line.strip()
        if not line:continue
        ab=line.split('|') if '|' in line else re.findall(r'\[[^\]]*\]',line)
        if len(ab)!=2:raise ValueError(f'malformed dump {line}')
        sides=[]
        for x in ab:
            x=x.strip().strip('[]')
            sides.append(tuple(sorted(int(v) for v in x.split(',') if v)))
        rows.append(tuple(sides))
    return rows

def oracle(edges):
    us=sorted({u for u,v in edges});vs=sorted({v for u,v in edges});es=set(edges)
    if len(us)>12:raise ValueError('oracle too large')
    ans=set()
    for mask in range(1,1<<len(us)):
        left={u for i,u in enumerate(us) if mask>>i&1}
        right={v for v in vs if all((u,v) in es for u in left)}
        if not right:continue
        closed_left={u for u in us if all((u,v) in es for v in right)}
        ans.add((tuple(sorted(closed_left)),tuple(sorted(right))))
    return ans

def selftest(args):
    mm=modes(args.modes)
    with tempfile.TemporaryDirectory(prefix='mbet_fair_selftest_') as td:
        td=Path(td)
        z=zipfile.ZipFile(sys.argv[0])
        for testno in range(args.cases):
            if testno<2:
                fname=f'tests/{"toy" if testno==0 else "flipped"}.txt'
                edge_text=z.read(fname).decode()
                edges=[tuple(map(int,l.split())) for l in edge_text.splitlines() if l.strip()]
            else:
                rng=random.Random(900011+testno)
                nu=3+(testno%5);nv=3+(testno%4)
                edges=[(i,j) for i in range(1,nu+1) for j in range(1,nv+1) if rng.random()<(0.18+0.14*(testno%5))]
                if not edges:edges=[(1,1)]
            graph=td/f'test{testno}.txt'
            if testno%2==0:
                nl=max(u for u,v in edges)+1
                nr=max(v for u,v in edges)+1
                graph.write_text(f'{nl} {nr} {len(edges)}\n'+''.join(f'{u} {v}\n' for u,v in edges))
            else:
                graph.write_text(''.join(f'{u} {v}\n' for u,v in edges))
            ref=oracle(edges)
            checks=[]
            for mode in mm:
                out=td/f'{testno}_{mode}.txt'
                r=execute(mode,graph,args.opt,args.cache_dir,300,dump=out)
                rows=read_dump(out)
                if len(rows)!=len(ref) or set(rows)!=ref:
                    missing=ref-set(rows);extra=set(rows)-ref
                    raise RuntimeError(f'SELFTEST FAIL graph={testno} mode={mode} expected={len(ref)} got={len(rows)} unique={len(set(rows))} missing={list(missing)[:2]} extra={list(extra)[:2]}')
                checks.append((r['count'],r['checksum_xor'],r['checksum_sum']))
            if len(set(checks))!=1:raise RuntimeError(f'selftest hash mismatch graph={testno}: {checks}')
            if (testno+1)%10==0 or testno==args.cases-1:print(f'[SELFTEST] {testno+1}/{args.cases} graphs, {len(mm)*(testno+1)} full-output checks: PASS',flush=True)
        print(f'[PASS] {args.cases*len(mm)} exact-set + same fingerprint checks',flush=True)

def already(path,graphsha):
    found={};path=Path(path)
    if path.is_file():
        with path.open(newline='') as f:
            reader=csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != COLS:
                raise RuntimeError(f'{path}: old or incompatible CSV schema; use fresh v2 output directory')
            for r in reader:
                if r.get('runner_version') != PACKAGE_VERSION:
                    raise RuntimeError(f'{path}: old runner version; do not resume across versions')
                if r.get('input_sha256')!=graphsha:raise RuntimeError(f'{path}: input graph sha mismatch; use fresh output file')
                k=(int(r['block']),r['mode']);
                if k in found:raise RuntimeError(f'duplicate entry in CSV {k}')
                found[k]=r
    return found

def bench_graph(graph,output,mm,args,graphname=None):
    graph=Path(graph).resolve();output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    graphsha=sha256(graph)
    existing=already(output,graphsha) if args.resume else {}
    if output.exists() and not args.resume:output.unlink()
    print(f'[BENCH] graph={graph.name} sha256={graphsha} blocks={args.repeats} modes={mm}',flush=True)
    for block in range(1,args.repeats+1):
        order=list(mm)
        random.Random(args.seed+block).shuffle(order)
        for mode in order:
            if (block,mode) in existing:
                print(f'[SKIP] {block} {mode}',flush=True);continue
            v=execute(mode,graph,args.opt,args.cache_dir,args.timeout,args.stack_mb,cpu=args.cpu)
            row=dict(graph=graphname or graph.stem,block=block,mode=mode,runner_version=PACKAGE_VERSION,input_format='auto-header3-or-edge2',input_sha256=graphsha,seed=args.seed,stack_mb=args.stack_mb,cpu=args.cpu if args.cpu is not None else "",**v)
            with output.open('a',newline='') as f:
                w=csv.DictWriter(f,fieldnames=COLS)
                if f.tell()==0:w.writeheader()
                w.writerow(row);f.flush();os.fsync(f.fileno())
            print(f'[RUN] {block} {mode} search_s={v["search_s"]:.5f} count={v["count"]} xor={v["checksum_xor"]} sum={v["checksum_sum"]}',flush=True)
    rows=already(output,graphsha)
    relevant=[rows[block,mode] for block in range(1,args.repeats+1) for mode in mm]
    fingerprints={(int(r['count']),int(r['checksum_xor']),int(r['checksum_sum'])) for r in relevant}
    if len(fingerprints)!=1:raise RuntimeError(f'INCONSISTENT OUTPUT signatures {fingerprints}; do not use timings in paper')
    print(f'[PASS] {len(relevant)} runs, identical count/XOR/SUM = {next(iter(fingerprints))}',flush=True)
    for mode in mm:
        ts=[float(rows[block,mode]['search_s']) for block in range(1,args.repeats+1)]
        print(f'[MEDIAN] {mode} search_s={statistics.median(ts):.6f}',flush=True)
    if 'mbet' in mm:
        for mode in mm:
            if mode=='mbet':continue
            ratios=[float(rows[b,'mbet']['search_s'])/float(rows[b,mode]['search_s']) for b in range(1,args.repeats+1)]
            print(f'[PAIRED] mbet/{mode} median={statistics.median(ratios):.6f}x',flush=True)
    print(f'[CSV] {output}',flush=True)

if __name__=='__main__':
    try:
        args=args_parse()
        if sys.platform!='linux':raise RuntimeError('This packaged runner is for Linux or WSL2; use WSL on Windows')
        if args.cmd=='modes':
            for m in ALL_MODES:print(m,{'mbet':'2024 official MBET; identical per-biclique hash','mbetm':'2024 official MBETM; identical per-biclique hash','st_nocr':'candidate optimized ST; materialized same hash as published baselines','st_cr':'candidate optimized ST + fast compressed CR (same hash, different output work)'}[m])
        elif args.cmd=='build':
            for m in modes(args.modes):build(m,args.opt,args.cache_dir)
        elif args.cmd=='selftest':selftest(args)
        elif args.cmd=='run':
            v=execute(args.mode,args.graph,args.opt,args.cache_dir,args.timeout,dump=args.dump)
            print('[FAIR_RUN]',json.dumps(v,sort_keys=True))
        elif args.cmd=='bench':bench_graph(args.graph,args.out,modes(args.modes),args)
        elif args.cmd=='batch':
            for name in GRAPH_NAMES:
                graph=Path(args.data_dir)/f'{name}.txt'
                if not graph.is_file():raise FileNotFoundError(f'Missing: {graph}')
            for name in GRAPH_NAMES:
                try:
                    bench_graph(Path(args.data_dir)/f'{name}.txt',Path(args.out_dir)/f'{name}.csv',modes(args.modes),args,graphname=name)
                except Exception as e:
                    print(f'[ERROR] {name}: {e}',file=sys.stderr,flush=True)
                    (Path(args.out_dir)/f'{name}.error.txt').write_text(str(e))
            print('[BATCH_FINISHED] inspect .error.txt files and CSV completeness; incomplete graphs are NOT validated',flush=True)
    except Exception as exc:
        print(f'[ERROR] {exc}',file=sys.stderr,flush=True)
        sys.exit(1)
