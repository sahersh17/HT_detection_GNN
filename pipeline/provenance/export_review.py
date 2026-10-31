"""Export blinded, fillable gate-label sheets from an aligned graph export.

Usage: python pipeline/provenance/export_review.py runs/provenance_v1/AES-T100/trojan
The CSV is an annotation aid; filling it does not itself certify ground truth.
"""
import argparse
import csv
import json
from pathlib import Path


def export(folder, output):
    folder = Path(folder)
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    candidates = json.loads((folder / "candidate_labels.json").read_text(encoding="utf-8"))
    if candidates["graph_id"] != metadata["graph_id"] or candidates["node_names"] != metadata["node_names"]:
        raise ValueError("Candidate and metadata row order differ")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = ["graph_id", "node_index", "node_name", "cell_type", "candidate_label", "source_span",
               "reviewed_label", "evidence_or_reason", "reviewer_id"]
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for i, name in enumerate(metadata["node_names"]):
            writer.writerow({"graph_id": metadata["graph_id"], "node_index": i, "node_name": name,
                             "cell_type": metadata["node_types"][i], "candidate_label": candidates["labels"][i],
                             "source_span": metadata["node_src"][i], "reviewed_label": "",
                             "evidence_or_reason": "", "reviewer_id": ""})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph_folder", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or args.graph_folder / "review_template.csv"
    print(export(args.graph_folder, output))


if __name__ == "__main__":
    main()
