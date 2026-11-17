#!/usr/bin/env python3
"""V63: exact 13-graph paired-block benchmark of independent candidate-layout/fork optimizations."""
from __future__ import annotations
import argparse, hashlib, json, math, os, platform, random, resource, shutil, statistics, subprocess, sys, tempfile, time, traceback
from pathlib import Path
import v57_run as base

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
REPORT=PROJECT/'diagnostics'/'V63_ALL_RESULTS.txt'
CACHE=PROJECT/'diagnostics'/'V63_CHECKPOINT.json'
DATASETS=['youtube','actors','stackoverflow','bibsonomy','dblp','forum','ukwiki','escorts','github','bkcrossing','twitter','imdb','amazon']
ET='--et on --tg off --kappa 2 --et2-root-degree-gate on --et2-reuse-buffers on --v56-terminal 3 --v57-mask-prefix on --v57-mask-fast-closure on --v56-min-paths 8 --v59-dispatch 1 --v59-work-gate 96 --v60-lazy-mask on --v60-root-gate on --v62-tree-mask on --v62-mask-cursor on --v61-fast-emit on'.split()
MODES={
 'st_only':base.BINARY_MODES['st_only'],
 'd_prefork':base.BINARY_MODES['d_prefork'],
 'v62_cursor_emit_d':ET+['--v56-prefork','on'],
 'v62_cursor_emit':ET,
 'v63_inline_st':base.BINARY_MODES['st_only'],
 'v63_core_st':base.BINARY_MODES['st_only'],
 'v63_inline_d':base.BINARY_MODES['d_prefork'],
 'v63_core_d':base.BINARY_MODES['d_prefork'],
 'v63_inline_et':ET,
 'v63_core_et':ET,
 'v63_core_et_d':ET+['--v56-prefork','on'],
 'v63_core_gate192':ET+['--v59-work-gate','192'],
 'v63_core_gate192_d':ET+['--v59-work-gate','192','--v56-prefork','on'],
}
ORIGINAL_MODES=base.BINARY_MODES.copy()
base.BINARY_MODES={**ORIGINAL_MODES,**MODES}
FLAGS=[*base.COMPILER,'-DMBE_V61_FAST_RESULT_APPEND=OFF','-DMBE_ET13_DIAG=OFF','-DMBE_V58_COST_PROFILE=OFF']
MODE_BUILD={m:('inline' if m.startswith('v63_inline_') else 'core' if m.startswith('v63_core_') else 'map') for m in MODES}
DEFAULT_MODES=['st_only','d_prefork','v62_cursor_emit_d','v63_inline_st','v63_core_st','v63_core_d','v63_core_et','v63_core_et_d']
SEED_BASE = 20261018
SEED_STRIDE = 1009

def log(s=''):
 print(s,flush=True)
 with REPORT.open('a',encoding='utf-8') as f:f.write(s+'\n')

def persist(obj):
 CACHE.parent.mkdir(parents=True, exist_ok=True)
 with tempfile.TemporaryDirectory(dir=CACHE.parent) as folder:
  pending = Path(folder) / CACHE.name
  with pending.open('w', encoding='utf-8') as stream:
   json.dump(obj, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
   stream.flush()
   os.fsync(stream.fileno())
  pending.replace(CACHE)


def run_protocol(args, cpu):
 return {
  'datasets': list(args.datasets), 'runs': args.runs, 'timeout': args.timeout, 'cpu': cpu,
  'system': list(platform.uname()), 'python': platform.python_version(),
  'stack': list(resource.getrlimit(resource.RLIMIT_STACK)),
  'mode_flags': {mode: MODES[mode] for mode in args.modes},
  'random_order': {'base': SEED_BASE, 'stride': SEED_STRIDE},
  'anchor_clock': 'perf_counter',
 }


def restore_store(args, protocol):
 if args.fresh or not CACHE.exists():
  return {'modes': args.modes, 'protocol': protocol, 'datasets': {}}
 saved = json.loads(CACHE.read_text(encoding='utf-8'))
 if 'protocol' not in saved:
  raise ValueError(f'{CACHE} predates run metadata. Keep it for reconstruction and collect new blocks in a fresh campaign.')
 if saved.get('protocol') != protocol or saved.get('modes') != args.modes:
  raise ValueError(f'{CACHE} uses different timing settings. Use the original settings or a new campaign directory.')
 return saved

def build():
 results={}
 for variant,extra in [('map',[]),('inline',['-DMBE_V63_INLINE_CANDIDATE=ON']),('core',['-DMBE_V63_INLINE_CANDIDATE=ON','-DMBE_V30_SKIP_EMPTY_PREV=ON'])]:
  dest=HERE/('build_v63_'+variant)
  for cmd in [['cmake','-S',str(HERE/'source'),'-B',str(dest),*FLAGS,*extra], ['cmake','--build',str(dest),'--parallel','2']]:
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=450)
   if p.returncode:raise RuntimeError(f'{cmd}\n{p.stdout[-2500:]}\n{p.stderr[-2500:]}')
  exe=dest/'mbet_fast'
  results[variant]=(exe,base.digest(exe))
 return results

def oracle_all(builds,args):
 # Each mode is checked against a literal oracle set under its OWN executable.
 # The reference b_ref in each group is also used for forced-cap fallback.
 for variant in ['map','inline','core']:
  exe=builds[variant][0]
  subset={m:flags for m,flags in MODES.items() if MODE_BUILD[m]==variant}
  subset['b_ref']=ORIGINAL_MODES['b_ref']
  saved=base.BINARY_MODES
  base.BINARY_MODES=subset
  try:
   log(f'[ORACLE_GROUP_START] variant={variant} modes={list(subset)}')
   base.oracle(exe,args.oracle_cases,type('R',(),{'log':staticmethod(log)})(),28,512,args.timeout)
  finally:
   base.BINARY_MODES=saved
  log(f'[ORACLE_GROUP_PASS] variant={variant}')

def filename(ds,root):
 for d in [root, PROJECT/'data_clean',HERE/'data']:
  if d is not None:
   p=Path(d)/(ds+'.txt')
   if p.is_file():return p
 return None

def has_complete(block,modes):
 jobs = [block.get(tag) for tag in ('st_begin', *modes, 'st_end')]
 return (all(isinstance(job,dict) and 'ms' in job and 'clock' in job for job in jobs)
         and all(math.isfinite(job['ms']) and job['ms'] > 0 for job in jobs)
         and all(math.isfinite(job['clock']) for job in jobs)
         and jobs[-1]['clock'] > jobs[0]['clock'])

def paired_stats(block,modes):
 beg=block['st_begin'];end=block['st_end']; t0=beg['clock'];t1=end['clock'];denom=max(1e-6,t1-t0)
 result={}
 for mode in modes:
  x=block[mode]
  weight=max(0.0,min(1.0,(x['clock']-t0)/denom))
  estimated=beg['ms']+(end['ms']-beg['ms'])*weight
  result[mode]=estimated/x['ms']
 return result

def geometric(a):return math.exp(sum(math.log(x) for x in a)/len(a)) if a else float('nan')

def report_summary(store,args,problems,exe_sha):
 log('\n=== V63 CROSS-DATASET PAIR-BLOCK SUMMARY ===')
 complete={};partial=[]
 for ds in args.datasets:
  item=store.get('datasets',{}).get(ds,{})
  blocks=[]
  for rep in range(args.runs):
   rec=item.get('blocks',{}).get(str(rep),{})
   if has_complete(rec,[m for m in args.modes if m!='st_only']):blocks.append(rec)
  if len(blocks)==args.runs and ds not in problems:
   complete[ds]=blocks
  else:
   partial.append((ds,len(blocks),args.runs))
 log(f'[COMPLETED_DATASETS] {list(complete)}')
 log(f'[PARTIAL_OR_MISSING] {partial}')
 log(f'[FAILED_DETAILS] {problems}')
 for ds,blocks in complete.items():
  pairs=[paired_stats(b,[m for m in args.modes if m!='st_only']) for b in blocks]
  sig=blocks[0]['st_begin']['signature']
  median_base=statistics.median([(b['st_begin']['ms']+b['st_end']['ms'])/2 for b in blocks])
  log(f'[DATASET] {ds} checksum={sig} runs={len(blocks)} st_anchor_mid_median_ms={median_base:.3f} PASS')
  changes=[b['st_end']['ms']/b['st_begin']['ms']-1 for b in blocks]
  log(f'[DRIFT] {ds} anchor_end_vs_begin_pct={list(round(v*100,2) for v in changes)}')
  for m in args.modes:
   if m=='st_only':continue
   obs=[p[m] for p in pairs]
   raw=statistics.median(b[m]['ms'] for b in blocks)
   log(f'[PAIRED] dataset={ds} mode={m} median_speedup={statistics.median(obs):.5f}x gm_blocks={geometric(obs):.5f}x raw_median_ms={raw:.3f} block_ratios={list(round(v,5) for v in obs)}')
 for m in args.modes:
  if m=='st_only':continue
  vals=[statistics.median([paired_stats(b,[m])[m] for b in blocks]) for ds,blocks in complete.items()]
  if not vals:continue
  win=sum(v>1.02 for v in vals)
  lose=sum(v<1.0 for v in vals)
  log(f'[GM_PAIRED] mode={m} datasets={len(vals)} gm_vs_ST={geometric(vals):.5f}x wins_over_2pct={win}/{len(vals)} losses={lose}/{len(vals)}')
  if 'd_prefork' in args.modes and m!='d_prefork':
   against_d=[statistics.median([paired_stats(b,[m,'d_prefork'])[m]/paired_stats(b,[m,'d_prefork'])['d_prefork'] for b in blocks]) for ds,blocks in complete.items()]
   log(f'[GM_VS_D] mode={m} datasets={len(against_d)} gm_vs_D={geometric(against_d):.5f}x wins_over_2pct={sum(x>1.02 for x in against_d)}/{len(against_d)}')
  if len(vals)==len(args.datasets) and len(vals)>=4 and win >= (len(vals)//2+1):
   log(f'[TARGET_CANDIDATE] mode={m} more_than_half_of_all_datasets_above_2pct=YES; requires repeated independent batch for stability')
 log(f'[COMPLETE] done={len(complete)}/{len(args.datasets)} all_complete={len(complete)==len(args.datasets)} combined_executable_sha256={exe_sha}')
 log(f'[CHECKPOINT] {CACHE}')
 log(f'[OUTPUT] {REPORT}')
 return len(complete)

def main():
 ap=argparse.ArgumentParser(description='V63 13-dataset paired randomized block benchmark, with resume checkpoints')
 ap.add_argument('--datasets',nargs='+',default=DATASETS)
 ap.add_argument('--data-root',type=Path,default=None)
 ap.add_argument('--runs',type=int,default=5)
 ap.add_argument('--timeout',type=int,default=1200)
 ap.add_argument('--cpu',default='auto')
 ap.add_argument('--min-completed',type=int,default=13)
 ap.add_argument('--modes',nargs='+',choices=MODES,default=DEFAULT_MODES)
 ap.add_argument('--oracle-cases',type=int,default=100)
 ap.add_argument('--skip-oracle',action='store_true')
 ap.add_argument('--fresh',action='store_true',help='clear past checkpoints/results and start again')
 ap.add_argument('--retry-failed',action='store_true',help='retry previously failed configuration jobs')
 args=ap.parse_args()
 if args.runs<=0 or args.timeout<=0 or args.min_completed<=0 or 'st_only' not in args.modes:ap.error('invalid runs, timeout or modes; st_only mandatory')
 if len(set(args.datasets))!=len(args.datasets):ap.error('duplicate datasets')
 if len(set(args.modes))!=len(args.modes):ap.error('duplicate modes')
 stack_warning = None
 try:
  soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
  minimum = 64 << 20 if hard == resource.RLIM_INFINITY else min(64 << 20, hard)
  if soft != resource.RLIM_INFINITY and soft < minimum:
   resource.setrlimit(resource.RLIMIT_STACK, (minimum, hard))
 except OSError as error:
  stack_warning = str(error)
 allowed=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else []
 cpu=(allowed[0] if allowed and shutil.which('taskset') else None) if args.cpu=='auto' else (None if args.cpu=='none' else int(args.cpu))
 if cpu is not None and allowed and cpu not in allowed:ap.error(f'CPU {cpu} outside allowed {allowed}')
 protocol = run_protocol(args, cpu)
 try:
  store = restore_store(args, protocol)
 except (OSError, ValueError) as error:
  ap.error(str(error))
 builds = build()
 sha = hashlib.sha256(json.dumps({v:d[1] for v,d in builds.items()}, sort_keys=True).encode()).hexdigest()
 if 'release_sha256' in store and store['release_sha256'] != sha:
  ap.error(f'{CACHE} uses different binaries. Use the original binaries or a new campaign directory.')
 store['release_sha256'] = sha
 REPORT.parent.mkdir(parents=True,exist_ok=True)
 REPORT.write_text('',encoding='utf-8')
 log('# V63: inline 0/1 candidate child; independent prev-cursor skip; V62 ET control; exact DFS fallback')
 log('# Release only, no phase clocks. Each block ST/start -> shuffled variants -> ST/end, with interpolated paired ST anchor.')
 log('# Paired speedups are compared within graph and block, then across graphs. Do not count incomplete datasets as wins.')
 log(f'[COMMAND] {sys.argv}')
 log(f'[CONFIG] 13data={args.datasets} modes={args.modes} runs={args.runs} timeout={args.timeout}s cpu={args.cpu} fresh={args.fresh}')
 log(f'[ENV] {platform.platform()} python={platform.python_version()} cwd={os.getcwd()}')
 if stack_warning:log(f'[STACK_WARNING] {stack_warning}')
 log(f'[CPU_AFFINITY] {cpu}')
 log(f'[BUILD] combined_sha256={sha} compile_flags={FLAGS}')
 for variant,(path,exe_sha) in builds.items():
  log(f'[BINARY] variant={variant} sha256={exe_sha} path={path}')
 if CACHE.exists() and not args.fresh:log('[RESUME] loaded compatible checkpoint')
 persist(store)
 if not args.skip_oracle:
  log('[ORACLE_START] exact full sets for ALL three compiled candidate layouts and forced-cap fallbacks')
  oracle_all(builds,args)
  log('[ORACLE_DONE] PASS')
 problems={};start_total=time.time()
 non_st=[m for m in args.modes if m!='st_only']
 for ds in args.datasets:
  source=filename(ds,args.data_root)
  if source is None:
   problems[ds]='dataset file not found';log(f'[MISSING] dataset={ds}');continue
  log(f'[START] dataset={ds} source={source}')
  try:
   with tempfile.TemporaryDirectory(prefix='v63_'+ds+'_' ) as tmp:
    prepared=Path(tmp)/'clean.txt'
    edges=base.cleanup_graph(source,prepared)
    digest=base.digest(prepared)
    log(f'[DATA] dataset={ds} clean_edges={edges} clean_sha256={digest}')
    dsentry = store['datasets'].setdefault(ds, {'graph_sha256': digest, 'blocks': {}, 'signature': None})
    if dsentry['graph_sha256'] != digest:
     problems[ds] = 'normalized input changed. Restore the original graph or use a new campaign directory.'
     log(f'[INPUT_MISMATCH] dataset={ds} {problems[ds]}')
     continue
    for rep in range(args.runs):
     block=dsentry['blocks'].setdefault(str(rep),{})
     # An interrupted block spans different thermal/load conditions. Keep
     # completed blocks but restart only the partial block on a new invocation.
     # Otherwise its two ST anchors would be temporally incomparable.
     if block and not has_complete(block,non_st):
      if not args.retry_failed and any('error' in job for job in block.values()):
       problems[ds] = f'block {rep+1} previously failed. Use --retry-failed to rerun it.'
       log(f'[SKIP_FAILED_BLOCK] dataset={ds} {problems[ds]}')
       break
      log(f'[RESUME_RESTART_PARTIAL_BLOCK] dataset={ds} block={rep+1}; discarding incomplete block for valid paired ST anchors')
      block.clear();persist(store)
     order=non_st.copy();random.Random(SEED_BASE+SEED_STRIDE*rep+sum(map(ord,ds))).shuffle(order)
     jobs=['st_begin',*order,'st_end']
     failed=False
     for position,tag in enumerate(jobs):
      if tag in block and 'ms' in block[tag]:continue
      mode='st_only' if tag.startswith('st_') and tag in ('st_begin','st_end') else tag
      log(f'[JOB_START] dataset={ds} block={rep+1}/{args.runs} mode={tag} pos={position+1}/{len(jobs)}')
      try:
       info=base.execute(builds[MODE_BUILD[mode]][0],prepared,mode,None,cpu,28,512,args.timeout)
       sig=[info['Count'],info['Checksum_XOR'],info['Checksum_SUM']]
       milliseconds = info['Search_Time_ms']
       if not math.isfinite(milliseconds) or milliseconds <= 0:raise ValueError('nonpositive or nonfinite search time')
       if ds in base.KNOWN_COUNT and sig[0]!=base.KNOWN_COUNT[ds]:raise ValueError(f'known COUNT mismatch {sig[0]} != {base.KNOWN_COUNT[ds]}')
       if dsentry['signature'] is None:dsentry['signature']=sig
       if sig != dsentry['signature']:raise ValueError(f'checksum mismatch {sig} != {dsentry["signature"]}')
       block[tag]={'ms':milliseconds,'clock':time.perf_counter(),'signature':sig,'rss_mib':info['rss_mib'],'bitmask_hits':info['V56_Hits'],'bitmask_outputs':info['V56_Outputs'],'prefork_skips':info['V56_PreFork_Skips']}
       del info
       log(f'[RUN] dataset={ds} block={rep+1}/{args.runs} mode={tag} search_ms={block[tag]["ms"]:.3f} hits={block[tag]["bitmask_hits"]} output={block[tag]["bitmask_outputs"]} prefork_skips={block[tag]["prefork_skips"]}')
      except Exception as e:
       block[tag]={'error':str(e)[-1000:]}
       log(f'[JOB_FAILED] dataset={ds} block={rep+1} mode={tag} reason={str(e)[-400:]}')
       persist(store)
       failed=True
       break
      persist(store)
     if has_complete(block,non_st):
      ratios=paired_stats(block,non_st)
      log(f'[BLOCK_DONE] dataset={ds} block={rep+1} paired='+ ' '.join(f'{k}:{v:.4f}x' for k,v in ratios.items()))
     else:log(f'[BLOCK_PARTIAL] dataset={ds} block={rep+1} completed={sum("ms" in block.get(k,{}) for k in jobs)}/{len(jobs)}')
     if failed:
      problems[ds]=f'block {rep+1} failed at {tag}';break
  except KeyboardInterrupt:
   log('[INTERRUPTED] safe checkpoint retained; run same command to resume');persist(store);raise
  except Exception as e:
   problems[ds]=str(e)[-800:];log(f'[FAILED_DATASET] dataset={ds} reason={str(e)[-500:]}')
  persist(store)
 done=report_summary(store,args,problems,sha)
 if done<args.min_completed:
  log(f'[INCOMPLETE] completed={done}, required={args.min_completed}; use same command to resume after resolving failures')
  raise SystemExit(2)
if __name__=='__main__':main()
