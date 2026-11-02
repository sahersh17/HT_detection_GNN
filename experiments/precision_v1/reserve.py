"""Prospectively nominate supplementary clean-only hosts to cover verification attrition."""
import argparse
import subprocess
from planning import ROOT,DATA,RUN,read,report
from preflight import raw,folder,sha,simulate,command
from select_panel import fingerprints
from triplets import PY,YRUN,trace_ok
import re

def keyset(r):
    return {r["repo"].lower(),r["repo"].split("/")[-2].lower(),str(r["author"]).strip().lower(),
            re.sub(r"[^a-z0-9]","",str(r["title"]).lower()),r["host"].lower(),*r["sha256"].values()}

def mapped_original(r):
    d=folder(r);out=d/"reserve_mapped.v"; script=d/"reserve.ys"
    rel=lambda p:p.relative_to(ROOT).as_posix()
    script.write_text("read_verilog "+" ".join(rel(f) for f in raw(r))+f"\nhierarchy -check -top {r['host']}\nproc; opt; flatten; opt; techmap; opt\nwrite_verilog -noattr {rel(out)}\n")
    command([str(PY),str(YRUN),"-q","-s",rel(script)],timeout=180)
    if not trace_ok(simulate(r,[out],"reserve_check"),read(d/"oracle.json")):raise ValueError("frozen clean mapping fails reference")

def main(n):
    import sys
    from bootstrap import summary
    first=read(DATA/"intake.json");anchor=read(ROOT/"data/overlap_six_v1/overlap.json")
    prior=read(DATA/"reserve_intake.json")["families"] if (DATA/"reserve_intake.json").exists() else []
    used=first["families"]+prior
    keys=set();modules=set();shapes=[]
    for r in used:
        m,s=fingerprints(r);keys.update(keyset(r));modules.update(m);shapes.append(s)
    available=[r for r in read(RUN/"preflight.json") if "error" not in r and r["host"] not in {x["host"] for x in used}]
    for r in available:
        panel=anchor["reference_clean"]
        r["rank"]=sum(sum((r["tokens"]>t)+.5*(r["tokens"]==t) for t in v)/len(v) for v in panel.values())/4
    pools=[sorted((r for r in available if (r["rank"]>.5)==high),key=lambda r:r["commit"]) for high in (True,False)]
    accepted=[];rejected=[]
    while any(pools) and len(accepted)<n:
        for pool in pools:
            while pool and len(accepted)<n:
                r=pool.pop(0)
                m,shape=fingerprints(r)
                if keys&keyset(r) or m&modules or not shape or any(len(shape&x)/min(len(shape),len(x))>.8 for x in shapes):continue
                if sha(folder(r)/"oracle.json")!=r["oracle_sha256"]:continue
                try:mapped_original(r)
                except Exception as e:
                    rejected.append(dict(host=r["host"],reason=str(e)[-500:]));continue
                accepted.append(r);keys.update(keyset(r));modules.update(m);shapes.append(shape);break
    allrows=used+accepted
    group=summary({r["host"]:r["rank"] for r in allrows})
    combined=summary(dict(anchor["origin_token_check"]["by_host"],**{r["host"]:r["rank"] for r in allrows}))
    passed=all(.30<=x<=.70 for g in (group,combined) for x in g["ci95"])
    data=dict(families=prior+accepted,requested_this_wave=n,newly_qualified=len(accepted),passed=passed,
              cumulative_new_origin=group,combined_origin=combined,rejected_clean_map=rejected)
    report(DATA/"reserve_intake.json",data)
    print("supplement",len(accepted),"cumulative CI",combined["ci95"],"passed",passed)
    if not passed:raise SystemExit("Supplemental length screen failed")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("additional",type=int);main(p.parse_args().additional)
