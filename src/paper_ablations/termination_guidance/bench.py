#!/usr/bin/env python3
"""Matched explicit-enumeration experiments for MBE_FAST_FOUR_MODES.
One text report, resumable by completed blocks. The benchmarked region is
reported by each binary; preprocessing is outside that region.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import resource
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

GRAPHS = ('youtube', 'actors', 'stackoverflow', 'bibsonomy', 'dblp',
          'forum', 'ukwiki', 'escorts', 'github', 'bkcrossing',
          'twitter', 'imdb', 'amazon')
MAIN = ('one_et', 'one_et_tg', 'two_et', 'two_et_tg_compact')
ADDITIONAL = ('one_st_d', 'one_et_tg_d', 'two_st_hybrid',
              'two_et_hybrid', 'two_et_tg')
ANCHORS = ('one_st', 'two_st')
PROGRAM_ID = 'MBE_2026_CORRECT_HEADER_BITMAP_CAP_1'


def sha256(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def match_one(pattern, s, typ=str):
    m = re.search(pattern, s, re.M)
    return typ(m.group(1)) if m else None


def parse_run(mode, out, sec):
    if mode.startswith('one_'):
        count = match_one(r'^Count:\s*(\d+)\s*$', out, int)
        xor = match_one(r'^Checksum_XOR:\s*(\d+)\s*$', out, int)
        su = match_one(r'^Checksum_SUM:\s*(\d+)\s*$', out, int)
        ms = match_one(r'^Search_Time_ms:\s*([\d.]+)\s*$', out, float)
        et = match_one(r'^Modules:\s*ST=on\s+ET=(on|off)', out)
        tg = match_one(r'^Modules:\s*ST=on\s+ET=(?:on|off)\s+TG=(on|off)', out)
        if not all(x is not None for x in (count, xor, su, ms, et, tg)):
            raise ValueError('Missing one-sided search time, status, or fingerprint')
        assert et == ('on' if 'et' in mode else 'off'), (mode, et)
        assert tg == ('on' if 'tg' in mode else 'off'), (mode, tg)
        return dict(count=count, xor=xor, sum=su, ms=ms, wall_s=round(sec, 4), et=et, tg=tg,
                    et_hits=match_one(r'^ET_Hits:\s*(\d+)',out,int),
                    tg_prefix2_hits=match_one(r'^TG_Prefix2_Hits:\s*(\d+)',out,int),
                    tg_ge3_hits=match_one(r'^TG_Prefix_Ge3_Hits:\s*(\d+)',out,int),
                    tg_deferred_paths=match_one(r'^TG_Deferred_Paths:\s*(\d+)',out,int))
    count = match_one(r'^Maximal_BiClique_Count:\s*(\d+)\s*,\s*Time:\s*\d+\s*ms', out, int)
    xor = match_one(r'^Enumeration_Set_XOR:\s*(\d+)\s*$', out, int)
    su = match_one(r'^Enumeration_Set_SUM:\s*(\d+)\s*$', out, int)
    ms = match_one(r'^Maximal_BiClique_Count:\s*\d+\s*,\s*Time:\s*(\d+)\s*ms', out, float)
    st = match_one(r'^ST:\s*(on|off)', out)
    et = match_one(r'^ET:\s*(on|off)', out)
    tg = match_one(r'^TG:\s*(on|off)', out)
    if not all(x is not None for x in (count, xor, su, ms, st, et, tg)):
        raise ValueError('Missing IPS search time, switches, or set fingerprint')
    assert st == 'on' and et == ('on' if 'et' in mode else 'off'), (mode, et)
    assert tg == ('on' if 'tg' in mode else 'off'), (mode, tg)
    return dict(count=count, xor=xor, sum=su, ms=ms, wall_s=round(sec, 4), et=et, tg=tg,
                et_used=match_one(r'^ET_Used / TT = (\d+)',out,int),
                et_output=match_one(r'^ET_Output_Count:\s*(\d+)',out,int),
                pivot_x=match_one(r'^Pivot_X_Choices:\s*(\d+)',out,int),
                pivot_c=match_one(r'^Pivot_C_Choices:\s*(\d+)',out,int))


def cpupre(cpu, memory_limit_mib=None):
    if cpu is None and memory_limit_mib is None: return None
    def fn():
        if cpu is not None: os.sched_setaffinity(0, {cpu})
        if memory_limit_mib is not None:
            limit = memory_limit_mib * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    return fn


def execute(cmd, timeout, cpu, cwd, memory_limit_mib=None):
    start = time.monotonic()
    try:
        if Path('/usr/bin/time').is_file():
            cmd=['/usr/bin/time','-f','BENCH_PEAK_RSS_KB=%M']+cmd
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=timeout, cwd=cwd, preexec_fn=cpupre(cpu, memory_limit_mib))
        wall = time.monotonic() - start
        return p.returncode, p.stdout, p.stderr, wall, None
    except subprocess.TimeoutExpired as e:
        return -1, '', '', time.monotonic() - start, 'timeout'
    except Exception as e:
        return -1, '', '', time.monotonic() - start, repr(e)


def interpolate(anchor_a, pa, anchor_b, pb, pos):
    if pa == pb: return anchor_a
    return anchor_a + (anchor_b - anchor_a) * (pos - pa) / (pb - pa)


def complete(block, modes):
    return (block.get('completed') is True and
            len(block.get('jobs', [])) == len(modes) + 4)


def block_sequence(modes, seed):
    middle = list(modes)
    random.Random(seed).shuffle(middle)
    return [*ANCHORS, *middle, *reversed(ANCHORS)]


def matching_outputs(jobs):
    return (all(job['status'] == 'OK' for job in jobs)
            and len({job['count'] for job in jobs}) == 1
            and all(len({(job['xor'], job['sum']) for job in jobs if job['mode'].startswith(prefix)}) == 1
                    for prefix in ('one_', 'two_')))


def recover_blocks(blocks, modes, seeds):
    recovered = {}
    for block in blocks:
        if not complete(block, modes) or not block.get('validation', '').startswith('PASS'):
            continue
        seed = block['seed']
        if seed not in seeds or seed in recovered:
            raise ValueError(f'Unexpected or repeated validated block seed {seed}')
        jobs = block['jobs']
        if ([job['mode'] for job in jobs] == block_sequence(modes, seed)
                and matching_outputs(jobs)
                and all(math.isfinite(job['ms']) and job['ms'] > 0 for job in jobs)):
            recovered[seed] = block
    return recovered


def save_checkpoint(path, document):
    with TemporaryDirectory(dir=path.parent) as temp:
        pending = Path(temp) / path.name
        with pending.open('w', encoding='utf-8') as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(path)


def make_report(meta, data, graphs, runs, modes, path):
    lines = []
    def add(s): lines.append(s)
    add('# Matched FULL ENUMERATION search timing: single-sided MBET vs double-sided IPS')
    add('# ST -> ET -> ET+TG with two separate, interpolated ST control anchors')
    add('# The checksums are framework-specific; compare counts across frameworks, never XOR numbers.')
    add('[META] ' + json.dumps(meta, ensure_ascii=False, sort_keys=True))
    validated=[d for d in graphs if len(data.get(d, [])) == runs and
               all(complete(b,modes) and b.get('validation','').startswith('PASS') for b in data[d])]
    add('[COMPLETE_DATASETS] ' + ', '.join(validated))
    add('[NOT_COMPLETE] ' + ', '.join(d for d in graphs if d not in validated))
    add('[VALIDATED_COMPLETE_DATASETS] ' + ', '.join(validated))
    summary = {}
    primary = list(ANCHORS) + list(modes)
    for graph in graphs:
        blocks = data.get(graph, [])
        add('\n=== DATASET ' + graph + ' complete_blocks=' + str(len(blocks)) + '/' + str(runs) + ' ===')
        ratios = {m: [] for m in primary if m not in ANCHORS}
        ratios['two_st_vs_one_st'] = []
        ratios['two_et_tg_compact_vs_one_et_tg'] = []
        ratios['two_et_vs_one_et'] = []
        direct = {('one_et_tg', 'one_et'): [], ('two_et_tg_compact', 'two_et'): [],
                  ('two_et_hybrid', 'two_st_hybrid'): [],
                  ('two_et_tg', 'two_et_hybrid'): []}
        for ib, block in enumerate(blocks, 1):
            jobs = block.get('jobs', [])
            if not complete(block, modes):
                add('[INCOMPLETE_BLOCK] ' + str(ib))
                continue
            trusted = block.get('validation', '').startswith('PASS')
            ad = {m: [] for m in ANCHORS}
            for i, j in enumerate(jobs):
                if j.get('status') == 'OK' and j['mode'] in ANCHORS:
                    ad[j['mode']].append((i, j['ms']))
            get = lambda mode: [(i, j) for i, j in enumerate(jobs) if j['mode'] == mode and j.get('status') == 'OK']
            anchor_at = {}
            if all(len(ad[m]) == 2 for m in ANCHORS):
                for m in ANCHORS:
                    pa, a = ad[m][0]; pb, b = ad[m][1]
                    anchor_at[m] = lambda pos, a=a, b=b, pa=pa, pb=pb: interpolate(a, pa, b, pb, pos)
                pos_mid = (len(jobs) - 1) / 2
                if trusted: ratios['two_st_vs_one_st'].append(anchor_at['one_st'](pos_mid) / anchor_at['two_st'](pos_mid))
            for mode in modes:
                hits = get(mode)
                if trusted and hits and ('one_st' if mode.startswith('one_') else 'two_st') in anchor_at:
                    pos, job = hits[0]
                    baseline = 'one_st' if mode.startswith('one_') else 'two_st'
                    ratios[mode].append(anchor_at[baseline](pos) / job['ms'])
            if trusted:
                for two, one, key in [('two_et_tg_compact','one_et_tg','two_et_tg_compact_vs_one_et_tg'),
                                      ('two_et','one_et','two_et_vs_one_et')]:
                    ta, oa = get(two), get(one)
                    if ta and oa:
                        ratios[key].append(oa[0][1]['ms'] / ta[0][1]['ms'])
            for (num, den), dest in direct.items():
                if trusted and num in modes and (den in modes or den in ANCHORS):
                    ns, ds = get(num), get(den)
                    if ns and ds: dest.append(ds[0][1]['ms'] / ns[0][1]['ms'])
            anchors = {m: [round(ms, 3) for _, ms in ad[m]] for m in ANCHORS}
            drift = {m: (round((ad[m][-1][1] / ad[m][0][1] - 1) * 100, 3)
                         if len(ad[m]) == 2 else None) for m in ANCHORS}
            add('[BLOCK] id=%d seed=%d anchors_ms=%s drift_pct=%s' % (
                ib, block.get('seed', -1), json.dumps(anchors), json.dumps(drift)))
            for j in jobs:
                if j.get('status') == 'OK':
                    stat = ' '.join('%s=%s'%(k,j[k]) for k in ('et_hits','tg_prefix2_hits','tg_ge3_hits',
                      'tg_deferred_paths','et_used','et_output','pivot_x','pivot_c','peak_rss_kb') if j.get(k) is not None)
                    add('[RUN] mode=%s search_ms=%.3f wall_s=%.3f count=%d xor=%d sum=%d %s' % (
                        j['mode'], j['ms'], j['wall_s'], j['count'], j['xor'], j['sum'], stat))
                else:
                    add('[FAIL] mode=%s status=%s details=%s' % (
                        j['mode'], j.get('status', 'unknown'), j.get('details', '')[:240]))
            add('[CORRECTNESS] ' + block.get('validation', 'NO VALIDATION'))
        for mode, vals in ratios.items():
            if len(vals) == runs:
                summary.setdefault(mode, {})[graph] = statistics.median(vals)
            add('[PAIRED] mode=%s blocks=%d/%d median_speedup=%s block_ratios=%s' % (
                mode, len(vals), runs, ('%.6fx' % statistics.median(vals) if vals else 'N/A'),
                ','.join('%.5f' % x for x in vals)))
        for (num, den), vals in direct.items():
            if vals:
                add('[DIRECT] %s_vs_%s blocks=%d median_speedup=%.6fx ratios=%s' % (
                    num, den, len(vals), statistics.median(vals), ','.join('%.5f' % x for x in vals)))
    add('\n=== CROSS-GRAPH SUMMARY ===')
    for mode in ['two_st_vs_one_st', 'two_et_vs_one_et', 'two_et_tg_compact_vs_one_et_tg'] + list(modes):
        vals = summary.get(mode, {})
        full = (len(vals) == len(graphs) and all(g in validated for g in graphs))
        if full:
            gm = math.exp(sum(math.log(x) for x in vals.values()) / len(vals))
            wins = sum(v >= 1.02 for v in vals.values())
            losses = sum(v < 1 for v in vals.values())
            add('[GM_COMPLETE] mode=%s datasets=%d gm=%.6fx wins_over_2pct=%d losses=%d' % (mode, len(vals), gm, wins, losses))
        else:
            add('[GM_INCOMPLETE] mode=%s covered=%d/%d (no overall GM; unavailable or failed runs)' % (mode, len(vals), len(graphs)))
    add('[REPORT] ' + str(path))
    content='\n'.join(lines)+'\n'
    temp=path.with_suffix('.tmp')
    temp.write_text(content,encoding='utf-8')
    temp.replace(path)


def main():
    ap=argparse.ArgumentParser(description='13-graph matched explicit-enumeration ST/ET/TG and cross-backbone comparison')
    ap.add_argument('--project-root', type=Path, default=Path.cwd())
    ap.add_argument('--datasets', nargs='+', default=list(GRAPHS))
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--timeout', type=int, default=1200)
    ap.add_argument('--cpu', default='auto')
    ap.add_argument('--extended', action='store_true', help='Additionally run D and matched hybrid adjacency configurations')
    ap.add_argument('--fresh', action='store_true', help='Discard prior checkpoint and repeat all blocks')
    ap.add_argument('--skip-build', action='store_true')
    ap.add_argument('--process-only',nargs='+',default=None)
    ap.add_argument('--retry-failed',action='store_true')
    ap.add_argument('--ips-memory-mib',type=int,default=6144)
    ap.add_argument('--skip-expected-count',action='store_true',help='Only for synthetic local smoke tests')
    ap.add_argument('--seed', type=int, default=2602026)
    args=ap.parse_args()
    if args.runs < 1 or args.timeout < 1: ap.error('runs and timeout must be positive')
    if args.ips_memory_mib < 1024: ap.error('--ips-memory-mib must be at least 1024')
    if args.process_only and any(d not in GRAPHS for d in args.process_only): ap.error('unknown --process-only dataset')
    if args.extended: ap.error('--extended disabled in the corrected, safety-checked six-mode protocol')
    if any(d not in GRAPHS for d in args.datasets): ap.error('Unknown dataset name')
    if len(set(args.datasets)) != len(args.datasets): ap.error('Repeated dataset name')
    root=args.project_root.resolve()
    suite=root/'MBE_FAST_FOUR_MODES'
    HERE=Path(__file__).resolve().parent
    if not (suite/'run.sh').is_file(): ap.error(f'Package missing: {suite}/run.sh')
    data_dir=root/'data_clean'
    modes=list(MAIN) + (list(ADDITIONAL) if args.extended else [])
    if args.cpu == 'auto':
        cpu=min(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None
    elif args.cpu == 'none': cpu=None
    else:
        cpu=int(args.cpu)
        if hasattr(os,'sched_getaffinity') and cpu not in os.sched_getaffinity(0):
            ap.error(f'CPU {cpu} not available (allowed: {sorted(os.sched_getaffinity(0))})')
    if not args.skip_build:
        print('[BUILD] compiling four-mode package once...',flush=True)
        subprocess.run(['bash',str(HERE/'build.sh')],check=True,cwd=root)
    if not (suite/'bin'/'one_core').is_file(): ap.error('Original one_core binary absent; compile the original MBE_FAST_FOUR_MODES first')
    if args.extended:
        hybrid_bin=suite/'bin'/'two_et_hybrid'
        src=suite/'two'/'source'
        if not hybrid_bin.exists() or not args.skip_build:
            print('[BUILD] two_et_hybrid: exact matched ET-only control for hybrid adjacency',flush=True)
            subprocess.run(['g++','-O3','-std=c++17','-march=native','-fopenmp','-UNDEBUG',
                            '-DIPS_ST_V24_SINGLE_DEFECT','-DIPS_ST_V15_HASHLESS',
                            '-DIPS_ST_V15_ROW_CACHE','-DIPS_CLASSIC_PIVOT',
                            '-I',str(src),str(src/'main.cpp'),'-o',str(hybrid_bin)],check=True,cwd=root)
    if args.extended:
        # The existing run.sh does not list two_et_hybrid. In this runner it is called directly.
        pass
    bins={'one_st':suite/'bin'/'one_core', 'two_st':HERE/'bin'/'two_st_safe',
          'one_et':suite/'bin'/'one_core', 'one_et_tg':suite/'bin'/'one_core',
          'two_et':HERE/'bin'/'two_et_safe', 'two_et_tg_compact':HERE/'bin'/'two_et_tg_compact_safe',
          'one_st_d':suite/'bin'/'one_core', 'one_et_tg_d':suite/'bin'/'one_core',
          'two_st_hybrid':suite/'bin'/'two_st_hybrid',
          'two_et_hybrid':suite/'bin'/'two_et_hybrid', 'two_et_tg':suite/'bin'/'two_et_tg'}
    checksums={m:sha256(bins[m].resolve()) for m in list(ANCHORS)+modes}
    diag=root/'diagnostics';diag.mkdir(parents=True,exist_ok=True)
    cp=diag/'MBE_CORRECTED_MAIN_CHECKPOINT.json'
    report=diag/'MBE_CORRECTED_MAIN_ALL_RESULTS.txt'
    files={d:data_dir/(d+'.txt') for d in args.datasets}
    filespecs={d:(dict(path=str(p),sha256=sha256(p)) if p.is_file() else dict(path=str(p),missing=True)) for d,p in files.items()}
    meta=dict(program=PROGRAM_ID, created=dt.datetime.now(dt.timezone.utc).isoformat(),
              root=str(root), datasets=list(args.datasets), runs=args.runs,
              timeout=args.timeout, cpu=cpu, seed=args.seed, modes=modes,
              bins=checksums, input=filespecs, extended=False,
              ips_memory_mib=args.ips_memory_mib, preprocessing='skip_three_integer_header_shared_edge_list',
              expected_count_check=not args.skip_expected_count)
    if cp.is_file() and not args.fresh:
        stored=json.loads(cp.read_text(encoding='utf-8'))
        prev=stored['meta'].copy();curr=meta.copy();prev.pop('created',None);curr.pop('created',None)
        if prev!=curr:
            ap.error(f'Checkpoint configuration or binary/input changed: {cp}. Use --fresh or remove the checkpoint to reset.')
        meta=stored['meta']
        data=stored['blocks']
        print('[RESUME] existing complete blocks reused; incomplete blocks will rerun',flush=True)
        failed_datasets=stored.get('failed_datasets',{})
    else:
        data={}
        failed_datasets={}
    def write_checkpoint():
        save_checkpoint(cp, dict(meta=meta, blocks=data, failed_datasets=failed_datasets))
        make_report(meta,data,args.datasets,args.runs,modes,report)
    from prepare_corrected import prepare_corrected
    from known_counts import KNOWN_COUNT
    requested = [d for d in args.datasets if not args.process_only or d in args.process_only]
    for dg,d in enumerate(args.datasets):
        if args.process_only and d not in args.process_only:
            print('[SKIP_DATASET]',d,'not selected',flush=True);continue
        if d in failed_datasets and not args.retry_failed:
            print('[SKIP_FAILED_DATASET]',d,failed_datasets[d],flush=True);continue
        seeds = [args.seed + (dg+1)*100003 + (b+1)*9176 for b in range(args.runs)]
        stored_blocks = data.get(d, [])
        recovered = recover_blocks(stored_blocks, modes, seeds)
        if len(recovered) != len(stored_blocks):
            print('[RESET_UNTRUSTED_BLOCKS]', d, len(stored_blocks) - len(recovered), flush=True)
        blocks = data[d] = [recovered[seed] for seed in seeds if seed in recovered]
        failed_datasets.pop(d, None)
        if len(recovered) == args.runs:
            print('[RESUME_GRAPH]', d, len(recovered), 'validated blocks retained', flush=True)
            continue
        p=files[d]
        if not p.exists():
            print('[MISSING_GRAPH]',d,p,flush=True)
            continue
        # Both frameworks MUST use the same graph, with the three-integer
        # header removed from the edge list. A header is NOT an extra edge.
        clean=HERE/'.cache'/(d+'.two.clean')
        one_input=HERE/'.cache'/(d+'.one.txt')
        print('[PREPARE_CORRECT_HEADER]',d,flush=True)
        try:
            prepare_corrected(p,one_input,clean,HERE/'.cache'/(d+'.meta.json'))
        except Exception as e:
            failed_datasets[d]='INPUT_PREPARATION_FAILED '+repr(e)
            print('[INPUT_PREPARATION_FAILED]',d,repr(e),flush=True)
            write_checkpoint()
            continue
        for b, seed in enumerate(seeds, 1):
            if seed in recovered:
                print('[RESUME_BLOCK]', d, b, flush=True)
                continue
            sequence=block_sequence(modes, seed)
            jobs=[]
            block = dict(seed=seed, jobs=jobs, completed=False)
            blocks.append(block)
            blocks.sort(key=lambda old: old['seed'])
            print(f'[BLOCK_START] {d} block={b}/{args.runs} jobs={len(sequence)}',flush=True)
            for k,mode in enumerate(sequence,1):
                if mode=='two_et_hybrid':
                    cmd=[str(bins[mode]),'-f',str(clean),'-d','two']
                elif mode.startswith('two_'):
                    cmd=[str(bins[mode]),'-f',str(clean),'-d','two']
                else:
                    cmd=['bash',str(suite/'run.sh'),mode,str(one_input)]
                rc,out,err,wall,error=execute(cmd,args.timeout,cpu,root,
                    args.ips_memory_mib if mode.startswith('two_') else None)
                job={'mode':mode,'pos':k,'wall_s':round(wall,4)}
                try:
                    if error:raise RuntimeError(error)
                    if rc!=0:raise RuntimeError('exit='+str(rc)+' '+err[-400:])
                    parsed=parse_run(mode,out,wall)
                    if not args.skip_expected_count and parsed['count'] != KNOWN_COUNT[d]:
                        raise ValueError(f'EXPECTED_COUNT_MISMATCH {d} {parsed["count"]} vs {KNOWN_COUNT[d]}')
                    parsed['peak_rss_kb']=match_one(r'BENCH_PEAK_RSS_KB=(\d+)',err,int)
                    if parsed['ms']<=0:raise ValueError('Nonpositive search duration')
                    job.update(parsed);job['status']='OK'
                except Exception as e:
                    job['status']='TIMEOUT' if error=='timeout' else 'ERROR'
                    job['details']=str(e)+' '+out[-300:]
                jobs.append(job)
                print('[RUN] %s %d/%d %s status=%s ms=%s' % (d,k,len(sequence),mode,job['status'],job.get('ms','NA')),flush=True)
                if job['status']!='OK':
                    failed_datasets[d]=f'mode={mode} exit={job.get("details","")[:180]}'
                write_checkpoint()
                if job['status']!='OK':
                    print('[PAUSE_GRAPH_AFTER_FIRST_FAILURE]',d,failed_datasets[d],flush=True)
                    break
            if d in failed_datasets:
                print('[GRAPH_FAILED_UNTRUSTED_BLOCK]',d,flush=True)
                break
            same=matching_outputs(jobs)
            validation='PASS all modes same count; within each framework same XOR/SUM' if same else 'FAIL output mismatch or mode failure; do not quote this block as confirmed'
            block.update(completed=True,validation=validation)
            if not same:
                failed_datasets[d] = validation
            write_checkpoint()
            print(f'[BLOCK_DONE] {d} block={b} {validation}',flush=True)
            if not same:
                break
    write_checkpoint()
    print('[DONE] consolidated report:',report,flush=True)
    print('[DONE] checkpoint:',cp,flush=True)
    incomplete = [d for d in requested if d in failed_datasets or len(data.get(d, [])) != args.runs]
    if incomplete:
        print('[INCOMPLETE_DATASETS]', ', '.join(incomplete), flush=True)
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())
