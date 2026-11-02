"""Repeat the frozen controls by edit kind and across all host-grouped edits."""
import json
from collections import defaultdict

import torch

from generate import HOSTS, KINDS, OUT, ROOT, RUN, build
import audit
from typed_pairs import distinguish, view


def read(path):
    return json.loads(path.read_text())


def mixed_scores(rows, features, scalars):
    results = {}
    for negative in ("clean","benign"):
        cohort = [i for i,r in enumerate(rows) if r["variant"] in (negative,"trojan")]
        probes = {name:{i:s[name] for i,s in enumerate(scalars)} for name in scalars[0]}
        for name in features[0]:
            matrix = torch.stack([f[name] for f in features])
            scores = {}
            for fold,h in enumerate(sorted(h.name for h in HOSTS)):
                train = [i for i in cohort if rows[i]["host"]!=h]
                test = [i for i in cohort if rows[i]["host"]==h]
                labels = torch.tensor([rows[i]["label"] for i in train])
                scores.update(zip(test,audit.fit_predict(matrix[train],labels,torch.ones(len(train)),matrix[test],42+fold)))
            probes[name]=scores
        results[negative]={}
        for name,scores in probes.items():
            pairs=defaultdict(dict)
            for i in cohort:
                row=rows[i]
                pairs[row["host"],row["edit_kind"]][row["variant"]]=scores[i]
            by_host={h.name:sum(audit.rank(pairs[h.name,k]["trojan"],pairs[h.name,k][negative])
                                for k in KINDS)/len(KINDS) for h in HOSTS}
            results[negative][name]=dict(mean=sum(by_host.values())/len(by_host),by_host=by_host)
    return results


def main():
    rows,features,scalars,checks,blockers=[],[],[],[],[]
    manifests=[]
    for kind in KINDS:
        directory=OUT/kind
        manifest=directory/"manifest.json"
        records=read(manifest)["records"]
        vectors,counts=audit.main(directory,RUN/kind,catalog_name=None)
        decision=read(directory/"decision.json")
        blockers.extend([kind,*entry] for entry in decision["blockers"])
        manifests.append(dict(edit_kind=kind,path=build.rel(manifest),sha256=build.digest(manifest),records=len(records)))
        for host in HOSTS:
            group={r["variant"]:r for r in records if r["host"]==host.name}
            graphs={s:view(RUN/kind/host.name/s/"yosys.json",r["mapped_json_sha256"]) for s,r in group.items()}
            for side in ("clean","benign"):
                checks.append(dict(host=host.name,edit_kind=kind,negative=side,
                                   **distinguish(graphs[side],graphs["trojan"])))
        rows.extend(records)
        features.extend(vectors)
        scalars.extend(counts)
    mixed=mixed_scores(rows,features,scalars)
    for side,probes in mixed.items():
        for name,r in probes.items():
            if max(r["mean"],1-r["mean"])>=0.90:
                blockers.append(["mixed",side,name,r["mean"]])
    # Matched-host generator identity diagnostic, with both sources represented
    # equally per host, kind and arm. Source identity is not the Trojan label.
    old=read(ROOT/"data/tier12_v2/decision.json")["scalar_features"]
    previous={(r["host"],r["variant"]):r for r in old}
    identity={}
    for key in scalars[0]:
        identity[key]=sum(audit.rank(s[key],previous[r["host"],r["variant"]][key])
                          for r,s in zip(rows,scalars))/len(rows)
    unresolved=[r for r in checks if r["distinguished"] is not True]
    status="no_go_shortcuts" if blockers else ("hold_typed_review" if unresolved else "eligible_for_development_training")
    build.report(OUT/"typed_new_pairs.json",checks)
    build.report(OUT/"decision.json",dict(status=status,blockers=blockers,mixed=mixed,
                 generator_identity_new_higher=identity,typed_unresolved=unresolved,
                 training_performed=False,independent_hosts=len(HOSTS),records=len(rows),
                 representation="Yosys-emitted Verilog and typed cell graphs"))
    build.report(ROOT/"data/integrated/ver2_tier12_v3_catalog.json",dict(
                 previous_catalog="data/integrated/ver2_tier12_v2_catalog.json",cohorts=manifests,
                 decision=build.rel(OUT/"decision.json"),status=status,
                 admitted_development_records=len(rows) if status=="eligible_for_development_training" else 0,
                 split_unit="original host across all generators, edits and reference arms"))
    print(status, blockers, "typed unresolved",len(unresolved))


if __name__=="__main__":
    main()
