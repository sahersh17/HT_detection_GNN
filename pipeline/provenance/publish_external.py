"""Publish and verify the frozen, two-host-family detection diagnostic.

The small test is intentionally called a diagnostic. Its 10 samples come from
only two independent clean host designs and it has no reviewed gate labels.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402
from train_external import EXPANSION, samples  # noqa: E402

DEST = ROOT / "results" / "external_diagnostic"
MODELS = ("rtl", "gnn", "fusion", "length")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inputs():
    paths = [ROOT / "data" / "integrated" / "paired_manifest.json"]
    for folder in (ROOT / "runs" / "rtl_clean_v1", ROOT / "runs" / "rtl_expansion_v1"):
        paths += [folder / "manifest.json", folder / "verification.json"]
        paths += sorted(folder.glob("*.pt"))
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        paths += [ROOT / source for record in manifest["records"] for source in record["sources"]]
    for folder in (ROOT / "runs" / name for name in
                   ("provenance_v1", "expansion_graphs", "expansion_pic_graphs")):
        paths += sorted(folder.rglob("graph.pt"))
        paths += sorted(folder.rglob("metadata.json"))
        paths += sorted(folder.rglob("yosys.json"))
    return sorted(set(paths))


def check_model(model, folder):
    rows = json.loads((folder / "predictions.json").read_text(encoding="utf-8"))
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    expected = {(benchmark, label) for benchmark in EXPANSION for label in (0, 1)}
    actual = [(r["benchmark"], r["true_label"]) for r in rows]
    if len(rows) != 10 or set(actual) != expected or len(set(actual)) != len(actual):
        raise ValueError(f"{model}: test samples do not match the frozen protocol")
    for row in rows:
        p = row["prob_trojan"]
        if not isinstance(p, (float, int)) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError(f"{model}: invalid probability")
        if row["predicted_label"] != int(p >= 0.5):
            raise ValueError(f"{model}: threshold mismatch")
    calculated = summarize_predictions(rows)
    for section in calculated:
        if summary[section] != calculated[section]:
            raise ValueError(f"{model}: saved {section} metrics disagree with rows")
    if summary["args"]["model"] != model or summary["seed"] != 42:
        raise ValueError(f"{model}: protocol mismatch")
    for family in ("memctrl", "PIC16F84"):
        expected_family = summarize_predictions([r for r in rows if r["family"] == family])["pooled"]
        if summary[f"family_{family}"] != expected_family:
            raise ValueError(f"{model}: {family} metrics disagree with rows")
    return summary["pooled"]


def publish():
    samples()  # Enforce clean-source train/test disjointness.
    for name, count in (("rtl_clean_v1", 42), ("rtl_expansion_v1", 10)):
        record = json.loads((ROOT / "runs" / name / "verification.json").read_text(encoding="utf-8"))
        if record["status"] != "verified" or record["samples"] != count:
            raise ValueError(f"Unverified RTL embeddings: {name}")
    paths = inputs()
    if len(paths) < 150 or any(not p.is_file() for p in paths):
        raise ValueError("Missing graph or embedding inputs")
    DEST.mkdir(parents=True, exist_ok=True)
    for model in MODELS:
        source = ROOT / "runs" / f"external_{model}"
        check_model(model, source)
        target = DEST / model
        target.mkdir(exist_ok=True)
        for filename in ("predictions.json", "summary.json"):
            shutil.copyfile(source / filename, target / filename)
    record = {"evaluation_status": "small_held_out_family_diagnostic",
              "train_pairs": 21, "test_pairs": 5, "test_clean_source_groups": 2,
              "reviewed_gate_labels": 0,
              "hashes": {p.relative_to(ROOT).as_posix(): sha256(p) for p in paths}}
    (DEST / "provenance.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return verify()


def verify():
    samples()
    record = json.loads((DEST / "provenance.json").read_text(encoding="utf-8"))
    if record["evaluation_status"] != "small_held_out_family_diagnostic":
        raise ValueError("Wrong evaluation status")
    for relative, expected in record["hashes"].items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Missing or changed input: {relative}")
    metrics = {model: check_model(model, DEST / model) for model in MODELS}
    return {"status": "verified", "test_samples": 10, "test_clean_source_groups": 2,
            "models": {name: {key: value[key] for key in ("balanced_accuracy", "macro_f1", "auroc")}
                       for name, value in metrics.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify() if args.verify else publish(), indent=2))
