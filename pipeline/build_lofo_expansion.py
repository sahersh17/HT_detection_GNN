"""Version the exploratory 10-host graph detection cohort without altering v1."""
import hashlib
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW = ("s15850", "s35932", "s38417")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-b19", action="store_true")
    args = parser.parse_args()
    previous = json.loads((ROOT / "data/lofo_detection/protocol.json").read_text(encoding="utf-8"))
    records = list(previous["samples"])
    for family in NEW:
        for pair in sorted((ROOT / "runs/new_gate_v1").glob(f"{family}-T*")):
            for side, label in (("clean", 0), ("trojan", 1)):
                path = pair / side / "graph.pt"
                metadata = json.loads(path.with_name("metadata.json").read_text(encoding="utf-8"))
                if metadata["graph_id"] != f"new_gate_v1/{pair.name}/{side}" or metadata["label"] != label:
                    raise ValueError(f"Graph identity mismatch: {path}")
                for source, expected in metadata["sources"].items():
                    if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != expected:
                        raise ValueError(f"Source hash mismatch: {source}")
                records.append({"benchmark": pair.name, "side": side, "family": family,
                                "label": label, "path": path.relative_to(ROOT).as_posix(),
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if args.include_b19:
        for pair in sorted((ROOT / "runs/new_vhdl_v1").glob("b19-T*")):
            for side, label in (("clean", 0), ("trojan", 1)):
                path = pair / side / "graph.pt"
                if not path.is_file():
                    raise ValueError(f"b19 graph missing: {path}")
                metadata = json.loads(path.with_name("metadata.json").read_text(encoding="utf-8"))
                if metadata["graph_id"] != f"new_vhdl_v1/{pair.name}/{side}" or metadata["label"] != label:
                    raise ValueError(f"b19 identity mismatch: {path}")
                for source, expected in metadata["sources"].items():
                    if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != expected:
                        raise ValueError(f"b19 source hash mismatch: {source}")
                records.append({"benchmark": pair.name, "side": side, "family": "b19", "label": label,
                                "path": path.relative_to(ROOT).as_posix(),
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    ids = [(r["benchmark"], r["side"]) for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate graph record")
    families = sorted({r["family"] for r in records})
    output = {"status": "exploratory_expansion_inspected_hosts", "parent": "data/lofo_detection/protocol.json",
              "split": "leave one entire host family out", "groups": families,
              "limitations": ["All included host families have been inspected", "Mixed synthesis domains",
                              "Repeated clean designs", "Unreviewed gate labels are not detection inputs"],
              "samples": records}
    target = ROOT / ("data/lofo_expanded_b19/protocol.json" if args.include_b19 else "data/lofo_expanded/protocol.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Frozen exploratory cohort: {len(records)} graphs, {len(records)//2} pairs, {len(families)} hosts")


if __name__ == "__main__":
    main()
