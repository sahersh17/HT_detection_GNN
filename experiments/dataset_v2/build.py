"""Curate a balanced, graph-only Trust-Hub development panel and full registry."""
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/dataset_v2"
torch.set_num_threads(2)
QUARANTINED = {"s38584-T300": "Unresolved trigger-to-payload connection; see docs/LOCALIZATION_LABEL_AUDIT.md"}


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def locked_write(path, content):
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"Refusing to overwrite changed dataset lock: {path}")
    path.write_text(content, encoding="utf-8")


def source_digest(sources):
    # Contents, rather than variant-specific source path names, identify repeats.
    return hashlib.sha256(json.dumps(sorted(sources.values())).encode()).hexdigest()


def verify_graph(graph, expected_label, expected_nodes=None):
    if graph.x.ndim != 2 or graph.x.shape[1] != 20 or not torch.isfinite(graph.x).all():
        raise ValueError("Incompatible graph feature schema")
    if not torch.allclose(graph.x[:, :16].sum(1), torch.ones(graph.num_nodes)):
        raise ValueError("Invalid gate class one-hot features")
    if expected_nodes is not None and graph.num_nodes != expected_nodes:
        raise ValueError("Graph node count differs from metadata")
    if graph.edge_index.ndim != 2 or graph.edge_index.shape[0] != 2:
        raise ValueError("Invalid edge index")
    if graph.num_edges and (int(graph.edge_index.min()) < 0 or int(graph.edge_index.max()) >= graph.num_nodes):
        raise ValueError("Edge index out of bounds")
    if hasattr(graph, "y") and int(graph.y.flatten()[0]) != expected_label:
        raise ValueError("Graph label mismatch")


def stage1_record(row, manifest, source_cache):
    m = manifest[row["key"]]
    path = ROOT / m["file"]
    if digest(path) != row["prepared_sha256"] or m["sha256"] != row["prepared_sha256"]:
        raise ValueError(f"Prepared hash mismatch: {row['key']}")
    sample = torch.load(path, weights_only=False, map_location="cpu")
    if sample["label"] != row["label"] or sample["host"] != row["host"]:
        raise ValueError(f"Prepared identity mismatch: {row['key']}")
    graph = sample["graph"]
    verify_graph(graph, row["label"], row["legacy_nodes"])
    for rel, expected in m["source_sha256"].items():
        if rel not in source_cache:
            source_cache[rel] = digest(ROOT / rel)
        actual = source_cache[rel]
        if actual != expected:
            raise ValueError(f"Source hash mismatch: {rel}")
    return {
        "key": row["key"], "source": "constructed_development", "cohort": row["cohort"],
        "family": row["host"], "benchmark": row["benchmark"], "variant": row["variant"],
        "label": row["label"], "graph_file": m["file"], "graph_sha256": m["sha256"],
        "graph_nodes": graph.num_nodes, "graph_edges": graph.num_edges,
        "source_bundle_sha256": source_digest(m["source_sha256"]),
        "source_files_sha256": m["source_sha256"], "synthesis_flow": row["synthesis_flow"],
        "mechanism_family": row["mechanism_family"],
        "label_scope": "constructed edit or fault; not a Trust-Hub attack",
        "available_modalities": ["legacy_20_feature_graph", "frozen_rtl_embedding"],
        "group_id": "owner:" + row["source_owner"],
    }


def trusthub_record(row, source_cache):
    path = ROOT / row["path"]
    if digest(path) != row["sha256"]:
        raise ValueError(f"Trust-Hub graph hash mismatch: {path}")
    meta_path = path.with_name("metadata.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta["label"] != row["label"] or meta["benchmark"] != row["benchmark"]:
        raise ValueError(f"Trust-Hub metadata mismatch: {path}")
    for rel, expected in meta["sources"].items():
        if rel not in source_cache:
            source_cache[rel] = digest(ROOT / rel)
        actual = source_cache[rel]
        if actual != expected:
            raise ValueError(f"Source hash mismatch: {rel}")
    graph = torch.load(path, weights_only=False, map_location="cpu")
    verify_graph(graph, row["label"], meta["num_nodes"])
    return {
        "key": "trusthub_" + row["benchmark"] + "_" + row["side"],
        "source": "trusthub_benchmark", "cohort": "trusthub", "family": row["family"],
        "benchmark": row["benchmark"], "variant": row["side"], "label": row["label"],
        "graph_file": row["path"], "graph_sha256": row["sha256"],
        "graph_nodes": graph.num_nodes, "graph_edges": graph.num_edges,
        "source_bundle_sha256": source_digest(meta["sources"]),
        "source_files_sha256": meta["sources"], "synthesis_flow": meta["synthesis_flow"],
        "mechanism_family": "not_independently_classified",
        "label_scope": "original Trust-Hub benchmark label; behavior not independently checked for every pair",
        "available_modalities": ["legacy_20_feature_graph"],
        "group_id": "trusthub_family:" + row["family"],
    }


def family_folds(primary):
    by_family = defaultdict(list)
    for row in primary:
        by_family[row["family"]].append(row)
    buckets = [[] for _ in range(5)]
    pair_counts = [0] * 5
    for family in sorted(by_family, key=lambda f: (-len(by_family[f]), f)):
        target = min(range(5), key=lambda i: (pair_counts[i], len(buckets[i]), i))
        buckets[target].append(family)
        pair_counts[target] += len(by_family[family]) // 2
    folds = []
    for i, families in enumerate(buckets):
        test = sorted((r["key"] for r in primary if r["family"] in families))
        train = sorted((r["key"] for r in primary if r["family"] not in families))
        labels = Counter(r["label"] for r in primary if r["family"] in families)
        assert labels[0] == labels[1]
        folds.append({"fold": i, "test_families": sorted(families), "test_keys": test,
                      "train_keys": train, "test_negative": labels[0], "test_positive": labels[1]})
    assert len(set().union(*(set(f["test_keys"]) for f in folds))) == len(primary)
    return {"purpose": "development leave-Trust-Hub-family-out folds; previously inspected, no final-test claim",
            "groups": "Trust-Hub clean host family", "folds": folds}


def csv_text(records):
    fields = ["key", "source", "cohort", "family", "benchmark", "variant", "label",
              "graph_file", "graph_sha256", "graph_nodes", "graph_edges", "source_bundle_sha256",
              "synthesis_flow", "mechanism_family", "label_scope", "group_id"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in records:
        writer.writerow({key: row[key] for key in fields})
    return buffer.getvalue()


def main():
    source_cache = {}
    input_stage1 = ROOT / "data/dataset_stage1/records.json"
    input_trusthub = ROOT / "data/lofo_expanded_b19/protocol.json"
    stage1 = read("data/dataset_stage1/records.json")
    manifest = {r["key"]: r for r in read("data/training_audit_v3/manifest.json")["records"]}
    original = read("data/lofo_expanded_b19/protocol.json")["samples"]
    constructed = [r for r in stage1 if r["role"] == "development" and r["cohort"] != "external_authored"]
    trusthub = [r for r in original if r["benchmark"] not in QUARANTINED]
    assert len(constructed) == 181 and len(trusthub) == 98
    rows = []
    for i, row in enumerate(constructed):
        rows.append(stage1_record(row, manifest, source_cache))
        if (i + 1) % 40 == 0:
            print(f"Verified {i+1}/{len(constructed)} constructed records", flush=True)
    for i, row in enumerate(trusthub):
        rows.append(trusthub_record(row, source_cache))
        if (i + 1) % 20 == 0:
            print(f"Verified {i+1}/{len(trusthub)} Trust-Hub records", flush=True)
    rows.sort(key=lambda r: r["key"])
    assert len(rows) == len({r["key"] for r in rows}) == 279
    by_benchmark = defaultdict(list)
    for row in rows:
        if row["source"] == "trusthub_benchmark":
            by_benchmark[row["benchmark"]].append(row)
    assert len(by_benchmark) == 49 and all(Counter(r["label"] for r in pair) == {0: 1, 1: 1} for pair in by_benchmark.values())
    primary = [r for r in rows if r["source"] == "trusthub_benchmark"]
    native = [r for r in rows if r["cohort"] == "native"]
    full_labels = Counter(r["label"] for r in rows)
    assert len(primary) == 98 and Counter(r["label"] for r in primary) == {0: 49, 1: 49}
    assert full_labels == {0: 167, 1: 112} and len(native) == 147
    # Balanced mixed training view: preserve one original clean per constructed
    # host, retain both negatives on the four two-positive four-project hosts,
    # and retain every paired Trust-Hub clean. All other benign variants stay
    # in the full registry as a separate hard-negative evaluation pool.
    balanced = [r for r in rows if r["label"] == 1 or r["source"] == "trusthub_benchmark"
                or r["variant"] == "clean" or (r["cohort"] == "four_projects" and r["variant"] == "benign")]
    assert len(balanced) == 224 and Counter(r["label"] for r in balanced) == {0: 112, 1: 112}
    excluded_negative = sorted(r["key"] for r in rows if r["label"] == 0 and r["key"] not in {x["key"] for x in balanced})
    assert len(excluded_negative) == 55
    primary.sort(key=lambda r: r["key"])
    folds = family_folds(primary)
    summary = {
        "status": "balanced_graph_only_development_dataset_locked",
        "full_registry": {"circuits": len(rows), "negative": full_labels[0], "positive": full_labels[1],
                          "host_families": len({r["family"] for r in rows}),
                          "source_lineage_groups": len({r["group_id"] for r in rows})},
        "trusthub_primary": {"circuits": len(primary), "negative": 49, "positive": 49,
                             "pairs": 49, "families": dict(sorted(Counter(r["family"] for r in primary if r["label"] == 1).items())),
                             "clean_source_bundle_fingerprints": len({r["source_bundle_sha256"] for r in primary if r["label"] == 0})},
        "balanced_mixed_training_view": {"circuits": len(balanced), "negative": 112, "positive": 112,
                                          "removed_benign_negative_records": len(excluded_negative)},
        "quarantined_pairs": QUARANTINED,
        "duplicate_handling": "The original Stage-1 RS232-T2100/T2200 copies are replaced by their Trust-Hub pool records, never counted twice.",
        "native_edit_records_separate_from_primary": len(native),
        "source_files_verified": len(source_cache),
        "input_sha256": {"data/dataset_stage1/records.json": digest(input_stage1),
                         "data/lofo_expanded_b19/protocol.json": digest(input_trusthub)},
        "claim_limits": ["All Trust-Hub families here have already been inspected during development.",
                         "Trust-Hub labels and pairs are source/hash verified; Trojan-on behavior and matched benign decoys are not independently verified for all pairs.",
                         "Mixed synthesis flows and repeated clean designs remain. Leave entire family out for evaluation.",
                         "Trust-Hub primary is graph-only; do not silently fill missing RTL embeddings.",
                         "Balanced training view omits 55 benign decoys; evaluate those hard negatives separately from training balance.",
                         "No untouched final test is admitted."],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "registry.json": canonical(rows), "registry.csv": csv_text(rows),
        "trusthub_primary.json": canonical(primary), "trusthub_primary.csv": csv_text(primary),
        "balanced_mixed_keys.json": canonical(sorted(r["key"] for r in balanced)),
        "hard_negative_keys.json": canonical(excluded_negative),
        "native_edit_keys.json": canonical(sorted(r["key"] for r in native)),
        "trusthub_folds.json": canonical(folds), "summary.json": canonical(summary),
    }
    for name, content in files.items():
        locked_write(OUT / name, content)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
