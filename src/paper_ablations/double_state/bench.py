#!/usr/bin/env python3
"""Resumable, strict-count, full-enumeration MBET / IPS P0 follow-up experiments.
Times are each algorithm's native search-region timing, not wall times.
For published MBET/MBETM a fingerprint is unavailable; do not claim identical
reporting contract with final Single. See README_CN.md.
"""
import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import resource
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

GRAPHS = ('youtube','actors','stackoverflow','bibsonomy','dblp','forum','ukwiki',
          'escorts','github','bkcrossing','twitter','imdb','amazon')
KNOWN = dict(youtube=1826587,actors=1075444,stackoverflow=3320824,
             bibsonomy=2507269,dblp=4899032,forum=16261,ukwiki=23772,
             escorts=49538,github=55346398,bkcrossing=54458953,
             twitter=5536526,imdb=5160061,amazon=7551358)
MODES = {
    'single': ('official_mbet','official_mbetm','new_st','new_et_tg'),
    'double': ('vector_st','compact_st','vector_et_tg','compact_et_tg'),
}
ANCHORS = {'single': ('official_mbet','new_st'), 'double': ('vector_st','compact_st')}
PROGRAM = 'MBE_NEW_P0_20261109_V1'
BRANCH_PAIRS = (('vector_st', 'compact_st'), ('vector_et_tg', 'compact_et_tg'))

def sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def parse(mode,out):
    def get(pattern,required=True):
        m=re.search(pattern,out,re.M)
        if not m and required:raise ValueError('Missing '+pattern+' in binary output:\n'+out[-1300:])
        return m.group(1) if m else None
    if mode in ('official_mbet','official_mbetm'):
        cnt=int(get(r'^\[Run-1\] cnt=(\d+)\s*,\s*time:'))
        # Original MBET reports its internal run timer; this deliberately
        # excludes its graph-loading and degree-ordering phases.
        sec=float(get(r'^\[Average\(1\)\] avg_run:\s*([\d.eE+-]+)\s*$'))
        return dict(count=cnt,ms=sec*1000,fp=None,
                    metric='MBET published run timer (graph sorting/order excluded)')
    if mode.startswith('new_'):
        cnt=int(get(r'^Count:\s*(\d+)\s*$'))
        ms=float(get(r'^Search_Time_ms:\s*([\d.eE+-]+)\s*$'))
        fp=(int(get(r'^Checksum_XOR:\s*(\d+)\s*$')),
            int(get(r'^Checksum_SUM:\s*(\d+)\s*$')))
        return dict(count=cnt,ms=ms,fp=fp,metric='MBET-Fast search timer')
    cnt=int(get(r'^Maximal_BiClique_Count:\s*(\d+)\s*,\s*Time:'))
    ms=float(get(r'^Maximal_BiClique_Count:\s*\d+\s*,\s*Time:\s*([\d.eE+-]+)\s*ms'))
    fp=(int(get(r'^Enumeration_Set_XOR:\s*(\d+)\s*$')),
        int(get(r'^Enumeration_Set_SUM:\s*(\d+)\s*$')))
    et=get(r'^ET:\s*(on|off)\s*$')
    tg=get(r'^TG:\s*(on|off)\s*$')
    expected_et='on' if mode.endswith('et_tg') else 'off'
    if et!=expected_et or tg!=expected_et:
        raise ValueError(f'Unexpected ET/TG mode {mode}: et={et} tg={tg}')
    if int(get(r'^Branch_Calls:\s*(\d+)\s*$')) < 1:
        raise ValueError('No branch calls')
    return dict(count=cnt,ms=ms,fp=fp,metric='IPS explicit-enumeration search timer',
                branches=int(get(r'^Branch_Calls:\s*(\d+)\s*$')),
                leaves=int(get(r'^Leaf_Calls:\s*(\d+)\s*$')),
                et_used=int(get(r'^ET_Used / TT =\s*(\d+)')),
                et_output=int(get(r'^ET_Output_Count:\s*(\d+)')))

def preexec(cpu,memory_mib):
    def setlimits():
        if cpu is not None:os.sched_setaffinity(0,{cpu})
        mem=memory_mib*1024*1024
        resource.setrlimit(resource.RLIMIT_AS,(mem,mem))
    return setlimits

def execute(cmd,cpu,timeout,memory_mib):
    timed=['/usr/bin/time','-f','MBE_PEAK_RSS_KB=%M']+cmd if Path('/usr/bin/time').exists() else cmd
    start=time.monotonic()
    try:
        p=subprocess.run(timed,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         encoding='utf-8',errors='replace',timeout=timeout,
                         preexec_fn=preexec(cpu,memory_mib))
        wall=round(time.monotonic()-start,4)
        if p.returncode:raise RuntimeError('exit=%d stderr=%s stdout=%s'%(p.returncode,p.stderr[-900:],p.stdout[-600:]))
        return p.stdout,p.stderr,wall
    except subprocess.TimeoutExpired as e:
        raise RuntimeError('timeout after %ss; %s'%(timeout,str(e)))

def anchor_at(jobs,mode,pos):
    hits=[(i,j['ms']) for i,j in enumerate(jobs) if j['mode']==mode and j['status']=='OK']
    if len(hits)!=2:return None
    (i,a),(k,b)=hits
    return a+(b-a)*(pos-i)/(k-i)


def block_sequence(kind, seed):
    anchors = ANCHORS[kind]
    middle = [mode for mode in MODES[kind] if mode not in anchors]
    random.Random(seed).shuffle(middle)
    return [*anchors, *middle, *reversed(anchors)]


def block_problem(jobs, kind, reference_count):
    anchors = ANCHORS[kind]
    modes = tuple(job['mode'] for job in jobs)
    middle = Counter(mode for mode in MODES[kind] if mode not in anchors)
    if modes[:2] != anchors or modes[-2:] != anchors[::-1] or Counter(modes[2:-2]) != middle:
        return 'incomplete or invalid mode order'
    if any(job['status'] != 'OK' for job in jobs):
        return 'unsuccessful native run'
    if any(not math.isfinite(job['ms']) or job['ms'] <= 0 for job in jobs):
        return 'invalid search time'
    counts = {job['count'] for job in jobs}
    if len(counts) != 1 or (reference_count is not None and counts != {reference_count}):
        return 'count mismatch'
    fingerprinted = [job['fp'] for job in jobs if kind == 'double' or job['mode'].startswith('new_')]
    if any(fp is None or len(fp) != 2 for fp in fingerprinted) or len({tuple(fp) for fp in fingerprinted}) != 1:
        return 'fingerprint mismatch'
    if kind == 'double':
        for first, second in BRANCH_PAIRS:
            calls = {job.get('branches') for job in jobs if job['mode'] in (first, second)}
            if len(calls) != 1 or not all(type(count) is int and count > 0 for count in calls):
                return f'branch counts disagree or are missing for {first}/{second}'
        if any(type(job.get('rss_kb')) is not int or job['rss_kb'] <= 0
               for job in jobs if job['mode'] in anchors):
            return 'missing or invalid ST peak RSS'
        if any(not math.isfinite(job['wall_s']) or job['wall_s'] <= 0 for job in jobs):
            return 'invalid whole-process time'
    return None


def validated(block, kind, reference_count):
    return (block.get('completed') is True and block.get('validation', '').startswith('PASS')
            and block_problem(block['jobs'], kind, reference_count) is None)


def recover_blocks(blocks, kind, seeds, reference_count):
    retained = {}
    for block in blocks:
        if not validated(block, kind, reference_count):
            continue
        seed = block['seed']
        if seed not in seeds or seed in retained:
            raise ValueError(f'Unexpected or repeated validated block seed {seed}')
        retained[seed] = block
    return retained


def write_outputs(meta,blocks,failed,cp,report):
    with TemporaryDirectory(dir=cp.parent) as folder:
        pending = Path(folder) / cp.name
        with pending.open('w', encoding='utf-8') as stream:
            json.dump(dict(meta=meta, blocks=blocks, failed_datasets=failed), stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(cp)
    modes=MODES[meta['kind']];anchors=ANCHORS[meta['kind']]
    lines=[f'# {PROGRAM} / {meta["kind"]}',
           '# Native internal search times; full counts, hashes only where implementation supports them',
           '[META] '+json.dumps(meta,sort_keys=True),
           '[FAILED_DATASETS] '+json.dumps(failed,sort_keys=True)]
    cross={}
    pairs = ([('new_st','official_mbet'),('new_st','official_mbetm'),
              ('new_et_tg','official_mbet'),('new_et_tg','new_st')]
             if meta['kind']=='single' else
             [('compact_st','vector_st'),('compact_et_tg','vector_et_tg'),
              ('vector_et_tg','vector_st'),('compact_et_tg','compact_st')])
    done=[]
    for name in meta['datasets']:
        bs=blocks.get(name,[])
        reference_count = KNOWN[name] if meta['expected_count_check'] else None
        verified = [b for b in bs if validated(b, meta['kind'], reference_count)]
        if len(verified) == len(bs) == meta['runs']:done.append(name)
        lines.append(f'\n[DATASET] {name} validated_blocks={len(verified)}/{meta["runs"]}')
        ratios={(n,d):[] for n,d in pairs}
        for b in bs:
            if b.get('completed') is not True:continue
            js=b['jobs']
            for j in js:
                lines.append('[RUN] %s status=%s ms=%s count=%s wall_s=%s rss_kb=%s branches=%s et_used=%s'%(
                    j['mode'],j['status'],j.get('ms'),j.get('count'),j.get('wall_s'),j.get('rss_kb'),j.get('branches'),j.get('et_used')))
            verdict = b.get('validation','')
            if verdict.startswith('PASS') and b not in verified:
                verdict = 'FAIL ' + block_problem(js, meta['kind'], reference_count)
            lines.append('[CORRECTNESS] '+verdict)
            if b not in verified:continue
            for n,d in pairs:
                n_values=[(i,j['ms']) for i,j in enumerate(js) if j['mode']==n and j['status']=='OK']
                if not n_values:continue
                i,n_time=n_values[0]
                d_time=anchor_at(js,d,i) if d in anchors else next((j['ms'] for j in js if j['mode']==d and j['status']=='OK'),None)
                # For comparing two anchors, take center-of-block times for both.
                if n in anchors and d in anchors:
                    i=(len(js)-1)/2
                    n_time=anchor_at(js,n,i)
                    d_time=anchor_at(js,d,i)
                elif n in anchors and d not in anchors:
                    d_pos=next((p for p,j in enumerate(js) if j['mode']==d and j['status']=='OK'),None)
                    if d_pos is not None:n_time=anchor_at(js,n,d_pos)
                if d_time is not None and n_time is not None and d_time>0 and n_time>0:
                    ratios[(n,d)].append(d_time/n_time)
        for (n,d),v in ratios.items():
            if len(v)==meta['runs']:cross.setdefault((n,d),{})[name]=statistics.median(v)
            lines.append('[PAIRED] %s_vs_%s %d/%d median_speedup=%s ratios=%s'%(
                n,d,len(v),meta['runs'],
                '%.6fx'%statistics.median(v) if v else 'N/A',
                ','.join('%.5f'%x for x in v)))
    lines.append('\n[VALIDATED_COMPLETE_DATASETS] '+', '.join(done))
    lines.append('[NOT_COMPLETE] '+', '.join(g for g in meta['datasets'] if g not in done))
    for k,vs in cross.items():
        if len(vs)==len(meta['datasets']) and len(done)==len(meta['datasets']):
            gm=math.exp(sum(math.log(x) for x in vs.values())/len(vs))
            lines.append('[GM_COMPLETE] %s_vs_%s datasets=%d gm=%.6fx'%(k[0],k[1],len(vs),gm))
        else:
            lines.append('[GM_INCOMPLETE] %s_vs_%s covered=%d/%d'%(k[0],k[1],len(vs),len(meta['datasets'])))
    tmp=report.with_suffix('.txt.tmp');tmp.write_text('\n'.join(lines)+'\n',encoding='utf-8');tmp.replace(report)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--kind',choices=['single','double'],required=True)
    ap.add_argument('--runs',type=int,default=5)
    ap.add_argument('--timeout',type=int,default=1200)
    ap.add_argument('--cpu',default='auto')
    ap.add_argument('--ips-memory-mib',type=int,default=6144)
    ap.add_argument('--process-only',nargs='+',default=None)
    ap.add_argument('--skip-build',action='store_true')
    ap.add_argument('--fresh',action='store_true')
    ap.add_argument('--retry-failed',action='store_true')
    ap.add_argument('--skip-expected-count',action='store_true',help='For synthetic smoke only; never use for paper')
    args=ap.parse_args()
    if args.runs<1 or args.timeout<1 or args.ips_memory_mib<1024:ap.error('bad runs/timeout/memory')
    if args.process_only and not set(args.process_only)<=set(GRAPHS):ap.error('unknown --process-only')
    if args.kind == 'double' and not Path('/usr/bin/time').is_file():
        ap.error('Table V requires GNU time at /usr/bin/time to record ST peak RSS')
    here=Path(__file__).resolve().parent;root=args.root.resolve()
    corrected=root/'MBE_CORRECTED_13DATA';suite=root/'MBE_FAST_FOUR_MODES';data=root/'data_clean'
    if not (corrected/'prepare_corrected.py').exists() or not (suite/'run.sh').exists():
        ap.error('Missing corrected preprocessing or original one-core run.sh under '+str(root))
    sys.path.insert(0,str(corrected))
    from prepare_corrected import prepare_corrected
    if not args.skip_build:subprocess.run(['bash',str(here/'build.sh')],check=True)
    bins={'official_mbet':here/'bin/official_mbet','official_mbetm':here/'bin/official_mbetm',
          'new_st':suite/'bin/one_core','new_et_tg':suite/'bin/one_core',
          'vector_st':here/'bin/double_vector_st','compact_st':here/'bin/double_compact_st',
          'vector_et_tg':here/'bin/double_vector_et_tg','compact_et_tg':here/'bin/double_compact_et_tg'}
    modes=MODES[args.kind]
    for name in modes:
        if not bins[name].exists():ap.error(f'Missing binary {bins[name]}; run without --skip-build')
    if args.cpu=='auto':cpu=min(os.sched_getaffinity(0))
    elif args.cpu=='none':cpu=None
    else:
        cpu=int(args.cpu)
        if cpu not in os.sched_getaffinity(0):ap.error('CPU not in affinity list')
    pchecks={n:sha256(bins[n].resolve()) for n in modes}
    samples={g:dict(sha256=sha256(data/(g+'.txt')) if (data/(g+'.txt')).is_file() else None) for g in GRAPHS}
    meta=dict(program=PROGRAM,kind=args.kind,runs=args.runs,timeout=args.timeout,
              cpu=cpu,memory_mib=args.ips_memory_mib,expected_count_check=not args.skip_expected_count,
              datasets=list(GRAPHS),binaries=pchecks,inputs=samples,
              preprocessing='verified 3-int header removed for MBET; retained for IPS',
              source='2024 author original MBET and corrected explicit-enumeration IPS',
              created=dt.datetime.now(dt.timezone.utc).isoformat())
    diag=here/'diagnostics';diag.mkdir(exist_ok=True)
    cp=diag/f'P0_{args.kind.upper()}_CHECKPOINT.json'
    report=diag/f'P0_{args.kind.upper()}_REPORT.txt'
    if cp.exists() and not args.fresh:
        old=json.loads(cp.read_text());pm=old['meta'].copy();cm=meta.copy();pm.pop('created',None);cm.pop('created',None)
        if pm!=cm:ap.error('Existing checkpoint disagrees with binaries/config/inputs. Do NOT force resume; examine changes or use --fresh after backing up checkpoint.')
        meta=old['meta']; blocks=old['blocks'];failed=old['failed_datasets'];print('[RESUME] checkpoint present',flush=True)
    else:blocks={};failed={}
    def save():write_outputs(meta,blocks,failed,cp,report)
    requested = [graph for graph in GRAPHS if not args.process_only or graph in args.process_only]
    for idx,g in enumerate(GRAPHS):
        if args.process_only and g not in args.process_only:continue
        if failed.get(g) and not args.retry_failed:
            print('[SKIP_FAILED]',g,failed[g],flush=True);continue
        reference_count = KNOWN[g] if not args.skip_expected_count else None
        seeds = [2602026 + (idx+1)*100003 + (block+1)*9176 for block in range(args.runs)]
        existing = blocks.get(g, [])
        retained = recover_blocks(existing, args.kind, seeds, reference_count)
        if len(retained) != len(existing):
            print('[RESET_UNTRUSTED_BLOCKS]', g, len(existing)-len(retained), flush=True)
        bb = blocks[g] = [retained[seed] for seed in seeds if seed in retained]
        failed.pop(g,None)
        if len(retained) == args.runs:
            print('[RESUME_GRAPH]', g, len(retained), 'validated blocks retained', flush=True)
            continue
        raw=data/(g+'.txt')
        if not raw.is_file():print('[MISSING_GRAPH]',raw,flush=True);continue
        one=corrected/'.cache'/(g+'.one.txt')
        two=corrected/'.cache'/(g+'.two.clean')
        try:
            prepare_corrected(raw,one,two,corrected/'.cache'/(g+'.meta.json'))
        except Exception as e:
            failed[g]='PREPARE_FAILED '+repr(e);save();continue
        for k, seed in enumerate(seeds, 1):
            if seed in retained:
                print('[RESUME_BLOCK]',g,k,flush=True)
                continue
            seq=block_sequence(args.kind, seed)
            print('[BLOCK_START]',args.kind,g,k,'/',args.runs,'sequence='+','.join(seq),flush=True)
            jobs=[]
            block = dict(seed=seed, jobs=jobs, completed=False)
            bb.append(block)
            bb.sort(key=lambda item: item['seed'])
            for mode in seq:
                if mode.startswith('official_'):
                    cmd=[str(bins[mode]),str(one),'1']
                elif mode.startswith('new_'):
                    cmd=['bash',str(suite/'run.sh'),'one_st' if mode=='new_st' else 'one_et_tg',str(one)]
                else:
                    cmd=[str(bins[mode]),'-f',str(two),'-d','two']
                job=dict(mode=mode)
                try:
                    out,err,wall=execute(cmd,cpu,args.timeout,args.ips_memory_mib)
                    job.update(parse(mode,out))
                    m=re.search(r'MBE_PEAK_RSS_KB=(\d+)',err)
                    job['rss_kb']=int(m.group(1)) if m else None
                    job['wall_s']=wall
                    if args.kind == 'double' and mode in ANCHORS['double'] and not job['rss_kb']:
                        raise RuntimeError('Missing or invalid ST peak RSS')
                    if not math.isfinite(job['ms']) or job['ms']<=0:raise RuntimeError('Invalid native search duration')
                    if not args.skip_expected_count and job['count']!=KNOWN[g]:
                        raise RuntimeError('INCORRECT_COUNT: got %d expected %d'%(job['count'],KNOWN[g]))
                    job['status']='OK'
                except Exception as e:
                    job['status']='FAIL';job['details']=str(e)[-1600:]
                    failed[g]=f'{mode}: {str(e)[-350:]}'
                jobs.append(job);save()
                print('[RUN]',mode,'status='+job['status'],'ms='+str(job.get('ms')),'count='+str(job.get('count')),flush=True)
                if job['status']!='OK':
                    print('[STOP_GRAPH_ON_FAILURE]',g,failed[g],flush=True);break
            if g in failed:
                save();break
            problem = block_problem(jobs, args.kind, reference_count)
            if problem:
                block.update(completed=True, validation=f'FAIL {problem}')
                failed[g] = problem
                save()
                print('[BLOCK_FAILED]',args.kind,g,k,problem,flush=True)
                break
            block.update(completed=True,validation='PASS output and measurement controls')
            save();print('[BLOCK_DONE]',args.kind,g,k,'PASS',flush=True)
    save()
    print('[REPORT]',report,flush=True)
    print('[CHECKPOINT]',cp,flush=True)
    if failed:print('[WARN] failures recorded:',failed,flush=True)
    incomplete = [name for name in requested if name in failed or len(blocks.get(name, [])) != args.runs]
    if incomplete:
        print('[INCOMPLETE_DATASETS]', ', '.join(incomplete), flush=True)
        return 1
    return 0

if __name__=='__main__':sys.exit(main())
