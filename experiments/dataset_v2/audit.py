"""Check the frozen dataset views and report graph-size shortcut risk."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/dataset_v2"


def read(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def auc(rows, field):
    pos = [r[field] for r in rows if r["label"] == 1]
    neg = [r[field] for r in rows if r["label"] == 0]
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    rows, primary = read("registry.json"), read("trusthub_primary.json")
    balanced, hard, native = (set(read(n)) for n in
                              ("balanced_mixed_keys.json", "hard_negative_keys.json", "native_edit_keys.json"))
    folds = read("trusthub_folds.json")["folds"]
    by_key = {r["key"]: r for r in rows}
    assert len(by_key) == len(rows) == 279
    assert len({r["graph_sha256"] for r in rows}) == len(rows)
    assert {r["key"] for r in primary} == {r["key"] for r in rows if r["source"] == "trusthub_benchmark"}
    assert Counter(r["label"] for r in primary) == {0: 49, 1: 49}
    assert len(balanced) == 224 and Counter(by_key[k]["label"] for k in balanced) == {0: 112, 1: 112}
    assert len(hard) == 55 and not (hard & balanced)
    assert all(by_key[k]["label"] == 0 for k in hard)
    assert len(native) == 147 and all(by_key[k]["cohort"] == "native" for k in native)
    assert balanced | hard == set(by_key)
    assert len(folds) == 5 and {k for f in folds for k in f["test_keys"]} == {r["key"] for r in primary}
    for f in folds:
        assert not set(f["test_keys"]) & set(f["train_keys"])
        assert not {by_key[k]["family"] for k in f["test_keys"]} & {by_key[k]["family"] for k in f["train_keys"]}
        assert Counter(by_key[k]["label"] for k in f["test_keys"]) == {0: f["test_negative"], 1: f["test_positive"]}
    pairs = defaultdict(dict)
    for r in primary:
        pairs[r["benchmark"]][r["label"]] = r
    assert len(pairs) == 49 and all(set(p) == {0, 1} for p in pairs.values())
    size_sign = Counter("positive_larger" if p[1]["graph_nodes"] > p[0]["graph_nodes"]
                        else "positive_smaller" if p[1]["graph_nodes"] < p[0]["graph_nodes"]
                        else "equal" for p in pairs.values())
    family_fingerprints = {family: len({r["source_bundle_sha256"] for r in primary
                                        if r["family"] == family and r["label"] == 0})
                           for family in sorted({r["family"] for r in primary})}
    report = {
        "trusthub_primary": {"circuits": 98, "negative": 49, "positive": 49,
                             "families": len(family_fingerprints),
                             "distinct_clean_source_bundles": len({r["source_bundle_sha256"] for r in primary if r["label"] == 0}),
                             "clean_source_bundles_by_family": family_fingerprints},
        "balanced_mixed": {"circuits": 224, "negative": 112, "positive": 112},
        "full_registry": {"circuits": 279, "negative": 167, "positive": 112},
        "trusthub_size_control": {"node_count_auc_untrained": auc(primary, "graph_nodes"),
                                  "edge_count_auc_untrained": auc(primary, "graph_edges"),
                                  "paired_node_count_sign": dict(size_sign)},
        "fold_test_balance": [{"fold": f["fold"], "families": f["test_families"],
                               "negative": f["test_negative"], "positive": f["test_positive"]} for f in folds],
        "conclusion": "Class balance and family separation pass. Size, repeated hosts, synthesis flow, and unverified attack behavior remain limitations.",
    }
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    path = DATA / "audit.json"
    if path.exists() and path.read_text(encoding="utf-8") != output:
        raise ValueError(f"Refusing to overwrite changed dataset audit: {path}")
    path.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
