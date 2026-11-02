"""Export candidate-label-blind excerpts without Trojan-marked instance names."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/localization_gate_audit"
SOURCE = BASE / "review_packet/blind_nodes.csv"
OUT = BASE / "review_packet_v2"
MARKER = re.compile(r"trojan|trigger|payload|tj(?:in|free)?", re.I)
TOKEN = re.compile(r"[A-Za-z_$\\][A-Za-z0-9_$\\]*")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mask_marked_tokens(value):
    return TOKEN.sub(lambda found: "MASKED_ID" if MARKER.search(found.group(0))
                     else found.group(0), value)


def excerpt(graph_id, spans, instance_name):
    metadata = json.loads((ROOT / "runs" / graph_id / "metadata.json").read_text(encoding="utf-8"))
    by_name = {}
    for relative in metadata["sources"]:
        name = Path(relative).name
        if name in by_name:
            raise ValueError(f"Ambiguous source basename: {name}")
        by_name[name] = ROOT / relative
    aliases = {name: f"source_{index:02d}" for index, name in enumerate(sorted(by_name), 1)}
    parts = []
    for name, start, end in spans:
        lines = by_name[name].read_text(encoding="utf-8", errors="replace").splitlines()
        if not 1 <= start <= end <= len(lines):
            raise ValueError(f"Invalid source span: {graph_id}/{name}:{start}-{end}")
        for lineno in range(max(1, start - 2), min(len(lines), end + 2) + 1):
            text = lines[lineno - 1].split("//", 1)[0].replace(instance_name, "MASKED_CELL")
            parts.append(f"{aliases[name]}:{lineno}: {mask_marked_tokens(text)}")
    return "\n".join(parts)


def main():
    original_manifest = json.loads((BASE / "review_packet/manifest.json").read_text(encoding="utf-8"))
    if sha256(SOURCE) != original_manifest["csv_sha256"]:
        raise ValueError("Original packet hash changed")
    rows, key = [], []
    with SOURCE.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            spans = json.loads(row["source_spans"])
            rows.append({"review_id": row["review_id"],
                         "design_id": sha256_text(row["graph_id"])[:12],
                         "cell_type": row["cell_type"],
                         "masked_source_excerpt": excerpt(row["graph_id"], spans, row["instance_name"]),
                         "reviewed_label": "", "reason": ""})
            key.append({"review_id": row["review_id"], "graph_id": row["graph_id"],
                        "source_spans": spans, "node_index": int(row["node_index"]),
                        "instance_name": row["instance_name"]})
    if len(rows) != original_manifest["rows"] or len({r["review_id"] for r in rows}) != len(rows):
        raise ValueError("Review packet incomplete")
    if any(MARKER.search(row["masked_source_excerpt"]) for row in rows):
        raise ValueError("Overt Trojan marker remains in reviewer excerpt")
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "blind_nodes.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    key_path = BASE / "review_locator_key_v2.json"
    key_path.write_text(json.dumps(key, indent=2), encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps({
        "status": "awaiting_independent_review_candidate_label_blind",
        "rows": len(rows), "graphs": len({r["design_id"] for r in rows}),
        "source_packet_sha256": sha256(SOURCE), "csv_sha256": sha256(target),
        "locator_key_sha256": sha256(key_path),
        "limitations": ["Source context can still reveal insertion style; no claim of fully blind hardware review",
                       "Source paths and overt Trojan markers masked in reviewer CSV",
                       "Candidate labels and model scores excluded from reviewer CSV"]}, indent=2), encoding="utf-8")
    print(f"Exported {len(rows)} masked review rows")


if __name__ == "__main__":
    main()
