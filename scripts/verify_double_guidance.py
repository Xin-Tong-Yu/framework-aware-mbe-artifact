#!/usr/bin/env python3
"""Check Double defect counts, Eq. (12) pivots and exact output on small graphs.

Builds temporary instrumented copies of the shipped C++ sources. The reference
pivot uses exact adjacency, independently of optional missing-ID/list caches.
Run on Linux with g++; --msvc supports local Windows correctness checks only.
No timing from this verifier is a manuscript measurement.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
MEMBERS = (
    "framework_ablations/MBE_CORRECTED_13DATA/two_source/",
    "framework_ablations/MBE_FAST_FOUR_MODES/two/source/",
)

VERIFY = r"""
#ifndef IPS_ET_TARGET_DEGREE
#define IPS_ET_TARGET_DEGREE 1
#endif
    void verifyDefects() {
        fprintf(stderr, "[VERIFY] STATE");
        for (int t=0;t<2;++t) {
            const int z=t^1;
            for (int i=S[t].x;i<S[t].r;++i) {
                const int u=S[t][i];
                int dc=0, dx=0;
                for (int j=S[z].c;j<S[z].r;++j) dc+=!g->connect(u,S[z][j],t);
                if (ndC[t][u]!=dc) {fprintf(stderr,"\nBAD exact candidate count\n");abort();}
                fprintf(stderr," %d:%d:%d:%d",t,i<S[t].c,u,dc);
                if(i>=S[t].c) {
                    for (int j=S[z].x;j<S[z].c;++j) dx+=!g->connect(u,S[z][j],t);
                    if(ndX[t][u]!=dx) {fprintf(stderr,"\nBAD exclusion count\n");abort();}
                    for(int v:currentResult[z]) if(!g->connect(u,v,t)) abort();
                }
            }
        }
        fprintf(stderr,"\n");
    }
    void verifyPivot(int actualSide,int actualId) {
        int bestSide=-1,bestId=-1,bestDegree=INT32_MAX;
        auto take=[&](int t,int u) {
            if(ndC[t][u]<bestDegree) {bestSide=t;bestId=u;bestDegree=ndC[t][u];}
        };
        for(int t=0;t<2;++t) for(int i=S[t].x;i<S[t].c;++i) take(t,S[t][i]);
        for(int t=0;t<2;++t) for(int i=S[t].c;i<S[t].r;++i) {
            int u=S[t][i];
            bool eligible=true;
#ifndef IPS_CLASSIC_PIVOT
            eligible=ndC[t][u]>IPS_ET_TARGET_DEGREE || ndX[t][u]>0;
            int z=t^1;
            for(int j=S[z].c;!eligible && j<S[z].r;++j) {
                int v=S[z][j];
                eligible=!g->connect(u,v,t) && ndC[z][v]>IPS_ET_TARGET_DEGREE;
            }
#endif
            if(eligible && bestSide>=0 && ndC[t][u]==bestDegree && S[bestSide].pos(bestId)<S[bestSide].c)
                fprintf(stderr,"[VERIFY] X_TIE\n");
            if(eligible)take(t,u);
        }
        if(bestSide<0) {
            fprintf(stderr,"[VERIFY] FALLBACK\n");
            for(int t=0;t<2;++t) for(int i=S[t].c;i<S[t].r;++i)take(t,S[t][i]);
        }
        if(bestSide!=actualSide || bestId!=actualId) {
            fprintf(stderr,"BAD Eq12 pivot: expected %d:%d, got %d:%d\n",bestSide,bestId,actualSide,actualId);
            abort();
        }
        const int pos=S[bestSide].pos(bestId);
        fprintf(stderr,"[VERIFY] PIVOT %d:%d:%d:%d\n",bestSide,bestId,bestDegree,pos<S[bestSide].c);
    }
"""


def instrument(code, reject=False):
    # Only temporary test copies are instrumented; production sources are intact.
    first="    void branch(int32_t deep) {\n"
    assert code.count(first)==1
    code=code.replace(first,VERIFY+first)
    spot="        //when there is no edge\n"
    assert code.count(spot)==1
    code=code.replace(spot,"        verifyDefects();\n\n"+spot)
    spot="        int32_t t = min_side, z = min_side ^ 1, pivot = min_id;\n"
    assert code.count(spot)==1
    code=code.replace(spot,"        verifyPivot(min_side, min_id);\n"+spot)
    dense='if (g->deg(u, tt) >= S[zz].cSize() - 1) {'
    assert code.count(dense)==1
    code=code.replace(dense,dense+' fprintf(stderr,"[VERIFY] DENSE\\n");')
    sparse='} else {        // u must not be skipped'
    assert code.count(sparse)==1
    code=code.replace(sparse,'} else { fprintf(stderr,"[VERIFY] SPARSE\\n");        // u must not be skipped')
    # Bounds-check the optional second ID in test copies so a target-degree-1
    # cached pivot cannot hide an invalid b == -1 access as unchecked UB.
    code=code.replace("ndC[z][b]","ndC[z].at(b)")
    if reject:
        if "    bool enumerateTwoBiplexTerminal() {\n" in code:
            code=code.replace("    bool enumerateTwoBiplexTerminal() {\n",
                              '    bool enumerateTwoBiplexTerminal() {\n        fprintf(stderr,"[VERIFY] REJECT\\n"); return false;\n')
        else:
            spot="                if (validMatching) {\n"
            assert code.count(spot)==1
            code=code.replace(spot,'                fprintf(stderr,"[VERIFY] REJECT\\n"); validMatching=false;\n'+spot)
    return code


def oracle(nl,nr,edges,left,right):
    neighbors=[{v for a,v in edges if a==u} for u in range(nl)]
    result=set()
    for mask in range(1,1<<nl):
        a=frozenset(u for u in range(nl) if mask>>u&1)
        b=frozenset.intersection(*(frozenset(neighbors[u]) for u in a))
        if len(a)<left or len(b)<right:continue
        if frozenset(u for u in range(nl) if b<=neighbors[u])==a:result.add((a,b))
    return result


def read_output(path):
    found=[]
    for line in path.read_text().splitlines():
        a,b=line.split("|")
        a=list(map(int,a.split()));b=list(map(int,b.split()))
        assert a[0]==len(a)-1 and b[0]==len(b)-1
        found.append((frozenset(a[1:]),frozenset(b[1:])))
    assert len(found)==len(set(found)),"duplicate owned output"
    return set(found)


def fixtures(cases):
    # A real two-hop-core root state contains sparse-scanned missing edges.
    # Before the fix, Eq. (12) selects side-1 ID 4; the cache-only code
    # skips that legal first minimum and incorrectly chooses side-1 ID 1.
    yield "sparse_obstruction",9,12,{(0, 2), (0, 4), (0, 9), (0, 11), (1, 1), (1, 4), (1, 6), (1, 7), (1, 10), (1, 11), (2, 0), (2, 2), (2, 3), (2, 4), (2, 5), (2, 10), (3, 2), (4, 0), (4, 1), (4, 4), (4, 5), (4, 6), (4, 7), (4, 10), (5, 2), (5, 3), (5, 4), (5, 7), (5, 8), (5, 9), (6, 4), (6, 5), (6, 6), (6, 10), (7, 4), (7, 6), (7, 7), (8, 4), (8, 8), (8, 10)},1,1
    yield "matching",6,6,{(u,v) for u in range(6) for v in range(6) if u!=v},1,1
    yield "cycle",6,6,{(u,v) for u in range(6) for v in range(6) if v not in (u,(u+1)%6)},1,1
    yield "sparse",6,7,{(u,v) for u in range(6) for v in range(7) if (u+v)%4==0},1,1
    yield "dense_sizes",6,7,{(u,v) for u in range(6) for v in range(7) if (u*7+v)%8},2,3
    rng=random.Random(8126012)
    for i in range(cases):
        p=(0.2,0.5,0.8)[i%3]
        edges={(u,v) for u in range(6) for v in range(7) if rng.random()<p}
        yield f"random{i}",6,7,edges or {(0,0)},1+(i%2),1+(i%3==0)


def compile_program(args,source,target,defines,work):
    if args.msvc:
        compat=work/"compat/sys";compat.mkdir(parents=True,exist_ok=True)
        (compat/"resource.h").write_text("// Resource accounting is unused in these correctness checks.\n")
        command=[args.cxx or "cl","/nologo","/std:c++17","/EHsc","/DNOMINMAX","/wd4477",
                 "/I"+str(compat.parent),*("/D"+x for x in defines),str(source/"main.cpp"),
                 "/Fe:"+str(target),"/Fo:"+str(target.with_suffix(".obj"))]
    else:
        command=[args.cxx or os.environ.get("CXX","g++"),"-O1","-std=c++17","-UNDEBUG",
                 *("-D"+x for x in defines),str(source/"main.cpp"),"-o",str(target)]
    run=subprocess.run(command,capture_output=True,text=True,errors="replace",timeout=120)
    if run.returncode:raise RuntimeError("Native build failed:\n"+run.stdout+run.stderr)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle",type=Path,default=ROOT/"src/paper_ablations/MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip")
    ap.add_argument("--only",choices=("guided","pure","all"),default="all")
    ap.add_argument("--cases",type=int,default=20)
    ap.add_argument("--pure-source",type=Path,default=ROOT/"src/pure_et1_et2/engine/two")
    ap.add_argument("--cxx")
    ap.add_argument("--msvc",action="store_true",help="run from a configured x64 MSVC environment")
    ap.add_argument("--report",type=Path)
    args=ap.parse_args()
    counts=Counter();checks=0
    with TemporaryDirectory(prefix="mbe-double-guidance-") as directory:
        work=Path(directory);sources={}
        if args.only!="pure":
            with ZipFile(args.bundle) as archive:
                assert archive.read(MEMBERS[0]+"ips.hpp")==archive.read(MEMBERS[1]+"ips.hpp"),"Double guided source copies differ"
                folder=work/"guided";folder.mkdir()
                for name in archive.namelist():
                    if name.startswith(MEMBERS[0]) and not name.endswith("/"):
                        (folder/Path(name).name).write_bytes(archive.read(name))
            sources["guided"]=folder
        if args.only!="guided":
            folder=work/"pure"
            shutil.copytree(args.pure_source,folder)
            sources["pure"]=folder
        modes={}
        for kind,source in sources.items():
            plans=[("vector_st",["IPS_CLASSIC_PIVOT","IPS_DISABLE_ET"],False),
                   ("compact_st",["IPS_CLASSIC_PIVOT","IPS_DISABLE_ET","IPS_ST_V24_SINGLE_DEFECT"],False)]
            degrees=(1,) if kind=="guided" else (1,2)
            for degree in degrees:
                common=[] if kind=="guided" else [f"IPS_ET_TARGET_DEGREE={degree}"]
                for state in ("vector","compact"):
                    plans.append((f"{state}_tg{degree}",common+(["IPS_ST_V24_SINGLE_DEFECT"] if state=="compact" else []),False))
                if kind=="pure":
                    plans.append((f"compact_cached{degree}",common+["IPS_ST_V24_SINGLE_DEFECT","IPS_TG2_CACHED_MISSING"],False))
            plans.append(("compact_reject",["IPS_ST_V24_SINGLE_DEFECT"],True))
            if kind=="pure":
                plans.append(("compact_cached1_reject",["IPS_ST_V24_SINGLE_DEFECT","IPS_ET_TARGET_DEGREE=1","IPS_TG2_CACHED_MISSING"],True))
            original=(source/"ips.hpp").read_text()
            for name,flags,reject in plans:
                (source/"ips.hpp").write_text(instrument(original,reject),encoding="utf-8")
                target=work/(kind+"_"+name+(".exe" if os.name=="nt" else ""))
                compile_program(args,source,target,flags,work)
                modes[kind,name]=target
        for name,nl,nr,edges,left,right in fixtures(args.cases):
            graph=work/(name+".clean")
            graph.write_text(f"{nl} {nr} {len(edges)}\n"+"".join(f"{u} {v}\n" for u,v in sorted(edges)))
            expected=oracle(nl,nr,edges,left,right);traces={}
            for (kind,mode),program in modes.items():
                output=work/"out.txt"
                command=[str(program),"-f",str(graph),"-d","two","-l",str(left),"-r",str(right),"-o",str(output)]
                run=subprocess.run(command,capture_output=True,text=True,errors="replace",timeout=30)
                if run.returncode:raise AssertionError(f"{name}/{kind}/{mode}: {run.returncode}\n{run.stderr[-5000:]}")
                assert read_output(output)==expected,f"incorrect result set: {name}/{kind}/{mode}"
                trace=[line for line in run.stderr.splitlines() if line.startswith("[VERIFY] ")]
                counts.update(line.split()[1] for line in trace)
                for line in trace:
                    if line.startswith("[VERIFY] STATE"):
                        for field in line.split()[2:]:
                            degree=int(field.rsplit(":",1)[1])
                            counts["DEFECT_"+(str(degree) if degree<=2 else "GT2")]+=1
                traces[kind,mode]=trace;checks+=1
            for kind in sources:
                for suffix in ("st",*(f"tg{d}" for d in ((1,) if kind=="guided" else (1,2)))):
                    assert traces[kind,"vector_"+suffix]==traces[kind,"compact_"+suffix],f"state representation changed branching: {name}/{kind}/{suffix}"
        for required in ("FALLBACK","REJECT","DENSE","SPARSE","X_TIE","DEFECT_0","DEFECT_1","DEFECT_2","DEFECT_GT2"):
            assert counts[required],"required boundary was not exercised: "+required
    report={"result":"PASS","exact_output_comparisons":checks,"events":dict(counts),
            "checks":["exact untruncated candidate/exclusion counts","Eq12 eligibility","excluded-pivot tie precedence",
                      "no-pivot fallback","forced terminal rejection","selected/candidate compatibility",
                      "vector/compact state and pivot trace equality","duplicate-free exact output sets","bounds-checked second missing-ID access"]}
    print(json.dumps(report,indent=2))
    if args.report:args.report.write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":main()
