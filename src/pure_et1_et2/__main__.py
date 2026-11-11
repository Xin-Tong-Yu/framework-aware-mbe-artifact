#!/usr/bin/env python3
"""Self-running ZIP app for the matched degree-two MBE experiments.

Usage: python3 MBE_1V2_BIPLEX_ET_PROFILER.zip help|modes|build|run|all|youtube|selftest
Native sources are extracted and compiled into a versioned *automatic cache*;
the user does not have to unzip the distribution.
"""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile


# Pure degree-one/degree-two experiment notes:
# 1) The Single --kappa 2 controls the common V59 dispatch path, whereas
#    --v59-dispatch 2 / 3 selects ONLY the matching or degree-two MIS solver.
#    No mask closure is selected (v56-terminal=0).
# 2) Single TG1 uses the existing matching prefix BuildTGPrefixPlan; TG2 uses
#    BuildTG2PrefixPlan. They are excluded from --modes pure.
# 3) No other compiler switches differ between Single et1/et2; the Double
#    modes use identical Compact state, adjacency and classic pivot.

# Explicitly named modes ensure that comparisons cannot silently change other factors.
SINGLE_DEFAULT = dict(layout='inline', cursor=True, result='inline', cr=False,
                      et=False, tg=False, prefork=False)
DOUBLE_DEFAULT = dict(state='compact', adjacency='ordinary', et=False, tg=False)
MODES = {}

def single(name, **kw):
    d=SINGLE_DEFAULT.copy(); d.update(kw); MODES[name]=('single', d)
def double(name, **kw):
    d=DOUBLE_DEFAULT.copy(); d.update(kw); MODES[name]=('double', d)

# Candidate-tree cumulative ablation. Pre-fork is held off in the ST vs ET/TG study.
single('single_map',layout='map',cursor=False)
single('single_inline',cursor=False)
single('single_st')
single('single_st_prefork',prefork=True)
# Independent Result Tree x CR factorial (four cells, fixed Candidate Tree/cursor).
single('single_result_flat',result='flat')
single('single_result_flat_cr',result='flat',cr=True)
single('single_result_inline_cr',cr=True)
# Matched one-sided degree-one controls (same ST, ownership and reporting).
# Exclusive V59 selector 2 invokes matching-only on the auxiliary path-column graph.
single('single_et1',et=True,biplex_threshold=1)
single('single_et1_tg1',et=True,tg=True,biplex_threshold=1)
# ET2 and TG2 incremental ablation, same optimized ST and reporting (CR off).
single('single_et2',et=True)
single('single_et2_tg2',et=True,tg=True)
single('single_et2_tg2_prefork',et=True,tg=True,prefork=True)
# Exact TG2 path-admission optimization: stack-allocated 0..2 misses.
single('single_et2_tg2_fast',et=True,tg=True,tgfast=True)
# Optional, separately controlled nonmatching-only prefix gate.
single('single_et2_tg2_selective',et=True,tg=True,tgfast=True,tgselect=True)
# Larger conservative minimum search-family gates: optional YouTube study.
single('single_et2_tg2_guard32',et=True,tg=True,tgfast=True,tgfamily=32)
single('single_et2_tg2_guard48',et=True,tg=True,tgfast=True,tgfamily=48)
# ET2 x CR for reporting separation; not mixed into the core ET/TG table.
single('single_et2_cr',et=True,cr=True)
single('single_et2_tg2_cr',et=True,tg=True,cr=True)
# Test whether ET2 itself works when candidate layout is not inlined.
single('single_map_et2',layout='map',cursor=False,et=True)
# Double vector/compact state x (ST, ET2, ET2+TG2) ablations.
for state in ('vector','compact'):
    for tag,flags in [('st',{}),('et2',{'et':True}),('et2_tg2',{'et':True,'tg':True})]:
        double('double_'+state+'_'+tag,state=state,**flags)
# Same IPS branch-ownership rule and pivots, but prefilter the true degree>2
# obstruction vertices instead of rescanning every opposite candidate.
# Bounded degree-two obstruction-aware pivot selection (new experiment).
double('double_compact_et2_tg2_tie',state='compact',et=True,tg=True,tgscore='tie')
double('double_compact_et2_tg2_near',state='compact',et=True,tg=True,tgscore='near')
double('double_compact_hybrid_et2_tg2_tie',state='compact',adjacency='hybrid',et=True,tg=True,tgscore='tie')
double('double_compact_hybrid_et2_tg2_near',state='compact',adjacency='hybrid',et=True,tg=True,tgscore='near')
double('double_compact_et2_tg2_cached',state='compact',et=True,tg=True,tgcache=True)
double('double_compact_et2_tg2_cached_lite',state='compact',et=True,tg=True,tgcache=True,tglite=True)
double('double_compact_et2_tg2_tie_x0',state='compact',et=True,tg=True,tgscore='tie',tgx0=True)
double('double_compact_et2_tg2_near_x0',state='compact',et=True,tg=True,tgscore='near',tgx0=True)
double('double_compact_et2_tg2_fast',state='compact',et=True,tg=True,tgfast=True)
double('double_compact_hybrid_et2_tg2_fast',state='compact',adjacency='hybrid',et=True,tg=True,tgfast=True)
# ET2-scratch reuse: unchanged path/cycle MIS and pivot, fewer allocations.
double('double_compact_et2_tg2_reuse',state='compact',et=True,tg=True,etreuse=True)
double('double_compact_et2_reuse',state='compact',et=True,etreuse=True)
double('double_compact_hybrid_et2_tg2_reuse',state='compact',adjacency='hybrid',et=True,tg=True,etreuse=True)
# Degree-two terminal remains general; specialize the frequent matching components.
double('double_compact_et2_tg2_matchfast',state='compact',et=True,tg=True,matchfast=True)
double('double_compact_et2_matchfast',state='compact',et=True,matchfast=True)
double('double_compact_hybrid_et2_tg2_matchfast',state='compact',adjacency='hybrid',et=True,tg=True,matchfast=True)
# Additional independent adjacency ablation, ST/ET/TG otherwise unchanged.
for tag,flags in [('st',{}),('et2',{'et':True}),('et2_tg2',{'et':True,'tg':True})]:
    double('double_compact_hybrid_'+tag,adjacency='hybrid',**flags)

# Matched threshold comparison: same candidate representation, search engine,
# output callback, and compiler. 1-biplex optionally uses the direct matching
# specialization; degree-two uses the general path/cycle terminal.
double('double_compact_et1',state='compact',et=True,tg=False,targetdegree=1,matchfast=True)
double('double_compact_et1_tg1',state='compact',et=True,tg=True,targetdegree=1,matchfast=True)
double('double_compact_et1_tg1_generic',state='compact',et=True,tg=True,targetdegree=1)
double('double_compact_et1_tg1_profile',state='compact',et=True,tg=True,targetdegree=1,matchfast=True,profile=True)
double('double_compact_et2_tg2_profile',state='compact',et=True,tg=True,targetdegree=2,profile=True)
double('double_compact_et2_tg2_pattern',state='compact',et=True,tg=True,targetdegree=2,pattern=True)
double('double_compact_et2_tg2_pattern_profile',state='compact',et=True,tg=True,targetdegree=2,pattern=True,profile=True)

# Strict terminal-threshold study: no TG, CR, Pattern, or other varying factors.
# Single and Double must be analyzed separately (different auxiliary/graph states).
PURE_1V2_MATRIX=['single_st','single_et1','single_et2',
                 'double_compact_st','double_compact_et1','double_compact_et2']
PURE_1_MATRIX=['single_st','single_et1','double_compact_st','double_compact_et1']
PURE_2_MATRIX=['single_st','single_et2','double_compact_st','double_compact_et2']
# Independent guidance-inclusive study, not a pure biplex threshold ablation.
GUIDED_1V2_MATRIX=['single_st','single_et1','single_et1_tg1',
                   'single_et2','single_et2_tg2',
                   'double_compact_st','double_compact_et1','double_compact_et1_tg1',
                   'double_compact_et2','double_compact_et2_tg2']

BIPLEX_COMPARE_MATRIX=[
    'double_compact_st',
    'double_compact_et1','double_compact_et1_tg1',
    'double_compact_et2','double_compact_et2_tg2',
    'double_compact_et2_tg2_pattern'
]
BIPLEX_PROFILE_MATRIX=[
    'double_compact_et1_tg1_profile',
    'double_compact_et2_tg2_profile',
    'double_compact_et2_tg2_pattern_profile'
]

PIVOT_MATRIX=['double_compact_et2','double_compact_et2_tg2',
              'double_compact_et2_tg2_tie','double_compact_et2_tg2_near',
              'double_compact_et2_tg2_tie_x0','double_compact_et2_tg2_near_x0',
              'double_compact_hybrid_et2_tg2','double_compact_hybrid_et2_tg2_tie',
              'double_compact_hybrid_et2_tg2_near']
BUILD_PROFILE=os.environ.get('MBE2_OPT','O3')

# Keep the 22 modes from the original release as a stable baseline.
MAIN_MATRIX = [
    'single_map','single_inline','single_st','single_st_prefork',
    'single_result_flat','single_result_flat_cr','single_result_inline_cr',
    'single_et2','single_et2_tg2','single_et2_tg2_prefork',
    'single_et2_cr','single_et2_tg2_cr','single_map_et2',
    'double_vector_st','double_compact_st',
    'double_vector_et2','double_compact_et2',
    'double_vector_et2_tg2','double_compact_et2_tg2',
    'double_compact_hybrid_st','double_compact_hybrid_et2',
    'double_compact_hybrid_et2_tg2'
]
SMOKE_MODES = [
    'single_map','single_st','single_et2','single_et2_tg2','single_st_prefork',
    'single_result_flat_cr','single_result_inline_cr',
    'double_vector_st','double_compact_st',
    'double_vector_et2','double_compact_et2',
    'double_vector_et2_tg2','double_compact_et2_tg2',
    'double_compact_hybrid_et2_tg2'
]
# Side-by-side comparison of the original degree-two controllers with optional
# conservative optimizations. The experimental modes are NOT assumed faster.
OPT_MATRIX = [
    'single_et2','single_et2_tg2','single_et2_tg2_fast',
    'single_et2_tg2_selective','single_et2_tg2_guard32',
    'double_compact_et2','double_compact_et2_tg2',
    'double_compact_et2_tg2_fast','double_compact_et2_tg2_reuse',
    'double_compact_et2_tg2_matchfast',
    'double_compact_hybrid_et2_tg2'
]
# Faster end-to-end example that does not automatically compile every mode.
YOUTUBE_MATRIX = [
    'single_st','single_et2','single_et2_tg2','single_et2_tg2_fast',
    'double_compact_st','double_compact_et2',
    'double_compact_et2_tg2','double_compact_hybrid_et2_tg2'
]

def die(msg):
    raise SystemExit('[ERROR] '+str(msg))

def root_cache():
    path=Path(os.environ.get('MBE2_CACHE',str(Path.home()/'.cache'/'mbe_pure_2biplex'))).expanduser()
    archive=Path(sys.argv[0]).resolve()
    if not zipfile.is_zipfile(archive):
        die('Use the ZIP directly: python3 MBE_1V2_BIPLEX_ET_PROFILER.zip ...')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()[:16]
    return path/digest,archive

def install(cache,archive):
    marker=cache/'engine'/'two'/'ips.hpp'
    if marker.is_file() and (cache/'engine'/'one'/'src'/'MBET.hpp').is_file():
        return
    cache.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if not info.filename.startswith('engine/') or info.is_dir():continue
            relative=Path(info.filename)
            if '..' in relative.parts:die('Unsafe ZIP entry')
            target=cache/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as src,target.open('wb') as dst: shutil.copyfileobj(src,dst)

def single_flags(d):
    flags=['-DMBE_ET_STREAM=1', '-DMBE_V32_CANDIDATE_POOL=1',
           '-DMBE_V32_RESULT_POOL=1','-DMBE_V40_FLAT_RESULT=1',
           '-DMBE_V52_INLINE_FORK_SCRATCH=1']
    if d['layout']=='inline': flags+=['-DMBE_V63_INLINE_CANDIDATE=1']
    if d['cursor']: flags+=['-DMBE_V30_SKIP_EMPTY_PREV=1']
    if d['result']=='inline': flags+=['-DMBE_V42_INLINE_RESULT=1']
    if d['cr']:flags+=['-DMBE_V42_FAST_REPORT=1']
    if d.get('tgfast'):flags+=['-DMBE_TG2_STACK_MISSES=1']
    return flags

def double_flags(d):
    flags=['-fopenmp']
    if d['state']=='compact': flags+=['-DIPS_ST_V24_SINGLE_DEFECT=1']
    if d['adjacency']=='hybrid':
        flags+=['-DIPS_ST_V15_HASHLESS=1','-DIPS_ST_V15_ROW_CACHE=1']
    if not d['et']: flags+=['-DIPS_DISABLE_ET=1']
    if not d['tg']: flags+=['-DIPS_CLASSIC_PIVOT=1']
    if d.get('tgfast'): flags+=['-DIPS_TG2_FAST_OBSTRUCTION=1']
    if d.get('tgcache'): flags+=['-DIPS_TG2_CACHED_MISSING=1']
    if d.get('tglite'): flags+=['-DIPS_TG2_CACHED_ID_TRUSTED=1']
    if d.get('tgscore')=='tie': flags+=['-DIPS_TG2_OBSTRUCTION_TIE=1']
    if d.get('tgscore')=='near': flags+=['-DIPS_TG2_OBSTRUCTION_NEAR=1']
    if d.get('tgx0'): flags+=['-DIPS_TG2_SCORE_ONLY_EMPTY_X=1']
    if d.get('etreuse'): flags+=['-DIPS_ET2_SCRATCH_REUSE=1']
    if d.get('matchfast'): flags+=['-DIPS_ET2_FAST_MATCHING_COMPONENTS=1']
    if d.get('targetdegree',2)!=2: flags+=['-DIPS_ET_TARGET_DEGREE='+str(d['targetdegree'])]
    if d.get('profile'): flags+=['-DIPS_ET_PROFILE=1']
    if d.get('pattern'): flags+=['-DIPS_ET2_PATTERN_CACHE=1']
    return flags

def build(mode,cache,archive,quiet=False):
    if mode not in MODES: die('Unknown mode: '+mode)
    install(cache,archive)
    kind,d=MODES[mode]
    src=cache/'engine'/('one' if kind=='single' else 'two')
    flags=single_flags(d) if kind=='single' else double_flags(d)
    # Different ET/TG switches in single are runtime switches, so binaries
    # are keyed by actual compiler arguments, not by name or description.
    sig=hashlib.sha256((str(src)+repr(flags)+kind+BUILD_PROFILE).encode()).hexdigest()[:14]
    exe=cache/'bin'/('one_' if kind=='single' else 'two_')
    exe=exe.with_name(exe.name+sig)
    if exe.is_file():return exe
    exe.parent.mkdir(parents=True,exist_ok=True)
    compiler=os.environ.get('CXX','g++')
    if shutil.which(compiler) is None:die('g++ not available. Run in WSL2/Linux with GCC 12+ and Python 3.9+.')
    cmd=[compiler,'-'+BUILD_PROFILE,'-std=c++17','-UNDEBUG','-I',str(src),*flags,str(src/'main.cpp'),'-o',str(exe)]
    if not quiet:print('[BUILD]',mode,flush=True)
    r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if r.returncode:die('Compilation failed for '+mode+'\n'+r.stderr[-5000:])
    return exe

def graph_variants(graph,cache):
    graph=Path(graph).resolve()
    if not graph.is_file():die('Graph not found: '+str(graph))
    key=hashlib.sha256((str(graph)+str(graph.stat().st_size)+str(graph.stat().st_mtime_ns)).encode()).hexdigest()[:16]
    directory=cache/'graphs'/key
    directory.mkdir(parents=True,exist_ok=True)
    single=directory/'graph.edges'
    double=directory/'graph.clean'
    if single.is_file() and double.is_file():return single,double
    # Auto-detect a canonical three-integer clean header (only first line).
    # The supplied two-side .clean format is expected to be 0-based.
    with graph.open(encoding='utf8') as f:
        first=f.readline().split()
    header=(len(first)==3 and all(re.fullmatch(r'\d+',v) for v in first))
    if header:
        with graph.open(encoding='utf8') as inp, single.open('w',encoding='utf8') as out:
            next(inp)
            shutil.copyfileobj(inp,out)
        shutil.copyfile(graph,double)
    else:
        left={};right={}; edges=set()
        with graph.open(encoding='utf8') as inp:
            for line_no,line in enumerate(inp,1):
                line=line.strip()
                if not line or line[0] in '#%':continue
                parts=line.split()
                if len(parts)!=2:die('Expected two-column edges at line '+str(line_no))
                a,b=parts
                if a not in left:left[a]=len(left)
                if b not in right:right[b]=len(right)
                edges.add((left[a],right[b]))
        if not edges:die('No edges detected')
        shutil.copyfile(graph,single)
        with double.open('w',encoding='utf8') as o:
            o.write(f'{len(left)} {len(right)} {len(edges)}\n')
            for a,b in sorted(edges):o.write(f'{a} {b}\n')
    return single,double

def parse_stats(kind,stdout):
    def pick(pattern):
        m=re.search(pattern,stdout,re.MULTILINE)
        return m.group(1) if m else ''
    if kind=='single':
        sec=pick(r'^\[TIME\] MBET::Run:\s*([\d.eE+-]+) sec')
        count=pick(r'^Count:\s*(\d+)')
        # V59 2 is the matching/ET1 path; 3 is the degree-two/ET2 path.
        # The native source reports both V59_ET1_Hits and V59_ET2_Hits.
        et_dispatch=pick(r'^V59_Dispatch:\s*(\d+)')
        if et_dispatch == '2':
            e_used=pick(r'^V59_ET1_Hits:\s*(\d+)')
            term='0'
            calls=pick(r'^V59_Selected_ET1:\s*(\d+)')
        else:
            e_used=pick(r'^ET2_Hits:\s*(\d+)')
            term=pick(r'^ET2_Nonmatching_Hits:\s*(\d+)')
            calls=pick(r'^V59_Selected_ET2:\s*(\d+)')
        fp=pick(r'^Checksum_XOR:\s*(\d+)')+'|'+pick(r'^Checksum_SUM:\s*(\d+)')
        rss=pick(r'^Peak_RSS_MiB:\s*([\d.]+)')
        return dict(time_s=sec,count=count,et_attempt=calls,et_hit=e_used,
                    et_degree2_hit=term,fingerprint=fp,rss_mib=rss,
                    branch_calls='',et_output_count='')
    ms=pick(r'Maximal_BiClique_Count:\s*(\d+), Time:\s*(\d+) ms')
    count=ms
    time_ms=pick(r'Maximal_BiClique_Count:\s*\d+, Time:\s*(\d+) ms')
    fine=pick(r'^Search_Time_s:\s*([\d.eE+-]+)')
    return dict(time_s=fine or (str(float(time_ms)/1000) if time_ms else ''),count=count,
                et_attempt=pick(r'^ET_Eligible / TT =\s*(\d+)'),
                et_hit=pick(r'^ET_Used / TT =\s*(\d+)'),
                et_degree2_hit=pick(r'^2Biplex_Degree2_Hits:\s*(\d+)'),
                fingerprint=pick(r'^Enumeration_Set_XOR:\s*(\d+)')+'|'+pick(r'^Enumeration_Set_SUM:\s*(\d+)'),
                rss_mib=pick(r'^\[MEMORY\] VmHWM:\s*([\d.]+)MB'),
                tg2_score_changes=pick(r'^TG2_Score_Changes:\s*(\d+)'),
                tg2_cache_used=pick(r'^TG2_Cache_Used:\s*(\d+)'),
                tg2_cache_fallback=pick(r'^TG2_Cache_Fallback:\s*(\d+)'),
                tg2_score_states=pick(r'^TG2_Score_States:\s*(\d+)'),
                branch_calls=pick(r'^Branch_Calls:\s*(\d+)'),
                et_output_count=pick(r'^ET_Output_Count:\s*(\d+)'),
                et_gate_ms=pick(r'^ET_Profiler_Gate_ms:\s*([\d.]+)'),
                et_setup_ms=pick(r'^ET_Profiler_Setup_ms:\s*([\d.]+)'),
                et_build_ms=pick(r'^ET_Profiler_Build_ms:\s*([\d.]+)'),
                et_decompose_ms=pick(r'^ET_Profiler_Decompose_ms:\s*([\d.]+)'),
                et_generate_ms=pick(r'^ET_Profiler_Generate_ms:\s*([\d.]+)'),
                et_gate_calls=pick(r'^ET_Profiler_Gate_Calls:\s*(\d+)'),
                et_terminal_calls=pick(r'^ET_Profiler_Terminal_Calls:\s*(\d+)'),
                et_candidate_sum=pick(r'^ET_Profiler_Total_Candidates:\s*(\d+)'),
                et_max_candidate=pick(r'^ET_Profiler_Max_Candidates:\s*(\d+)'),
                et_pattern_components=pick(r'^ET_Pattern_Components:\s*(\d+)'))

def command(mode,exe,single_path,double_path,min_left,min_right,emit_path=None):
    kind,d=MODES[mode]
    if kind=='single':
        cmd=[str(exe),'-f',str(single_path),'-l',str(min_left),'-r',str(min_right),
             '--orientation','left-upper','--st','on','--et','on' if d['et'] else 'off',
             '--tg','on' if d['tg'] else 'off','--kappa','2',
             '--v56-terminal','0','--v59-dispatch',('2' if d.get('biplex_threshold',2)==1 else '3') if d['et'] else '0',
             '--et-min-paths','2','--et-root-summary','on',
             '--et-cardinality-gate','on','--et2-root-degree-gate','on',
             '--et2-reuse-buffers','on','--et2-max-defects','30',
             '--et2-max-mis','4096', '--v59-et2-max-paths','64',
             '--v56-prefork','on' if d['prefork'] else 'off',
             '--tg2-prefix','on' if (d['tg'] and d.get('biplex_threshold',2)==2) else 'off',
             '--tg-prefix-min','4','--tg-prefix-cap','8',
             '--tg2-require-nonmatching','on' if d.get('tgselect') else 'off',
             '--tg-two-min-family','8','--tg-min-family',str(d.get('tgfamily',16)),
             '--tg-batch-mode','skip' if d['tg'] else 'off']
        if emit_path:cmd+=['--emit',str(emit_path)]
        return cmd
    cmd=[str(exe),'-f',str(double_path),'-d','two','-l',str(min_left),'-r',str(min_right)]
    if emit_path:cmd+=['-o',str(emit_path)]
    return cmd

def execute(mode,cache,archive,graph,min_left,min_right,timeout,emit_path=None,quiet=False,precomputed=None):
    exe=build(mode,cache,archive,quiet=quiet)
    paths=precomputed if precomputed is not None else graph_variants(graph,cache)
    cmd=command(mode,exe,*paths,min_left,min_right,emit_path)
    t=time.perf_counter()
    try:
        proc=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    except subprocess.TimeoutExpired:die(mode+' exceeded timeout '+str(timeout)+'s')
    elapsed=time.perf_counter()-t
    # Print small adjacency-allocation diagnostics even on successful runs.
    for diag_line in proc.stderr.splitlines():
        if diag_line.startswith('[GRAPH_STAGE]') or diag_line.startswith('[BITMAP_GUARD]'):
            print(diag_line,flush=True)
    if proc.returncode:die(mode+' returned '+str(proc.returncode)+'\n'+proc.stdout[-1500:]+'\n'+proc.stderr[-1500:])
    result=parse_stats(MODES[mode][0],proc.stdout)
    for field in ('et_gate_ms','et_setup_ms','et_build_ms','et_decompose_ms',
                  'et_generate_ms','et_gate_calls','et_terminal_calls',
                  'et_candidate_sum','et_max_candidate','et_pattern_components'):
        result.setdefault(field,'')
    result.setdefault('tg2_score_changes','')
    result.setdefault('tg2_cache_used','')
    result.setdefault('tg2_cache_fallback','')
    result.setdefault('tg2_score_states','')
    result.update(mode=mode,kind=MODES[mode][0],wall_s=elapsed,
                  graph=Path(graph).name,et=MODES[mode][1]['et'],tg=MODES[mode][1]['tg'])
    if not result['count']:die('Missing output count in '+mode+'\n'+proc.stdout[-2500:])
    return result,proc.stdout

def compare_result(out,expected,mode):
    # Full set equality; no hashes or counts used as substitute.
    def parse_set(line):
        if '|' in line and re.fullmatch(r'\s*\d+(?:\s+\d+)*\s*\|\s*\d+(?:\s+\d+)*\s*',line):
            left,right=line.split('|')
            xs=list(map(int,left.split())); ys=list(map(int,right.split()))
            assert xs[0]==len(xs)-1 and ys[0]==len(ys)-1
            return tuple(sorted(xs[1:])),tuple(sorted(ys[1:]))
        m=re.fullmatch(r'\[([\d, ]*)\]\[([\d, ]*)\]',line)
        if not m:return None
        return (tuple(sorted(int(x) for x in m[1].split(',') if x.strip())),
                tuple(sorted(int(x) for x in m[2].split(',') if x.strip())))
    lines=out.splitlines()
    parsed=[v for line in lines if (v:=parse_set(line)) is not None]
    if len(parsed)!=len(set(parsed)) or set(parsed)!=expected:
        missing=sorted(expected-set(parsed))[:4]
        extra=sorted(set(parsed)-expected)[:4]
        die(f'Oracle mismatch in {mode}: expected={len(expected)}, observed={len(parsed)}, '
            f'missing={missing}, extra={extra}, duplicates={len(parsed)-len(set(parsed))}')

def oracle(nl,nr,edges,ll,rr):
    results=set()
    for mask in range(1,1<<nl):
        l=tuple(i for i in range(nl) if mask>>i&1)
        r=tuple(j for j in range(nr) if all((i,j) in edges for i in l))
        if len(l)<ll or len(r)<rr:continue
        closed=tuple(i for i in range(nl) if all((i,j) in edges for j in r))
        if closed==l:results.add((l,r))
    return results

def selftest(args,cache,archive):
    global BUILD_PROFILE
    BUILD_PROFILE='O0'  # fast correctness builds; the benchmark defaults to O3
    rng=random.Random(args.seed)
    chosen=(args.modes.split(',') if args.modes else
            (list(MODES) if args.all_modes else SMOKE_MODES))
    for name in chosen:
        if name not in MODES: die('Unknown selftest mode: '+name)
    print('[SELFTEST] Building',len(chosen),'modes ...',flush=True)
    for mode in chosen:build(mode,cache,archive,quiet=True)
    total=0
    with tempfile.TemporaryDirectory() as temp:
        directory=Path(temp)
        for z in range(args.cases):
            nl=rng.randint(2,7);nr=rng.randint(2,7)
            p=[.1,.3,.52,.72,.94][z%5]
            edges={(i,j) for i in range(nl) for j in range(nr) if rng.random()<p}
            if z%7==0:
                nl=nr=rng.randint(4,7)
                edges={(i,j) for i in range(nl) for j in range(nr)
                       if j not in (i,(i+1)%nr)}
            if not edges:edges={(0,0)}
            ll,rr=rng.choice([(1,1),(1,2),(2,1),(2,2)])
            graph=directory/('test_%d.clean'%z)
            graph.write_text(f'{nl} {nr} {len(edges)}\n'+''.join(f'{i} {j}\n' for i,j in sorted(edges)))
            expected=oracle(nl,nr,edges,ll,rr)
            paths=graph_variants(graph,cache)
            for mode in chosen:
                if MODES[mode][0]=='single':
                    result,stdout=execute(mode,cache,archive,graph,ll,rr,args.timeout,
                                          emit_path='stdout',quiet=True,precomputed=paths)
                    source=stdout
                else:
                    output=directory/(mode+'.txt')
                    result,stdout=execute(mode,cache,archive,graph,ll,rr,args.timeout,
                                          emit_path=output,quiet=True,precomputed=paths)
                    source=output.read_text()
                compare_result(source,expected,mode)
                if int(result['count'])!=len(expected):die('Count mismatch')
                total+=1
            if (z+1)%10==0 or z+1==args.cases:
                print(f'[SELFTEST] {z+1}/{args.cases} graphs, {total} exact-set checks: PASS',flush=True)
    print(f'[PASS] {total} independent full-output set comparisons ({len(chosen)} modes)')

def all_matrix(args,cache,archive):
    if args.modes=='main':modes=MAIN_MATRIX
    elif args.modes=='smoke':modes=SMOKE_MODES
    elif args.modes=='opt':modes=OPT_MATRIX
    elif args.modes=='youtube':modes=YOUTUBE_MATRIX
    elif args.modes=='pivot':modes=PIVOT_MATRIX
    elif args.modes=='cache':modes=['double_compact_et2_tg2','double_compact_et2_tg2_cached','double_compact_et2_tg2_cached_lite']
    elif args.modes=='pure':modes=PURE_1V2_MATRIX
    elif args.modes=='pure1':modes=PURE_1_MATRIX
    elif args.modes=='pure2':modes=PURE_2_MATRIX
    elif args.modes=='guided':modes=GUIDED_1V2_MATRIX
    elif args.modes=='biplex':modes=BIPLEX_COMPARE_MATRIX
    elif args.modes=='pair':modes=['double_compact_et1_tg1','double_compact_et2_tg2']
    elif args.modes=='profile':modes=BIPLEX_PROFILE_MATRIX
    else:modes=args.modes.split(',')
    for m in modes:
        if m not in MODES:die('Unknown selected mode '+m)
    print(f'[MATRIX] {len(modes)} modes, {args.repeats} paired blocks; times exclude build/preprocess',flush=True)
    for m in modes:build(m,cache,archive,quiet=False)
    paths=graph_variants(args.graph,cache)
    rows=[]
    rng=random.Random(args.seed)
    for block in range(args.repeats):
        order=modes[:];rng.shuffle(order)
        block_counts=[]
        per_framework={}
        for mode in order:
            row,_=execute(mode,cache,archive,args.graph,args.min_left,args.min_right,args.timeout,
                          quiet=True,precomputed=paths)
            row['block']=block+1;rows.append(row)
            block_counts.append(row['count'])
            kind=row['kind'];fp=row['fingerprint']
            # Within a frame, checksums are controlled by CR flags; full per
            # result count must always agree across *all* 2-biplex variants.
            per_framework.setdefault((kind,MODES[mode][1].get('cr',False)),[]).append((mode,fp))
            print('[RUN]',block+1,mode,'search_s='+str(row['time_s']),
                  'count='+row['count'],'ET_hit='+row['et_hit'],flush=True)
        if len(set(block_counts))!=1:
            die('Output counts differ across the matrix in block '+str(block+1)+': '+str(block_counts))
        for group in per_framework.values():
            # Caution: any change in traversal ordering must still use
            # commutative fingerprints, which these two engines provide.
            vals={v for _,v in group}
            if len(vals)>1:
                die('Fingerprint mismatch in block '+str(block+1)+': '+str(group))
    out=Path(args.out).resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['graph','block','mode','kind','time_s','wall_s',
                      'count','et','tg','et_attempt','et_hit','et_degree2_hit','fingerprint','rss_mib','tg2_score_states','tg2_score_changes','tg2_cache_used','tg2_cache_fallback','branch_calls','et_output_count', 'et_gate_ms','et_setup_ms','et_build_ms', 'et_decompose_ms','et_generate_ms','et_gate_calls','et_terminal_calls','et_candidate_sum','et_max_candidate','et_pattern_components'])
        writer.writeheader();writer.writerows(rows)
    print('[CSV]',out)
    print('Mode\tmedian_search_s\tmedian_wall_s\tcount\tmedian_peak_RSS_MiB')
    for mode in modes:
        rr=[v for v in rows if v['mode']==mode]
        s=[float(v['time_s']) for v in rr if v['time_s']]
        print(mode,statistics.median(s) if s else 'NA',round(statistics.median(v['wall_s'] for v in rr),6),rr[0]['count'],(statistics.median(float(v['rss_mib']) for v in rr if v['rss_mib']) if any(v['rss_mib'] for v in rr) else 'NA'),sep='\t')
    print('[CAUTION] Search timer boundaries differ between Single and Double; DO NOT rank across frameworks by search_s.')

def main():
    argv=sys.argv[1:]
    if BUILD_PROFILE not in ('O0','O1','O2','O3'):die('MBE2_OPT must be O0/O1/O2/O3')
    if not argv or argv[0] in ('help','--help','-h'):
        print(__doc__)
        print('Examples:')
        print('  python3 MBE_1V2_BIPLEX_ET_PROFILER.zip modes')
        print('  python3 MBE_1V2_BIPLEX_ET_PROFILER.zip selftest --cases 50')
        print('  python3 MBE_1V2_BIPLEX_ET_PROFILER.zip youtube --modes pivot --repeats 5 --out youtube.csv')
        print('  python3 MBE_1V2_BIPLEX_ET_PROFILER.zip all /path/to/graph.txt --modes opt --repeats 5')
        return
    command_name=argv[0]
    if command_name=='modes':
        for name,(kind,d) in MODES.items(): print(name,kind,d)
        return
    cache,archive=root_cache()
    parser=argparse.ArgumentParser(prog=f'python3 {archive.name} {command_name}')
    if command_name=='build':
        parser.add_argument('mode',nargs='?',default='all')
        a=parser.parse_args(argv[1:]);modes=MAIN_MATRIX if a.mode=='all' else [a.mode]
        for m in modes:print('[BUILD_READY]',m,build(m,cache,archive))
    elif command_name=='run':
        parser.add_argument('mode',choices=MODES.keys())
        parser.add_argument('graph')
        parser.add_argument('--min-left',type=int,default=1)
        parser.add_argument('--min-right',type=int,default=1)
        parser.add_argument('--timeout',type=int,default=3600)
        parser.add_argument('--emit',help='optional full-output file; adds disk I/O')
        parser.add_argument('--raw',action='store_true',help='print native program output')
        a=parser.parse_args(argv[1:])
        if a.min_left<1 or a.min_right<1:die('minimum sizes must be >= 1')
        emit=a.emit
        r,text=execute(a.mode,cache,archive,a.graph,a.min_left,a.min_right,a.timeout,emit_path=emit)
        if a.raw:print(text)
        else:
            print('[MODE]',a.mode)
            print('[RESULT]',r)
        if emit:print('[EMIT]',Path(emit).resolve())
    elif command_name in ('all','youtube'):
        if command_name=='all': parser.add_argument('graph')
        parser.add_argument('--repeats',type=int,default=5)
        parser.add_argument('--min-left',type=int,default=1)
        parser.add_argument('--min-right',type=int,default=1)
        parser.add_argument('--timeout',type=int,default=3600)
        parser.add_argument('--seed',type=int,default=71213)
        parser.add_argument('--out',default='mbe_2biplex_results.csv')
        parser.add_argument('--modes',default=('youtube' if command_name=='youtube' else 'main'),
                            help='pure|pure1|pure2|guided|main|smoke|opt|youtube|pivot|cache|biplex|pair|profile|comma-separated mode names')
        a=parser.parse_args(argv[1:])
        if a.repeats<1:die('--repeats must be >= 1')
        if command_name=='youtube':
            # Bundled cleaned edge list is streamed out of the ZIP automatically.
            # The ZIP itself remains executable; users need not unpack it.
            with zipfile.ZipFile(archive) as z:
                entry='examples/youtube.txt'
                if entry not in z.namelist():die('Embedded YouTube dataset not found')
                destination=cache/'examples'/'youtube.txt'
                if not destination.is_file() or destination.stat().st_size!=z.getinfo(entry).file_size:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(entry) as src,destination.open('wb') as dst:
                        shutil.copyfileobj(src,dst)
            a.graph=str(destination)
        all_matrix(a,cache,archive)
    elif command_name=='selftest':
        parser.add_argument('--cases',type=int,default=50)
        parser.add_argument('--seed',type=int,default=196002)
        parser.add_argument('--timeout',type=int,default=30)
        parser.add_argument('--all-modes',action='store_true')
        parser.add_argument('--modes',default=None,help='Comma-separated correctness-test modes')
        a=parser.parse_args(argv[1:]);selftest(a,cache,archive)
    else:die('Unknown command: '+command_name+' (try help)')

if __name__=='__main__':main()
