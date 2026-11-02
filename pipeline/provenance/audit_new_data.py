"""Create a model-ready cohort manifest and exercise every new graph."""
import json
import sys
from collections import Counter
from pathlib import Path
import torch
from torch_geometric.data import Data
from torch_geometric.data.data import DataEdgeAttr, DataTensorAttr
from torch_geometric.data.storage import GlobalStorage
from build import ROOT, sha256
from verify import verify_one
from verify_new_archives import verify as verify_archives

sys.path.insert(0, str(ROOT / "pipeline"))
from models import GNNOnly, CrossAttentionFusion


def main():
    torch.set_num_threads(4)
    torch.manual_seed(42)
    archive_summary = verify_archives()
    model = GNNOnly().eval()
    rows = []
    for version in ("new_gate_v1", "new_vhdl_v1"):
        for path in sorted((ROOT / "runs" / version).glob("*-T*/*/metadata.json")):
            folder = path.parent
            status_path = folder / "synthesis_status.json"
            if status_path.exists() and json.loads(status_path.read_text())["status"] != "graph_built_unreviewed":
                continue
            verified = verify_one(folder)
            meta = json.loads(path.read_text())
            with torch.serialization.safe_globals([Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]):
                graph = torch.load(folder / "graph.pt", weights_only=True)
            if not torch.isfinite(graph.x).all() or int(graph.y.item()) != int(meta["side"] == "trojan"):
                raise ValueError(f"Invalid features/label: {folder}")
            with torch.inference_mode():
                logits = model(graph)["logits"]
            if logits.shape != (1, 2) or not torch.isfinite(logits).all():
                raise ValueError(f"GNN forward failed: {folder}")
            for adaptation in meta.get("adaptations", []):
                if sha256(ROOT / adaptation["adapted"]) != adaptation["sha256"]:
                    raise ValueError("Adapted synthesis source hash changed")
            rows.append({"benchmark": meta["benchmark"], "side": meta["side"],
                         "family": meta["benchmark"].split("-")[0], "label": int(graph.y.item()),
                         "graph": (folder / "graph.pt").relative_to(ROOT).as_posix(),
                         "graph_sha256": sha256(folder / "graph.pt"),
                         "source_level": verified["source_level"], "nodes": graph.num_nodes,
                         "edges": graph.num_edges, "gnn_forward": "passed",
                         "split_group": meta["benchmark"].split("-")[0]})
    for row in rows:
        row["paired"] = any(r["benchmark"] == row["benchmark"] and r["side"] != row["side"] for r in rows)
    embeddings_path = ROOT / "runs/new_rtl_v1/manifest.json"
    if not embeddings_path.exists():
        raise ValueError("VHDL embeddings must finish before final cohort audit")
    from verify_rtl import verify as verify_rtl
    embedding_summary = verify_rtl(embeddings_path.parent, new_vhdl=True)
    embeddings = json.loads(embeddings_path.read_text())["records"]
    for row in rows:
        found = [e for e in embeddings if (e["benchmark"], e["side"]) == (row["benchmark"], row["side"])]
        row["rtl_embedding"] = (embeddings_path.parent / found[0]["embedding_file"]).relative_to(ROOT).as_posix() if found else None
    fusion = CrossAttentionFusion().eval()
    fusion_checks = []
    for row in rows:
        if row["benchmark"] != "MC8051-T200":
            continue
        with torch.serialization.safe_globals([Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]):
            graph = torch.load(ROOT / row["graph"], weights_only=True)
        rtl = torch.load(ROOT / row["rtl_embedding"], weights_only=True)
        with torch.inference_mode():
            result = fusion(graph, rtl)
        if result["logits"].shape != (1, 2) or not all(torch.isfinite(t).all() for t in result.values()):
            raise ValueError("Fusion model compatibility test failed")
        fusion_checks.append(f'{row["benchmark"]}/{row["side"]}')
    failures = [json.loads(p.read_text()) for p in (ROOT / "runs/new_vhdl_v1").glob("*-T*/*/synthesis_status.json")
                if json.loads(p.read_text())["status"] != "graph_built_unreviewed"]
    result = {"status": "verified", "archive_audit": archive_summary, "embedding_audit": embedding_summary,
              "graphs": len(rows), "paired_benchmarks": len({r["benchmark"] for r in rows if r["paired"]}),
              "family_graph_counts": dict(Counter(r["family"] for r in rows)),
              "host_family_groups": len({r["split_group"] for r in rows}), "reviewed_gate_labels": 0,
              "model_check": "untrained GNN forward compatibility only; no accuracy measurement",
              "full_fusion_forward_checks": fusion_checks,
              "split_policy": "Keep every variant of a host family together; no new train/test split assigned",
              "synthesis_failures": failures, "samples": rows}
    out = ROOT / "data/new_trusthub"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cohort_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "synthesis_failures")}, indent=2))


if __name__ == "__main__":
    main()
