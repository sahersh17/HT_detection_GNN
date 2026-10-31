"""Gate for new data: run this on every data drop BEFORE training. Exit code 1 = do not train.
Usage: python audit_data.py [--dff-col N]
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict

import config as C

problems, warns = [], []


def fail(msg):
    problems.append(msg)


def warn(msg):
    warns.append(msg)


def load_graph(z, name):
    import torch
    from torch_geometric.data import Data
    from torch_geometric.data.data import DataEdgeAttr, DataTensorAttr
    from torch_geometric.data.storage import GlobalStorage
    with torch.serialization.safe_globals([Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]):
        return torch.load(io.BytesIO(z.read(name)), map_location="cpu", weights_only=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dff-col", type=int, default=C.DFF_COL)
    args = ap.parse_args()
    import torch

    samples = json.loads(C.PAIRED_MANIFEST.read_text(encoding="utf-8"))["samples"]
    folds = json.loads(C.FOLDS.read_text(encoding="utf-8"))["folds"]
    print(f"samples={len(samples)} labels={dict(Counter(s['label'] for s in samples))}")

    # pairing: every benchmark needs exactly one clean + one Trojan sample
    by_b = defaultdict(set)
    for s in samples:
        by_b[s["benchmark"]].add(s["label"])
    for b, labels in by_b.items():
        if labels != {0, 1}:
            fail(f"{b}: labels {sorted(labels)} (need one clean + one Trojan)")

    # folds: no benchmark overlap, no clean-RTL source shared between train and test
    seen_test = Counter()
    for f in folds:
        tr, te = set(f["train_benchmarks"]), set(f["test_benchmarks"])
        if tr & te:
            fail(f"fold {f['fold']}: benchmark overlap {sorted(tr & te)}")
        tr_h = {s["source_text_sha256"] for s in samples if s["benchmark"] in tr and s["label"] == 0}
        te_h = {s["source_text_sha256"] for s in samples if s["benchmark"] in te and s["label"] == 0}
        if tr_h & te_h:
            fail(f"fold {f['fold']}: clean RTL source shared between train and test (leakage)")
        seen_test.update(te)
    if any(v != 1 for v in seen_test.values()):
        fail("a benchmark is tested in != 1 fold")

    # RTL embeddings
    digests, chunks = defaultdict(list), Counter()
    for s in samples:
        p = C.EMB_ROOT / s["rtl_embedding_path"]
        if not p.is_file():
            fail(f"missing embedding {p}")
            continue
        t = torch.load(p, map_location="cpu", weights_only=True)
        if t.ndim != 2 or t.shape[1] != C.RTL_DIM:
            fail(f"{p.name}: bad shape {tuple(t.shape)}")
            continue
        if not torch.isfinite(t).all():
            fail(f"{p.name}: NaN/Inf")
        chunks[t.shape[0]] += 1
        digests[hashlib.sha256(t.float().numpy().tobytes()).hexdigest()].append((s["benchmark"], s["label"]))
    print(f"chunk-count distribution: {dict(sorted(chunks.items()))}")
    if chunks and max(chunks) <= 2:
        fail("all designs have <=2 chunks: windowing bug not fixed (expect ~30)")
    n_src = len({s["source_text_sha256"] for s in samples})
    print(f"unique embeddings={len(digests)} unique RTL source texts={n_src}")
    if len(digests) < n_src:
        warn(f"{n_src - len(digests)} distinct RTL texts collapsed to identical embeddings "
             "(Trojan code outside the embedded windows?)")
    for g in digests.values():
        if len({lab for _, lab in g}) > 1:
            fail(f"identical embedding for both labels: {g[:4]}")

    # graphs
    z = zipfile.ZipFile(C.GRAPH_ZIP)
    names = {n.replace("\\", "/"): n for n in z.namelist()}
    graphs = {}
    for s in samples:
        key = s["graph_archive_path"].replace("\\", "/")
        if key not in names:
            fail(f"missing graph {key}")
            continue
        g = load_graph(z, names[key])
        if g.x.ndim != 2 or g.x.shape[1] != C.NODE_DIM:
            fail(f"{key}: x shape {tuple(g.x.shape)}")
            continue
        if not torch.isfinite(g.x.float()).all():
            fail(f"{key}: NaN/Inf in x")
        if int(g.y.item()) != s["label"]:
            fail(f"{key}: y={int(g.y.item())} != manifest label {s['label']}")
        graphs[(s["benchmark"], s["label"])] = g
        if args.dff_col is not None and g.x[:, args.dff_col].sum() == 0:
            fail(f"{key}: no flip-flop nodes in column {args.dff_col}")
    if args.dff_col is None and graphs:
        g = next(iter(graphs.values()))
        print("DFF column not set. Per-column feature sums of one graph "
              "(identify the DFF column, then rerun with --dff-col):")
        print([round(float(v), 1) for v in g.x.sum(0)])
    smaller = [b for (b, lab), g in graphs.items()
               if lab == 1 and (b, 0) in graphs and g.num_nodes < graphs[(b, 0)].num_nodes]
    if smaller:
        warn(f"{len(smaller)} Trojan graphs have FEWER nodes than their clean pair "
             f"(different synthesis flow?): {smaller[:6]}")
    print("most common graph node counts:", dict(Counter(g.num_nodes for g in graphs.values()).most_common(5)))

    for w in warns:
        print("WARN:", w)
    for p in problems:
        print("FAIL:", p)
    print("AUDIT", "FAILED" if problems else "PASSED")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
