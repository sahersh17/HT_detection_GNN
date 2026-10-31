"""Prepare portable paired manifests while leaving large graphs compressed."""
import hashlib
import json
import zipfile
from collections import defaultdict

import config as C


def main():
    C.PAIRED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    C.EMB_ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(C.GRAPH_ZIP) as z:
        names = set(z.namelist())
        records = json.loads(z.read("results/fusion/pairs_portable.json"))
        usable = [r for r in records if not r["excluded"]]
        by_variant = defaultdict(list)
        for r in usable:
            by_variant[r["variant"]].append(r)
        paired = {b for b, rs in by_variant.items() if {r["label"] for r in rs} == {0, 1}}
        samples = []
        for r in usable:
            if r["variant"] not in paired:
                continue
            graph_path, emb_path = r["netlist_path"], r["embedding_path"]
            side = "clean" if r["label"] == 0 else "trojan"
            rtl_path = f"results/llm/rtl/{r['variant']}_{side}_rtl.v"
            for name in (graph_path, emb_path, rtl_path):
                if name not in names:
                    raise ValueError(f"Missing archive member: {name}")
            target = C.EMB_ROOT / emb_path.removeprefix("results/llm/embeddings/")
            target.write_bytes(z.read(emb_path))
            samples.append({
                "benchmark": r["variant"], "family": r["family"],
                "class_name": side, "label": r["label"],
                "graph_archive_path": graph_path,
                "rtl_embedding_path": target.name,
                "source_text_sha256": hashlib.sha256(z.read(rtl_path)).hexdigest(),
                "num_nodes": r["num_nodes"], "num_edges": r["num_edges"],
            })

    clean_hash = {s["benchmark"]: s["source_text_sha256"] for s in samples if s["label"] == 0}
    groups = defaultdict(list)
    for benchmark, digest in clean_hash.items():
        groups[digest].append(benchmark)
    if len(groups) < 2:
        raise ValueError("Need at least two distinct clean-source groups")
    folds = []
    all_benchmarks = set(clean_hash)
    for i, test_group in enumerate(sorted(groups.values(), key=lambda g: sorted(g)[0]), 1):
        test = sorted(test_group)
        folds.append({"fold": i, "train_benchmarks": sorted(all_benchmarks - set(test)),
                      "test_benchmarks": test})
    C.PAIRED_MANIFEST.write_text(json.dumps({"samples": samples}, indent=2), encoding="utf-8")
    C.FOLDS.write_text(json.dumps({"folds": folds}, indent=2), encoding="utf-8")
    print(f"Prepared {len(samples)} samples from {len(paired)} paired benchmarks; "
          f"{len(folds)} clean-source-held-out folds; {len(usable) - len(samples)} usable unpaired samples omitted.")


if __name__ == "__main__":
    main()
