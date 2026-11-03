"""Rebuild and verify the recorded corpus using the semantic graph representation."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"pipeline/provenance"))
from build import graph_from_json
from semantic import NODE_DIM, SCHEMA_SHA256, verify_semantic_values

RUN = ROOT/"runs/semantic_graph_v1"
OUT = ROOT/"data/semantic_graph_v1"


def read(path):
    return json.loads(path.read_bytes())


def source_path(row, lookup):
    host, side = row["host"], row["variant"]
    if row["cohort"] == "baseline":
        return ROOT/f"runs/overlap_v1/{host}/{side}/yosys.json"
    if row["cohort"] == "native":
        return ROOT/f"runs/precision_v1/hosts/{host}/{side}/yosys.json"
    if row["cohort"] == "test":
        folder = "expansion_graphs" if host == "memctrl" else "expansion_pic_graphs"
        return ROOT/f"runs/{folder}/{row['key'].removeprefix('test_').removesuffix('_'+side)}/{side}/yosys.json"
    benchmark = row["key"].removeprefix(row["cohort"]+"_").removesuffix("_"+side)
    return ROOT/lookup[benchmark,side]["mapped"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    torch.set_num_threads(2)
    lookup = {}
    for path in (ROOT/"data/transfer_v1/intake.json",ROOT/"data/augmentation_v2/intake.json"):
        lookup.update({(r.get("benchmark", r["host"]),r["variant"]):r for r in read(path)["records"]})
    rows = read(ROOT/"data/training_audit_v3/manifest.json")["records"]
    if not args.all:
        rows = [r for r in rows if r["host"] == "tt_um_rejunity_decoder"]
    prepared = RUN/"prepared"
    prepared.mkdir(exist_ok=True)
    records = []
    pair = {}
    for row in rows:
        path = source_path(row,lookup)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["mapped_sha256"]:
            raise ValueError(str(path))
        document = json.loads(raw)
        original = torch.load(ROOT/row["file"],weights_only=False)
        # Flattened netlists retain one top module in every recorded design.
        if row["cohort"] in ("baseline","native"):
            version = "overlap_six_v1" if row["cohort"]=="baseline" else "precision_v1"
            top = next(r["top"] for r in read(ROOT/f"data/{version}/manifest.json")["records"]
                       if r["host"]==row["host"] and r["variant"]==row["variant"])
        elif row["cohort"] == "test":
            top = "mc_top" if row["host"]=="memctrl" else "pic_16f84_core"
        else:
            benchmark = row["key"].removeprefix(row["cohort"]+"_").removesuffix("_"+row["variant"])
            top = lookup[benchmark,row["variant"]]["top"]
        graph,meta = graph_from_json(document,top,"semantic_v1/"+row["key"],row["label"],
                                     representation="semantic_v1")
        check = verify_semantic_values(document,top,graph,meta)
        target = prepared/(row["key"]+".pt")
        metadata = prepared/(row["key"]+".json")
        item = dict(original,graph=graph)
        torch.save(item,target)
        metadata.write_text(json.dumps(meta))
        records.append(dict(row,file=target.relative_to(ROOT).as_posix(),
                            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                            metadata=metadata.relative_to(ROOT).as_posix(),
                            mapped_json=path.relative_to(ROOT).as_posix(),
                            source_prepared_file=row["file"], source_prepared_sha256=row["sha256"],
                            rtl_tensor_sha256=hashlib.sha256(original["rtl"].contiguous().numpy().tobytes()).hexdigest(),
                            representation="semantic_v1",nodes=graph.num_nodes,edges=graph.num_edges,
                            checked=check))
        records[-1]["source_embedding_sha256"] = records[-1].pop("embedding_sha256", None)
        if row["host"]=="tt_um_rejunity_decoder":
            pair[row["variant"]] = (original["graph"],graph,meta)
        print(row["key"],graph.num_nodes,graph.num_edges,check,flush=True)
    report = dict(representation="semantic_v1",schema_sha256=SCHEMA_SHA256,node_dim=NODE_DIM,records=records)
    if "benign" in pair and "trojan" in pair:
        old_a,a,meta_a=pair["benign"]
        old_b,b,meta_b=pair["trojan"]
        legacy_equal = torch.equal(old_a.x,old_b.x) and torch.equal(old_a.edge_index,old_b.edge_index)
        def histogram(g):
            return Counter(row.tobytes() for row in g.x.numpy())
        new_distinct=histogram(a)!=histogram(b)
        if not legacy_equal or not new_distinct:
            raise ValueError("Known collision was not repaired")
        # Cell/graph IDs and labels never enter this feature multiset comparison.
        perm=torch.randperm(a.num_nodes)
        shuffled=a.clone()
        shuffled.x=a.x[perm]
        inverse=torch.empty_like(perm)
        inverse[perm]=torch.arange(a.num_nodes)
        shuffled.edge_index=inverse[a.edge_index]
        assert histogram(shuffled)==histogram(a)
        assert histogram(shuffled)!=histogram(b)
        report["known_pair"]=dict(legacy_identical=True,semantic_distinguished=True,
                                  permutation_invariant=True,
                                  benign_nodes=a.num_nodes,fault_nodes=b.num_nodes,
                                  checked_bits=[next(r["checked"]["bits"] for r in records if r["host"]=="tt_um_rejunity_decoder" and r["variant"]==side) for side in ("benign","trojan")])
    (OUT/("manifest.json" if args.all else "pair_verification.json")).write_text(json.dumps(report,indent=2))
    print("VERIFIED",len(records),report.get("known_pair"),flush=True)


if __name__=="__main__":
    main()
