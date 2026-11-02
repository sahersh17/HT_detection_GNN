"""Audit mapped-netlist instance correspondence; emit candidate labels, never reviewed truth."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_ROOT = ROOT / "runs/new_gate_v1"
OUT = ROOT / "data/localization_gate_audit"
EXPECTED = {"s38584-T100": 9, "s38584-T200": 83, "s38584-T300": 731,
            "s15850-T100": 26, "s35932-T100": 15, "s35932-T200": 12,
            "s35932-T300": 35, "s38417-T100": 12, "s38417-T200": 15,
            "s38417-T300": 44}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells(path, top):
    module = json.loads(path.read_text(encoding="utf-8"))["modules"][top]
    aliases = {}
    for name, net in module.get("netnames", {}).items():
        if name.startswith("$"):
            continue
        for offset, bit in enumerate(net["bits"]):
            if isinstance(bit, int):
                aliases.setdefault(bit, []).append(f"{name}[{offset}]")
    aliases = {bit: sorted(names, key=lambda n: (len(n), n))[0] for bit, names in aliases.items()}
    result = {}
    for name, cell in module["cells"].items():
        ports = {port: [aliases.get(bit, f"unknown:{path}:{bit}") if isinstance(bit, int) else bit
                        for bit in bits] for port, bits in cell["connections"].items()}
        result[name] = (cell["type"], ports, cell.get("parameters"))
    return result


def same_cell(a, b):
    # Unknown or elaboration-generated wires cannot establish a benign match.
    return a == b


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for family in ("s38584", "s15850", "s35932", "s38417", "b15"):
        for pair in sorted(GRAPH_ROOT.glob(f"{family}-T*")):
            clean_meta_path = pair / "clean/metadata.json"
            trojan_meta_path = pair / "trojan/metadata.json"
            if not clean_meta_path.exists() or not trojan_meta_path.exists():
                continue
            clean = json.loads(clean_meta_path.read_text(encoding="utf-8"))
            trojan = json.loads(trojan_meta_path.read_text(encoding="utf-8"))
            clean_source = ROOT / next(iter(clean["sources"]))
            trojan_source = ROOT / next(iter(trojan["sources"]))
            if digest(clean_source) != next(iter(clean["sources"].values())) or digest(trojan_source) != next(iter(trojan["sources"].values())):
                raise ValueError(f"Source hash mismatch: {pair.name}")
            if len(clean["node_names"]) != clean["num_nodes"] or len(trojan["node_names"]) != trojan["num_nodes"]:
                raise ValueError(f"Node order mismatch: {pair.name}")
            clean_json = pair / "clean/yosys.json"
            trojan_json = pair / "trojan/yosys.json"
            if digest(clean_json) != clean["yosys_json_sha256"] or digest(trojan_json) != trojan["yosys_json_sha256"]:
                raise ValueError(f"Synthesis JSON hash mismatch: {pair.name}")
            c, t = cells(clean_json, clean["top"]), cells(trojan_json, trojan["top"])
            clean_names, trojan_names = set(clean["node_names"]), set(trojan["node_names"])
            if not clean_names.issubset(c) or not trojan_names.issubset(t):
                raise ValueError(f"Graph/source instance names disagree: {pair.name}: "
                                 f"clean graph-only={sorted(clean_names-set(c))[:5]} source-only={sorted(set(c)-clean_names)[:5]}; "
                                 f"trojan graph-only={sorted(trojan_names-set(t))[:5]} source-only={sorted(set(t)-trojan_names)[:5]}")
            added, removed = trojan_names - clean_names, clean_names - trojan_names
            modified = {name for name in clean_names & trojan_names if not same_cell(c[name], t[name])}
            named = {name for name in trojan_names if "trojan" in name.lower()}
            # An unchanged instance definition is a defensible negative for the
            # inserted-cell task. Rewired shared instances remain unknown.
            labels = [1 if n in added else -1 if n in modified else 0 for n in trojan["node_names"]]
            row = {"benchmark": pair.name, "graph_id": trojan["graph_id"],
                   "clean_graph_id": clean["graph_id"], "family": family,
                   "clean_nodes": clean["num_nodes"], "trojan_nodes": trojan["num_nodes"],
                   "added": len(added), "removed": len(removed), "modified_shared": len(modified),
                   "trojan_named": len(named), "named_and_added": len(named & added),
                   "name_diff_only": sorted(added - named), "named_shared": sorted(named - added),
                   "clean_source_sha256": digest(clean_source), "trojan_source_sha256": digest(trojan_source),
                   "clean_metadata_sha256": digest(clean_meta_path), "trojan_metadata_sha256": digest(trojan_meta_path),
                   "label_status": "mechanical_candidate_unreviewed"}
            if family != "b15":
                row["published_trojan_gate_count"] = EXPECTED[pair.name]
                row["count_matches_published"] = len(added) == EXPECTED[pair.name]
                if removed or not row["count_matches_published"]:
                    row["label_status"] = "correspondence_discrepancy_unreviewed"
                if pair.name == "s38584-T300":
                    row["label_status"] = "quarantined_trigger_payload_disconnect"
                (OUT / f"{pair.name}_candidate_labels.json").write_text(json.dumps({
                    "graph_id": trojan["graph_id"], "node_names": trojan["node_names"],
                    "labels": labels, "reviewed": False, "task": "inserted_cell_localization",
                   "source": "hash-verified Yosys instance set diff and exact shared-cell comparison",
                    "unknown_means": "shared instance with changed type or port connections",
                    "audit": row}, indent=2), encoding="utf-8")
            summary.append(row)
    (OUT / "audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for row in summary:
        print(f"{row['benchmark']}: +{row['added']} -{row['removed']} changed={row['modified_shared']} named={row['trojan_named']} status={row['label_status']}")


if __name__ == "__main__":
    main()
