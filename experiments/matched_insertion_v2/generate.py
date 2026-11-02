"""Build a topology-balanced revision of the four-host gate insertion pilot.

Both comparator cones have identical internal topology. The second cone swaps
two primary input bits, making a different trigger. A matched unused XOR chain
balances connections in all three variants. The gate-only representation omits
primary-input and output roles, so this is also an identifiability control.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from build import graph_from_json  # noqa: E402

OUT = ROOT / "runs/matched_insertion_v2"
HOSTS = {
    "AES": "runs/provenance_v1/AES-T100/clean/yosys.json",
    "RS232": "runs/provenance_v1/RS232-T2100/clean/yosys.json",
    "memctrl": "runs/expansion_graphs/memctrl-T100/clean/yosys.json",
    "PIC16F84": "runs/expansion_pic_graphs/PIC16F84-T100/clean/yosys.json",
}
VARIANTS = ("clean_matched", "decoy", "trojan")
PREFIX = "__matched_g1b_"


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_io(module):
    inputs = [(name, port["bits"]) for name, port in module["ports"].items()
              if port["direction"] == "input" and len(port["bits"]) >= 8
              and all(isinstance(bit, int) for bit in port["bits"])]
    outputs = [(name, i, bit) for name, port in module["ports"].items()
               if port["direction"] == "output" for i, bit in enumerate(port["bits"])
               if isinstance(bit, int)]
    driven = {bit for cell in module["cells"].values()
              for pin, direction in cell["port_directions"].items() if direction == "output"
              for bit in cell["connections"][pin] if isinstance(bit, int)}
    outputs = [row for row in outputs if row[2] in driven]
    if not inputs or not outputs:
        raise ValueError("Host requires an 8-bit primary input and a driven output")
    return inputs[0][0], inputs[0][1][:8], outputs[0]


def next_bit(module):
    bits = [bit for port in module["ports"].values() for bit in port["bits"] if isinstance(bit, int)]
    bits += [bit for cell in module["cells"].values() for conn in cell["connections"].values()
             for bit in conn if isinstance(bit, int)]
    bits += [bit for net in module["netnames"].values() for bit in net["bits"] if isinstance(bit, int)]
    return max(bits) + 1


def inject(document, variant, input_bits, output):
    result = copy.deepcopy(document)
    top = next(iter(result["modules"]))
    module = result["modules"][top]
    if any(name.startswith(PREFIX) for name in module["cells"]):
        raise ValueError("Synthetic cell prefix already exists")
    cursor = next_bit(module)
    inserted = []

    def cell(name, kind, connections):
        nonlocal cursor
        output_bit = cursor
        cursor += 1
        ports = {pin: [bit] for pin, bit in connections.items()}
        ports["Y"] = [output_bit]
        module["cells"][name] = {"hide_name": 0, "type": f"$_{kind}_", "parameters": {},
            "attributes": {}, "port_directions": {**{pin: "input" for pin in connections}, "Y": "output"},
            "connections": ports}
        inserted.append(name)
        return output_bit

    def comparator(tag, pattern, bits):
        terms = []
        for i, bit in enumerate(bits):
            terms.append(bit if pattern & (1 << i) else cell(f"{PREFIX}{tag}_not_{i}", "NOT", {"A": bit}))
        value = terms[0]
        for i, term in enumerate(terms[1:], 1):
            value = cell(f"{PREFIX}{tag}_and_{i}", "AND", {"A": value, "B": term})
        return value

    a = comparator("a", 0xA5, input_bits)
    permuted = list(input_bits)
    permuted[0], permuted[1] = permuted[1], permuted[0]
    b = comparator("b", 0xA5, permuted)
    _, position, original_bit = output
    first = a if variant != "decoy" else b
    second = b if variant == "trojan" else first
    middle = cell(f"{PREFIX}payload_1", "XOR", {"A": original_bit, "B": first})
    final = cell(f"{PREFIX}payload_2", "XOR", {"A": middle, "B": second})
    dummy_first = b if variant != "decoy" else a
    dummy_second = a if variant == "trojan" else dummy_first
    dummy_middle = cell(f"{PREFIX}decoy_1", "XOR", {"A": original_bit, "B": dummy_first})
    cell(f"{PREFIX}decoy_2", "XOR", {"A": dummy_middle, "B": dummy_second})
    module["ports"][output[0]]["bits"][position] = final
    return result, top, inserted


def exhaustive_cone_check():
    outcome = {}
    for variant in VARIANTS:
        differing_patterns = []
        for pattern in range(256):
            a, b = pattern == 0xA5, pattern == 0xA6
            first = a if variant != "decoy" else b
            second = b if variant == "trojan" else first
            for original in (0, 1):
                changed = original ^ first ^ second
                if changed != original:
                    differing_patterns.append(pattern)
        outcome[variant] = sorted(set(differing_patterns))
    if outcome != {"clean_matched": [], "decoy": [], "trojan": [0xA5, 0xA6]}:
        raise AssertionError(outcome)
    return outcome


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    proof = exhaustive_cone_check()
    records = []
    for host, source_rel in HOSTS.items():
        source = ROOT / source_rel
        document = json.loads(source.read_text(encoding="utf-8"))
        top = next(iter(document["modules"]))
        input_name, input_bits, output = selected_io(document["modules"][top])
        host_rows = []
        for variant in VARIANTS:
            mutated, top, inserted = inject(document, variant, input_bits, output)
            target_dir = OUT / host / variant
            target_dir.mkdir(parents=True, exist_ok=True)
            json_path = target_dir / "yosys.json"
            json_path.write_text(json.dumps(mutated), encoding="utf-8")
            graph, metadata = graph_from_json(mutated, top, f"matched_g1/{host}/{variant}",
                                              int(variant == "trojan"))
            graph_path = target_dir / "graph.pt"
            torch.save(graph, graph_path)
            node_labels = [int(name in inserted and variant == "trojan") for name in metadata["node_names"]]
            if variant == "trojan" and sum(node_labels) != len(inserted):
                raise ValueError("Inserted gate labels do not align with graph")
            (target_dir / "node_labels.json").write_text(json.dumps({"node_names_sha256":
                metadata["node_names_sha256"], "labels": node_labels}), encoding="utf-8")
            row = {"host": host, "variant": variant, "source": source_rel,
                   "source_sha256": hash_file(source), "top": top,
                   "input_port": input_name, "trigger_input_bits": input_bits,
                   "output_port": output[0], "output_bit_index": output[1],
                   "inserted_cells": len(inserted), "positive_nodes": sum(node_labels),
                   "num_nodes": graph.num_nodes, "num_edges": int(graph.edge_index.shape[1]),
                   "json_sha256": hash_file(json_path), "graph_sha256": hash_file(graph_path),
                   "cone_differing_input_patterns": proof[variant]}
            records.append(row)
            host_rows.append(row)
            print(host, variant, row["num_nodes"], row["num_edges"], flush=True)
        if len({r["num_nodes"] for r in host_rows}) != 1:
            raise AssertionError(f"Node count mismatch in {host}")
    (OUT / "manifest.json").write_text(json.dumps({"status": "generated_pending_external_validation",
        "generator": "G1b_balanced_comparator_xor", "selected_hosts": list(HOSTS),
        "source_provenance": "same frozen clean synthesized Yosys JSON within each host",
        "functional_check": "exhaustive two-valued enumeration of inserted output cone",
        "records": records}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
