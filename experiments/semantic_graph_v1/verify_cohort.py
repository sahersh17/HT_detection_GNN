"""Independently verify saved semantic tensors against their original netlists."""
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"pipeline/provenance"))
from semantic import NODE_DIM,SCHEMA_SHA256,verify_semantic_values
from prepare import source_path

OUT=ROOT/"data/semantic_graph_v1"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    torch.set_num_threads(2)
    manifest=read(OUT/"manifest.json")
    lookup={}
    for path in (ROOT/"data/transfer_v1/intake.json",ROOT/"data/augmentation_v2/intake.json"):
        lookup.update({(r.get("benchmark",r["host"]),r["variant"]):r for r in read(path)["records"]})
    totals=dict(graphs=0,nodes=0,edges=0,bits=0,memory_states=0,memory_operations=0,initial_bits=0)
    hashes={}
    for row in manifest["records"]:
        path=ROOT/row["file"]
        if sha(path)!=row["sha256"]:
            raise ValueError("Prepared graph hash mismatch")
        item=torch.load(path,weights_only=False)
        original_path=ROOT/row["source_prepared_file"]
        if sha(original_path)!=row["source_prepared_sha256"]:
            raise ValueError("Original prepared item changed")
        original=torch.load(original_path,weights_only=False)
        if not torch.equal(original["rtl"],item["rtl"]):
            raise ValueError("RTL embeddings changed during graph repair")
        row["rtl_tensor_sha256"]=hashlib.sha256(item["rtl"].contiguous().numpy().tobytes()).hexdigest()
        for name,expected in row["source_sha256"].items():
            if name not in hashes:
                hashes[name]=sha(ROOT/name)
            if hashes[name]!=expected:
                raise ValueError("RTL source changed")
        mapped=source_path(row,lookup)
        if sha(mapped)!=row["mapped_sha256"]:
            raise ValueError("Mapped netlist changed")
        row["mapped_json"]=mapped.relative_to(ROOT).as_posix()
        document=read(mapped)
        metadata=read(ROOT/row["metadata"])
        if metadata["schema_sha256"]!=SCHEMA_SHA256 or metadata["node_dim"]!=NODE_DIM:
            raise ValueError("Semantic schema mismatch")
        graph=item["graph"]
        graph.validate(raise_on_error=True)
        if not torch.isfinite(graph.x).all() or graph.x.shape[1]!=NODE_DIM:
            raise ValueError("Invalid model features")
        if item["label"]!=row["label"] or int(graph.y.item())!=row["label"]:
            raise ValueError("Label mismatch")
        # Explicit tops follow the retained source manifest, not class or graph IDs.
        if row["cohort"] in ("baseline","native"):
            version="overlap_six_v1" if row["cohort"]=="baseline" else "precision_v1"
            top=next(r["top"] for r in read(ROOT/f"data/{version}/manifest.json")["records"]
                     if r["host"]==row["host"] and r["variant"]==row["variant"])
        elif row["cohort"]=="test":
            top="mc_top" if row["host"]=="memctrl" else "pic_16f84_core"
        else:
            benchmark=row["key"].removeprefix(row["cohort"]+"_").removesuffix("_"+row["variant"])
            top=lookup[benchmark,row["variant"]]["top"]
        verified=verify_semantic_values(document,top,graph,metadata)
        if verified!=row["checked"]:
            raise ValueError("Semantic coverage mismatch")
        totals["graphs"]+=1
        totals["nodes"]+=graph.num_nodes
        totals["edges"]+=graph.num_edges
        for key in ("bits","memory_states","memory_operations","initial_bits"):
            totals[key]+=verified[key]
    manifest["representation"]="semantic_v1"
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
    pair=read(OUT/"pair_verification.json")
    pair["records"]=[r for r in manifest["records"] if r["host"]=="tt_um_rejunity_decoder"]
    pair["representation"]="semantic_v1"
    (OUT/"pair_verification.json").write_text(json.dumps(pair,indent=2))
    totals.update(status="verified",node_dim=NODE_DIM,schema_sha256=SCHEMA_SHA256,
                  rtl_embeddings_identical=True,source_netlists_unchanged=True,
                  manifest_sha256=sha(OUT/"manifest.json"))
    (OUT/"verification.json").write_text(json.dumps(totals,indent=2))
    print(totals)


if __name__=="__main__":
    main()
