"""Export a stratified, prediction-free review packet and a separate answer key."""
import csv
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/localization_gate_audit"


def main():
    rng = random.Random(42)
    packet = []
    key = []
    for path in sorted(BASE.glob("*_candidate_labels.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        audit = record["audit"]
        if audit["family"] == "b15" or audit["label_status"] != "mechanical_candidate_unreviewed":
            continue
        metadata_path = ROOT / "runs" / record["graph_id"] / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["node_names"] != record["node_names"]:
            raise ValueError(f"Node order mismatch: {record['graph_id']}")
        groups = {label: [i for i, value in enumerate(record["labels"]) if value == label] for label in (1, 0, -1)}
        selected = []
        for label, limit in ((1, 10), (0, 10), (-1, 5)):
            selected.extend(rng.sample(groups[label], min(limit, len(groups[label]))))
        rng.shuffle(selected)
        for index in selected:
            row_id = hashlib.sha256(f"{record['graph_id']}:{index}".encode()).hexdigest()[:16]
            packet.append({"review_id": row_id, "graph_id": record["graph_id"], "node_index": index,
                           "instance_name": record["node_names"][index], "cell_type": metadata["node_types"][index],
                           "source_spans": json.dumps(metadata["source_ranges"][index]),
                           "reviewed_label": "", "reason": ""})
            key.append({"review_id": row_id, "candidate_label": record["labels"][index]})
    rng.shuffle(packet)
    out = BASE / "review_packet"
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "blind_nodes.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(packet[0]))
        writer.writeheader(); writer.writerows(packet)
    (BASE / "review_key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"status": "awaiting_independent_review",
        "rows": len(packet), "graphs": len({row['graph_id'] for row in packet}),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "instructions": "Review each cell from the netlist and benchmark context; use 1 inserted trigger/payload, 0 confidently unrelated, -1 uncertain. Candidate labels and model scores are absent."}, indent=2), encoding="utf-8")
    print(f"Blind packet: {len(packet)} rows across {len({row['graph_id'] for row in packet})} graphs")


if __name__ == "__main__":
    main()
