"""Run the existing graph controls and source metadata probes on development hosts."""
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

import torch
from transformers import AutoTokenizer

from build import ROOT, OUT, RUN, digest, rel, report

sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from lofo_graph_baselines import fit_predict, stats, wl


def load_module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rank(a,b):
    return float(a>b)+0.5*(a==b)


def main(out=OUT, run_dir=RUN, catalog_name="ver2_catalog.json", graph_review=None):
    torch.set_num_threads(1)
    builder=load_module("graph_builder",ROOT/"pipeline/provenance/build.py")
    probes=load_module("matched_probes",ROOT/"experiments/matched_insertion_v3/controls.py")
    probes.OUT=run_dir
    tokenizer=AutoTokenizer.from_pretrained("microsoft/codebert-base",
            revision="3b0952feddeffad0063f274080e3c23d75e7eb39",local_files_only=True)
    manifest=out/"manifest.json"
    cohort=json.loads(manifest.read_text())
    rows=cohort["records"]
    features=[]
    scalars=[]
    for row in rows:
        folder=run_dir/row["host"]/row["variant"]
        src=ROOT/row["source"]
        if digest(src)!=row["sha256"] or digest(folder/"yosys.json")!=row["mapped_json_sha256"]:
            raise ValueError(f"Artifact integrity check failed for {src}")
        content=src.read_text()
        windows=len(tokenizer(content,truncation=True,max_length=512,stride=50,
                              return_overflowing_tokens=True)["input_ids"])
        graph,_=builder.graph_from_json(json.loads((folder/"yosys.json").read_text()),"top",row["host"],row["label"])
        torch.save(graph,folder/"graph.pt")
        size=[len(content),len(content.splitlines()),windows]
        meta=dict(**row,top="top")
        features.append(dict(source_metadata=torch.tensor(size).float(),graph_stats=stats(graph),
                gates=graph.x[:,:-4].sum(0),wl2=wl(graph),wl8=wl(graph,rounds=8),
                input_fanout=probes.input_fanout_motifs(meta),output_xor=probes.output_xor_motifs(meta),
                output_cone=probes.output_cone_equivalence(meta)))
        scalars.append(dict(characters=size[0],lines=size[1],windows=windows,nodes=graph.num_nodes,edges=graph.num_edges))
    hosts=sorted({r["host"] for r in rows})
    results={}
    blockers=[]
    for negative in ["clean","benign"]:
        pairs={}
        def record(name, scores):
            value=sum(scores.values())/len(scores)
            pairs[name]=dict(mean=value,by_host=scores)
            if max(value,1-value)>=0.90:
                blockers.append([negative,name,value])
        for name in scalars[0]:
            scores={}
            for host in hosts:
                pair={r["variant"]:s[name] for r,s in zip(rows,scalars) if r["host"]==host}
                scores[host]=rank(pair["trojan"],pair[negative])
            record(name,scores)
        for name in features[0]:
            matrix=torch.stack([f[name] for f in features])
            scores={}
            for fold,host in enumerate(hosts):
                train=[i for i,r in enumerate(rows) if r["host"]!=host and r["variant"] in (negative,"trojan")]
                test=[next(i for i,r in enumerate(rows) if (r["host"],r["variant"])==(host,v)) for v in (negative,"trojan")]
                labels=torch.tensor([rows[i]["label"] for i in train])
                a,b=fit_predict(matrix[train],labels,torch.ones(len(train)),matrix[test],42+fold)
                scores[host]=rank(b,a)
            record(name,scores)
        results[negative]=pairs
    decision="no_go_shortcuts" if blockers else "pending_independent_generator_and_review"
    supplementary = {}
    if graph_review is not None:
        comparisons = graph_review(out, run_dir)
        graph_report = out/"gate_graph_comparisons.json"
        report(graph_report, comparisons)
        collisions = [r for r in comparisons if r["isomorphic"] is True]
        supplementary = dict(gate_graph_comparisons=rel(graph_report), gate_graph_collisions=collisions)
        if collisions and not blockers:
            decision = "hold_for_gate_graph_collisions_and_independent_generator"
    report(out/"decision.json",dict(status=decision,controls=results,blockers=blockers,**supplementary,
           scalar_features=[dict(host=r["host"],variant=r["variant"],**s) for r,s in zip(rows,scalars)],
           constant_factors=["one language","one synthesis flow","one generator; generator-ID probe inapplicable"]))
    base=ROOT/"data/integrated/paired_manifest.json"
    catalogs=[dict(source="existing_paired",path=rel(base),sha256_lf_text=hashlib.sha256(base.read_text().encode()).hexdigest(),
                   records=len(json.loads(base.read_text())["samples"])),
              dict(source=cohort["generator"],path=rel(manifest),sha256=digest(manifest),records=len(rows),
                   status=decision,admitted_training_records=0)]
    report(ROOT/"data/integrated"/catalog_name,dict(cohorts=catalogs,
           evaluation="Separate cohorts. Group synthetic rows by clean host. Existing folds apply only to existing data.",
           decision=rel(out/"decision.json")))
    print(decision,blockers)


if __name__=="__main__":
    main()
