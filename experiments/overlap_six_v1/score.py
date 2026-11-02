"""Reuse frozen feature extraction, host splits, cutoffs and origin reference."""
from intake import DATA, HERE, HOSTS, PARENT, ROOT, RUN, SIDES, digest, relative, report

import torch
import admission as frozen


def main():
    torch.set_num_threads(1)
    manifest=frozen.read(DATA/"manifest.json")
    if manifest["protocol_sha256"]!=digest(PARENT) or manifest["screen_sha256"]!=digest(DATA/"overlap.json"):
        raise ValueError("Intake or frozen rules changed")
    rows=manifest["records"]
    hosts=sorted(HOSTS)
    if {(r["host"],r["variant"]) for r in rows}!={(h,s) for h in hosts for s in SIDES} or len(rows)!=18:
        raise ValueError("Require all six original/benign/Trojan triplets")
    frozen.motifs.OUT=RUN
    items={}
    for r in rows:
        items[r["host"],r["variant"]]=frozen.collect(r,RUN)
        print("controls",r["host"],r["variant"],flush=True)
    tops={h:HOSTS[h][0] for h in hosts}
    paired=frozen.probe_cohort(hosts,items)
    origins=frozen.origin({"external":hosts},items)["external_other_families"]
    overlap={}
    for h in hosts:
        pos=items[h,"trojan"][1]
        overlap[h]={}
        for neg in ("clean","benign"):
            hist=items[h,neg][1]
            delta={k:pos[k]-hist[k] for k in sorted(pos.keys()|hist.keys()) if pos[k]!=hist[k]}
            distance=sum(map(abs,delta.values()))/sum(hist.values())
            overlap[h][neg]=dict(relative_L1=distance,passed=distance<=0.05,delta=delta,
                                 typed_view=frozen.typed_check(h,neg,items,RUN,tops))
    stops=[]
    margins=[]
    for domain,groups in (("class",paired),("origin",origins)):
        for side,measures in groups.items():
            for key,m in measures.items():
                if max(m["mean"],1-m["mean"])>=0.90: stops.append([domain,side,key,m["mean"]])
                if domain=="origin" or key in items[hosts[0],"clean"][0]:
                    if m["ci95"][0]<0.30 or m["ci95"][1]>0.70:
                        margins.append([domain,side,key,m["ci95"]])
    coverage={k:sum(bool(f[2][k].abs().sum()) for f in items.values())
              for k in ("input_fanout","output_xor","output_cone")}
    failures=[(r["host"],r["variant"]) for r in rows if not r["mapped_agrees"]]
    hold=bool(stops or margins or failures or len(hosts)<6 or any(not v["passed"] or v["typed_view"]=="inconclusive"
               for group in overlap.values() for v in group.values()))
    status="hold" if hold else "eligible_for_development_training"
    report(DATA/"admission.json",dict(status=status,families=hosts,semantic_failures=failures,overlap=overlap,
           hard_stops=stops,outside_equivalence_margin=margins,paired_controls=paired,origin_controls=origins,
           coverage=coverage,measurements=[dict(host=h,variant=s,**v[0],gates=v[1]) for (h,s),v in items.items()],
           same_family_native_comparison="inapplicable: no selected host comes from the TrustHub reference panel",
           uncertainty="Exact ordered six-host bootstrap on held-out scores conditional on the inspected reference panel; original token screen was used for host selection.",
           manifest_sha256=digest(DATA/"manifest.json"),protocol_sha256=digest(PARENT)))
    report(ROOT/"data/integrated/ver2_overlap_six_catalog.json",dict(previous_catalog="data/integrated/ver2_tier3_catalog.json",
           original_screen=relative(DATA/"overlap.json"),manifest=relative(DATA/"manifest.json"),
           sha256=digest(DATA/"manifest.json"),admission=relative(DATA/"admission.json"),families=6,records=18,
           source_bundle=relative(DATA/"sources.zip"),source_bundle_sha256=digest(DATA/"sources.zip"),
           admitted_records=0 if hold else 18,status=status,trained=False))
    print(status,len(stops),"hard stops,",len(margins),"margin failures")


if __name__=="__main__":
    main()
