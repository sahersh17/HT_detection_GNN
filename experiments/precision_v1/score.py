"""Rerun the original held-out protocol on the six anchors plus verified new families."""
from collections import Counter
import hashlib,json,sys
from planning import ROOT,DATA,RUN,PREV,read,report
from preflight import sha
from bootstrap import summary
sys.path.insert(0,str(ROOT/"experiments/tier3_admission_v1"))
import admission as frozen
import torch
import math

def main(cache_only=False):
    torch.set_num_threads(1)
    frozen.summary=summary
    previous=read(PREV/"admission.json")
    intake=read(DATA/"intake.json")
    if (DATA/"reserve_intake.json").exists():
        intake["families"]+=read(DATA/"reserve_intake.json")["families"]
    if cache_only:
        ready=[folder for r in intake["families"] if (folder:=RUN/"hosts"/r["host"]/"verified.json").exists()]
        incoming=dict(records=[r for p in ready for r in read(p)],screen_sha256=sha(DATA/"intake.json"))
    else:
        incoming=read(DATA/"manifest.json")
        if (DATA/"reserve_intake.json").exists() and incoming["reserve_screen_sha256"]!=sha(DATA/"reserve_intake.json"):
            raise ValueError("Supplementary intake changed")
    if sha(DATA/"intake.json")!=incoming["screen_sha256"] or sha(ROOT/"experiments/tier3_admission_v1/protocol.json")!=previous["protocol_sha256"]:
        raise ValueError("Frozen inputs changed")
    for groups in (previous["paired_controls"],previous["origin_controls"]):
        for metrics in groups.values():
            for old in metrics.values():
                fresh=summary(old["by_host"])
                assert max(abs(a-b) for a,b in zip(fresh["ci95"],old["ci95"]))<1e-10
    rows=read(PREV/"manifest.json")["records"]+incoming["records"]
    new={r["host"] for r in incoming["records"]}
    hosts=sorted({r["host"] for r in rows})
    tops={r["host"]:r["top"] for r in rows}
    def root(h):return RUN/"hosts" if h in new else ROOT/"runs/overlap_v1"
    items={};graph_unavailable={}
    original_fit=frozen.fit_predict
    def checked_fit(*args):
        scores=original_fit(*args)
        if not all(math.isfinite(v) for v in scores):raise ValueError("Nonfinite probe score")
        return scores
    frozen.fit_predict=checked_fit
    cache=RUN/"feature_cache";cache.mkdir(exist_ok=True)
    for i,r in enumerate(rows):
        h,s=r["host"],r["variant"];frozen.motifs.OUT=root(h)
        key=hashlib.sha256(json.dumps([r["sources"],r["mapped_json_sha256"],previous["protocol_sha256"]],sort_keys=True).encode()).hexdigest()
        path=cache/(key+".pt")
        if path.exists():
            sc,hist,feat=torch.load(path,weights_only=True);item=sc,Counter(hist),feat
        else:
            try:item=frozen.collect(r,root(h))
            except ValueError as e:
                if str(e)!="No gates after synthesis":raise
                sc=dict(frozen.lexical(tuple(ROOT/p for p in r["sources"])),cells=0,edges=0)
                item=sc,Counter(),{"metadata":torch.tensor([sc[k] for k in ("characters","lines","windows")]).float()}
            torch.save((item[0],dict(item[1]),item[2]),path)
        if not item[1]:graph_unavailable[h]=s
        items[h,s]=item
        if i%15==0:print("features",i+1,"/",len(rows),flush=True)
    if cache_only:return
    graph_hosts=[h for h in hosts if h not in graph_unavailable]
    print("starting family-held-out probes",len(hosts),len(graph_hosts),flush=True)
    paired=frozen.probe_cohort(graph_hosts,items)
    if graph_unavailable:
        scalar_items={key:(v[0],v[1],{"metadata":v[2]["metadata"]}) for key,v in items.items()}
        for arm,metrics in frozen.probe_cohort(hosts,scalar_items).items():paired[arm].update(metrics)
    origin=frozen.origin({"extended":hosts},items)["extended_other_families"]
    stops=[];margins=[]
    for domain,groups in (("class",paired),("origin",origin)):
        for arm,mm in groups.items():
            for key,m in mm.items():
                if max(m["mean"],1-m["mean"])>=.90:stops.append([domain,arm,key,m["mean"]])
                if domain=="origin" or key in items[hosts[0],"clean"][0]:
                    if m["ci95"][0]<.30 or m["ci95"][1]>.70:margins.append([domain,arm,key,m["ci95"]])
    overlap={}
    for h in hosts:
        overlap[h]={}
        for side in ("clean","benign"):
            neg=items[h,side][1];pos=items[h,"trojan"][1]
            delta={k:pos[k]-neg[k] for k in sorted(neg.keys()|pos.keys()) if neg[k]!=pos[k]}
            dist=sum(map(abs,delta.values()))/sum(neg.values())
            overlap[h][side]=dict(relative_L1=dist,passed=dist<=.05,delta=delta,
                typed_view="inconclusive" if h in graph_unavailable else frozen.typed_check(h,side,items,root(h),tops))
    comparison=[]
    for domain,arm,key,_ in previous["outside_equivalence_margin"]:
        m=(paired if domain=="class" else origin)[arm][key];ci=m["ci95"]
        comparison.append(dict(domain=domain,arm=arm,control=key,mean=m["mean"],ci95=ci,
            still_fails=ci[0]<.30 or ci[1]>.70,point_outside=not .30<=m["mean"]<=.70,
            excludes_chance=not ci[0]<=.50<=ci[1],
            new_only=sum(m["by_host"][h] for h in new)/len(new) if new else None))
    coverage={k:sum(bool(f[2][k].abs().sum()) for f in items.values() if k in f[2]) for k in ("input_fanout","output_xor","output_cone")}
    strata={"original_six":set(hosts)-new,
            "new_native":{r["host"] for r in incoming["records"] if r["edit_kind"]!="guarded_output_fallback"},
            "new_boundary_fallback":{r["host"] for r in incoming["records"] if r["edit_kind"]=="guarded_output_fallback"}}
    sensitivity=[]
    for domain,groups in (("class",paired),("origin",origin)):
        for side,metrics in groups.items():
            for key,m in metrics.items():
                estimates={}
                for label,members in strata.items():
                    available=members & m["by_host"].keys()
                    if available:
                        part=summary({h:m["by_host"][h] for h in available})
                        estimates[label]=dict(n=len(available),mean=part["mean"],ci95=part["ci95"])
                sensitivity.append(dict(domain=domain,side=side,metric=key,subgroups=estimates))
    verified_only_blocked=bool(stops or margins or len(hosts)<6 or any(not x["passed"] or x["typed_view"]=="inconclusive" for g in overlap.values() for x in g.values()))
    flags=bool(incoming["failures"] or verified_only_blocked)
    status="hold" if flags else "eligible_for_development_training"
    report(DATA/"admission.json",dict(status=status,verified_only_passes_controls=not verified_only_blocked,
        independent_lineage_groups=len(hosts),verified_rows=len(rows),graph_unavailable=graph_unavailable,
        hard_stops=stops,outside_equivalence_margin=margins,earlier_29=comparison,semantic_failures=incoming["failures"],
        coverage=coverage,overlap=overlap,paired_controls=paired,origin_controls=origin,
        construction_sensitivity=sensitivity,
        measurements=[dict(host=h,variant=s,**v[0],gates=dict(v[1])) for (h,s),v in items.items()],
        protocol_sha256=previous["protocol_sha256"],parent_manifest_sha256=sha(PREV/"manifest.json"),manifest_sha256=sha(DATA/"manifest.json"),
        limits="Pointwise exact whole-family bootstrap conditional on fixed out-of-fold predictions and fixed TrustHub panel. New families share an interface and selection procedure; this is not independent evidence of deployment performance."))
    report(ROOT/"data/integrated/ver2_precision_catalog.json",dict(previous_catalog="data/integrated/ver2_overlap_six_catalog.json",
        planning="data/precision_v1/planning.json",intake="data/precision_v1/intake.json",manifest="data/precision_v1/manifest.json",
        decision="data/precision_v1/admission.json",attempted_new=len(intake["families"]),verified_new=len(new),total_verified_families=len(hosts),
        source_bundle="data/precision_v1/triplet_edits.zip",source_bundle_sha256=sha(DATA/"triplet_edits.zip"),
        status=status,admitted_records=0 if flags else len(rows),trained=False))
    print(status,len(stops),"hard stops",len(margins),"failed intervals",flush=True)
if __name__=="__main__": main("--cache-only" in sys.argv)
