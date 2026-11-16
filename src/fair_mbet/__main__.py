#!/usr/bin/env python3
"""Zero-manual-extract unified per-biclique reporter for MBET / MBETM / Single-ST.
Run: python3 MBE_MBET_MBETM_FAIR_REPORT.zip --help
"""
import argparse, csv, fcntl, hashlib, json, math, os, platform, random, re, resource, shutil, statistics, subprocess, sys, tempfile, time, zipfile
from functools import lru_cache
from pathlib import Path

PACKAGE_VERSION = 'fair-output-v3-paired-resume'
ALL_MODES = ('mbet','mbetm','st_nocr','st_cr')
GRAPH_NAMES = ('youtube','actors','stackoverflow','bibsonomy','dblp','forum','ukwiki','escorts','github','bkcrossing','twitter','imdb','amazon')
COLS = ('graph','block','mode','runner_version','run_id','input_format','input_sha256','seed','stack_mb','cpu','count','checksum_xor','checksum_sum','search_s','order_s','presort_s','engine_total_s','wall_s','exe_sha256','compile_flags')

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
        s.add_argument('--resume',action='store_true',help='Reuse complete blocks from the same run configuration')
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

@lru_cache(maxsize=1)
def compiler_identity():
    name = os.environ.get('CXX', 'g++')
    compiler = shutil.which(name)
    if compiler is None:
        raise RuntimeError(f'Compiler not found: {name}')
    version = subprocess.check_output([compiler, '--version'], text=True)
    return compiler, version

def build(mode,opt,cache):
    members=zip_members(mode)
    flags=['-std=c++17',f'-{opt}','-DNDEBUG']
    if mode in ('mbet','mbetm'):
        flags+=['-DFAIR_REPORT']
        if mode=='mbetm':flags+=['-DMBETM']
    else:
        flags+=['-DMBE_V63_INLINE_CANDIDATE=1','-DMBE_V42_INLINE_RESULT=1','-DMBE_V30_SKIP_EMPTY_PREV=1']
        if mode=='st_cr':flags+=['-DMBE_V42_FAST_REPORT=1']
    cxx, version = compiler_identity()
    with zipfile.ZipFile(sys.argv[0]) as z:
        content_hash=hashlib.sha256()
        content_hash.update(json.dumps([PACKAGE_VERSION, mode, cxx, version, flags]).encode())
        for fn in members:content_hash.update(z.read(fn))
        key=content_hash.hexdigest()[:20]
        dst=Path(cache).resolve()/f'{mode}_{key}'
        exe=dst/'engine'
        dst.mkdir(parents=True, exist_ok=True)
        with (dst / '.build.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if exe.is_file():
                return exe, flags
            for fn in members:
                target = dst / fn
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(fn))
            source = dst / ('original' if mode in ('mbet', 'mbetm') else 'optimized')
            print(f'[BUILD] {mode} compile_flags={" ".join(flags)}', flush=True)
            with tempfile.TemporaryDirectory(dir=dst) as temp:
                binary = Path(temp) / 'engine'
                cmd = [cxx, *flags, '-I', str(source), str(source / 'main.cpp'), '-o', str(binary)]
                with (dst / 'compile.log').open('w') as log:
                    result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(f'Compilation failed: {dst / "compile.log"} (exit {result.returncode})')
                binary.replace(exe)
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

def execute(mode,graph,opt,cache,timeout,stack_mb=256,dump=None,cpu=None,built=None):
    graph=Path(graph).resolve()
    if not graph.is_file():raise FileNotFoundError(f'No input graph: {graph}')
    exe,flags=built if built is not None else build(mode,opt,cache)
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

def already(path, common, builds, repeats):
    found = {}
    with path.open(newline='') as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != COLS:
            raise RuntimeError(f'{path}: incompatible CSV schema; use a new output path')
        for row in reader:
            block, mode = int(row['block']), row['mode']
            key = block, mode
            expected = {**common, **builds.get(mode, {})}
            if (None in row or None in row.values() or key in found or not 1 <= block <= repeats
                    or mode not in builds or any(row[field] != str(value) for field, value in expected.items())):
                raise RuntimeError(f'{path}: incompatible or duplicate record {key}; use a new output path')
            if not math.isfinite(float(row['search_s'])) or float(row['search_s']) <= 0:
                raise RuntimeError(f'{path}: invalid search time in {key}')
            found[key] = row
    return found


def signatures(rows):
    return {(int(row['count']), int(row['checksum_xor']), int(row['checksum_sum'])) for row in rows}


def write_checkpoint(output, rows):
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        path = Path(temp) / output.name
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=COLS)
            writer.writeheader()
            writer.writerows(rows.values())
            f.flush()
            os.fsync(f.fileno())
        path.replace(output)


def bench_graph(graph, output, mm, args, graphname=None):
    if args.repeats < 1:
        raise ValueError('--repeats must be >= 1')
    graph = Path(graph).resolve()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(output.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        bench_locked(graph, output, mm, args, graphname or graph.stem)


def bench_locked(graph, output, mm, args, graphname):
    built = {mode: build(mode, args.opt, args.cache_dir) for mode in mm}
    builds = {mode: dict(exe_sha256=sha256(exe), compile_flags=' '.join(flags))
              for mode, (exe, flags) in built.items()}
    common = dict(graph=graphname, runner_version=PACKAGE_VERSION,
                  input_format='auto-header3-or-edge2', input_sha256=sha256(graph),
                  seed=args.seed, stack_mb=args.stack_mb, cpu=args.cpu if args.cpu is not None else '')
    params = dict(**common, builds=builds, modes=mm, repeats=args.repeats, timeout=args.timeout,
                  compiler=list(compiler_identity()), runner_sha256=sha256(sys.argv[0]),
                  host=list(platform.uname()), affinity=sorted(os.sched_getaffinity(0)))
    encoded = json.dumps(params, sort_keys=True)
    common['run_id'] = hashlib.sha256(encoded.encode()).hexdigest()
    manifest = output.with_suffix(output.suffix + '.manifest.json')
    rows = {}
    if args.resume and output.exists():
        if not manifest.is_file() or json.loads(manifest.read_text(encoding='utf-8')) != params:
            raise RuntimeError(f'{output}: run configuration changed or manifest missing; use a new output path')
        rows = already(output, common, builds, args.repeats)
        complete = {block for block in range(1, args.repeats + 1)
                    if all((block, mode) in rows for mode in mm)}
        rows = {key: row for key, row in rows.items() if key[0] in complete}
        if len(signatures(rows.values())) > 1:
            raise RuntimeError(f'{output}: incompatible output fingerprints; use a new output path')
    else:
        write_checkpoint(output, rows)
        with tempfile.TemporaryDirectory(dir=output.parent) as temp:
            path = Path(temp) / manifest.name
            path.write_text(json.dumps(params, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            path.replace(manifest)

    print(f'[BENCH] graph={graph.name} sha256={common["input_sha256"]} blocks={args.repeats} modes={mm}', flush=True)
    for block in range(1, args.repeats + 1):
        if (block, mm[0]) in rows:
            print(f'[SKIP_BLOCK] {block}', flush=True)
            continue
        order = list(mm)
        random.Random(args.seed + block).shuffle(order)
        new_rows = {}
        for mode in order:
            result = execute(mode, graph, args.opt, args.cache_dir, args.timeout, args.stack_mb,
                             cpu=args.cpu, built=built[mode])
            if (any(result[field] != value for field, value in builds[mode].items())
                    or not math.isfinite(result['search_s']) or result['search_s'] <= 0):
                raise RuntimeError(f'{mode}: binary identity changed or search time is invalid')
            new_rows[block, mode] = dict(**common, block=block, mode=mode, **result)
            print(f'[RUN] {block} {mode} search_s={result["search_s"]:.5f} count={result["count"]} '
                  f'xor={result["checksum_xor"]} sum={result["checksum_sum"]}', flush=True)
        if len(signatures([*rows.values(), *new_rows.values()])) != 1:
            raise RuntimeError(f'Block {block}: inconsistent output signatures; timings were discarded')
        rows.update(new_rows)
        write_checkpoint(output, rows)

    relevant = [rows[block, mode] for block in range(1, args.repeats + 1) for mode in mm]
    fingerprints = signatures(relevant)
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
            failures = []
            for name in GRAPH_NAMES:
                graph=Path(args.data_dir)/f'{name}.txt'
                if not graph.is_file():raise FileNotFoundError(f'Missing: {graph}')
            for name in GRAPH_NAMES:
                try:
                    bench_graph(Path(args.data_dir)/f'{name}.txt',Path(args.out_dir)/f'{name}.csv',modes(args.modes),args,graphname=name)
                except Exception as e:
                    print(f'[ERROR] {name}: {e}',file=sys.stderr,flush=True)
                    (Path(args.out_dir)/f'{name}.error.txt').write_text(str(e))
                    failures.append(name)
                else:
                    (Path(args.out_dir)/f'{name}.error.txt').unlink(missing_ok=True)
            if failures:
                raise RuntimeError('Batch incomplete for: ' + ', '.join(failures))
            print('[BATCH_FINISHED] all graph configurations validated', flush=True)
    except Exception as exc:
        print(f'[ERROR] {exc}',file=sys.stderr,flush=True)
        sys.exit(1)
