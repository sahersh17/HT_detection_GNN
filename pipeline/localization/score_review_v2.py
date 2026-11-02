"""Score two independent human reviews or one human versus candidate labels.

The 162-row packet is stratified. Agreement on it is sample agreement, not an
estimate of population precision or recall for all netlist nodes.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/localization_gate_audit"
PACKET = BASE / "review_packet_v2/blind_nodes.csv"
MANIFEST = BASE / "review_packet_v2/manifest.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_review(path, expected):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    labels = {}
    for row in rows:
        key = row["review_id"]
        if key not in expected or key in labels:
            raise ValueError(f"Unexpected or duplicate review ID: {key}")
        value = row["reviewed_label"].strip()
        if value not in ("", "-1", "0", "1"):
            raise ValueError(f"Invalid review label: {key}={value}")
        labels[key] = None if not value else int(value)
    if set(labels) != expected:
        raise ValueError("Review file does not cover the complete packet")
    return labels


def agreement(a, b):
    pairs = [(a[k], b[k]) for k in a if a[k] in (0, 1) and b[k] in (0, 1)]
    if not pairs:
        return {"comparable": 0, "kappa": None, "positive_agreement": None}
    n = len(pairs)
    both_pos = sum(x == 1 and y == 1 for x, y in pairs)
    both_neg = sum(x == 0 and y == 0 for x, y in pairs)
    disagree = n - both_pos - both_neg
    p_a = sum(x == 1 for x, _ in pairs) / n
    p_b = sum(y == 1 for _, y in pairs) / n
    observed = (both_pos + both_neg) / n
    expected = p_a * p_b + (1 - p_a) * (1 - p_b)
    return {"comparable": n, "both_positive": both_pos, "both_negative": both_neg,
            "disagreements": disagree, "observed_agreement": observed,
            "kappa": (observed - expected) / (1 - expected) if expected < 1 else None,
            "positive_agreement": 2 * both_pos / (2 * both_pos + disagree)
                                  if 2 * both_pos + disagree else None,
            "negative_agreement": 2 * both_neg / (2 * both_neg + disagree)
                                  if 2 * both_neg + disagree else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--review-a", type=Path, required=True)
    ap.add_argument("--review-b", type=Path,
                    help="Second independent human review; otherwise compare with automatic candidates")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(PACKET) != manifest["csv_sha256"]:
        raise ValueError("Blind packet hash changed")
    with PACKET.open(newline="", encoding="utf-8") as stream:
        ids = {row["review_id"] for row in csv.DictReader(stream)}
    if len(ids) != manifest["rows"]:
        raise ValueError("Packet ID count mismatch")
    a = read_review(args.review_a, ids)
    if args.review_b:
        b = read_review(args.review_b, ids)
        mode = "two_independent_human_reviewers"
        second_hash = sha256(args.review_b)
    else:
        candidates = json.loads((BASE / "review_key.json").read_text(encoding="utf-8"))
        b = {r["review_id"]: r["candidate_label"] for r in candidates}
        if set(b) != ids:
            raise ValueError("Candidate key does not match packet")
        mode = "one_human_vs_automatic_candidates_not_interrater"
        second_hash = sha256(BASE / "review_key.json")
    result = {"status": "stratified_sample_agreement_only", "mode": mode,
              "packet_sha256": sha256(PACKET), "review_a_sha256": sha256(args.review_a),
              "second_sha256": second_hash, "rows": len(ids),
              "review_a_completed": sum(value is not None for value in a.values()),
              "review_a_confident": sum(value in (0, 1) for value in a.values()),
              "review_a_uncertain": sum(value == -1 for value in a.values()),
              "agreement": agreement(a, b),
              "limits": ["Stratified sample cannot be used for unweighted population precision or recall",
                         "Source excerpts may reveal insertion structure despite masking overt markers",
                         "One human versus automatic candidates is not human inter-rater reliability"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
