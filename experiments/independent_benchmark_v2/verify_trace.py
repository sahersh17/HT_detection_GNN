"""Independently evaluate saved sequential Trojan activation traces.

This uses a separate primitive-gate evaluator and natural state advancement.
The upstream simplified scan-FF representation has no clock pin; this check
models one DIN-to-Q update per cycle and does not certify original RTL timing.
"""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/independent_benchmark_v2/runs"
REPORT = ROOT / "data/independent_benchmark_v2/sequential_trace.json"
CELL = re.compile(r"^\s*(and|or|nand|nor|not|xor|xnor|buf|sdff|sdffr)\s+\S+\s*\(([^)]*)\)\s*;", re.I)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def parse(path):
    inputs, outputs, gates, flops = [], [], [], []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("input "):
            inputs.extend(x.strip() for x in stripped[6:].rstrip(";").split(","))
        elif stripped.startswith("output "):
            outputs.extend(x.strip() for x in stripped[7:].rstrip(";").split(","))
        match = CELL.match(line)
        if not match:
            continue
        kind, body = match.group(1).lower(), [x.strip() for x in match.group(2).split(",")]
        if kind in ("sdff", "sdffr"):
            if len(body) < (4 if kind == "sdff" else 5):
                raise ValueError(f"Malformed flip-flop: {line}")
            flops.append({"q": body[0], "qbar": body[1], "d": body[2] if kind == "sdff" else body[3]})
        else:
            gates.append((kind, body[0], body[1:]))
    if not inputs or not outputs or not gates:
        raise ValueError(f"Empty parsed circuit: {path}")
    if len(set(inputs)) != len(inputs) or len(set(outputs)) != len(outputs):
        raise ValueError("Duplicate top port")
    return {"inputs": inputs, "outputs": outputs, "gates": gates, "flops": flops}


def bit(values, name):
    if name == "1'b0":
        return 0
    if name == "1'b1":
        return 1
    return values.get(name)


def evaluate(circuit, input_values, state):
    values = dict(input_values)
    for ff in circuit["flops"]:
        q = state[ff["q"]]
        values[ff["q"]], values[ff["qbar"]] = q, 1 - q
    pending = list(circuit["gates"])
    for _ in range(len(pending) + 1):
        if not pending:
            break
        rest = []
        for kind, output, names in pending:
            args = [bit(values, name) for name in names]
            if any(value is None for value in args):
                rest.append((kind, output, names))
                continue
            if kind == "and":
                result = int(all(args))
            elif kind == "or":
                result = int(any(args))
            elif kind == "nand":
                result = int(not all(args))
            elif kind == "nor":
                result = int(not any(args))
            elif kind == "not":
                result = 1 - args[0]
            elif kind == "xor":
                result = args[0] ^ args[1]
            elif kind == "xnor":
                result = 1 - (args[0] ^ args[1])
            elif kind == "buf":
                result = args[0]
            else:
                raise ValueError(f"Unsupported primitive: {kind}")
            values[output] = result
        if len(rest) == len(pending):
            break
        pending = rest
    if pending:
        raise ValueError(f"Unresolved combinational gates: {len(pending)}")
    outputs = {name: bit(values, name) for name in circuit["outputs"]}
    if any(value is None for value in outputs.values()):
        raise ValueError("Undriven output")
    next_state = {ff["q"]: bit(values, ff["d"]) for ff in circuit["flops"]}
    if any(value is None for value in next_state.values()):
        raise ValueError("Undriven next state")
    return values, outputs, next_state


def verify_one(folder, item):
    infected_file = folder / item["source_path"]
    gold_file = folder / (Path(json.loads((folder / "summary.json").read_text())["netlist"]).stem + "_conv.v")
    if sha256(infected_file) != item["source_sha256"]:
        raise ValueError("Infected source changed")
    golden, infected = parse(gold_file), parse(infected_file)
    if golden["inputs"] != infected["inputs"] or golden["outputs"] != infected["outputs"]:
        raise ValueError("Clean/infected top interfaces differ")
    rng = random.Random(0)
    inputs = {name: rng.randint(0, 1) for name in infected["inputs"]}
    inputs.update({name: int(value) for name, value in item["merged_care_bits"].items()
                   if name in inputs})
    golden_state = {ff["q"]: 0 for ff in golden["flops"]}
    infected_state = {ff["q"]: 0 for ff in infected["flops"]}
    expected = (1 << len(item["counter_qs"])) - 1
    trace = []
    state_at_fire = None
    for cycle in range(expected + 2):
        if cycle == expected:
            state_at_fire = (dict(golden_state), dict(infected_state))
        gv, go, golden_state = evaluate(golden, inputs, golden_state)
        iv, io, infected_state = evaluate(infected, inputs, infected_state)
        differing = sorted(name for name in go if go[name] != io[name])
        trace.append({"cycle": cycle, "trigger": iv.get(item["trigger_signal"]),
                      "fire": iv.get(item["fire_signal"]),
                      "payload_difference": iv.get(item["payload"]) != iv.get(item["payload_tap"]),
                      "different_output_count": len(differing),
                      "different_outputs": differing[:16]})
    trigger_held = all(row["trigger"] == 1 for row in trace[:expected + 1])
    no_early_fire = all(row["fire"] == 0 and row["different_output_count"] == 0
                        for row in trace[:expected])
    fired = trace[expected]["fire"] == 1 and trace[expected]["payload_difference"]
    observable = trace[expected]["different_output_count"] > 0
    postfire = None
    if fired and not observable:
        search_rng = random.Random(20261102)
        for attempt in range(256):
            candidate = {name: search_rng.randint(0, 1) for name in infected["inputs"]}
            _, gold_outputs, _ = evaluate(golden, candidate, state_at_fire[0])
            _, infected_outputs, _ = evaluate(infected, candidate, state_at_fire[1])
            changed = sorted(name for name in gold_outputs if gold_outputs[name] != infected_outputs[name])
            if changed:
                postfire = {"attempt": attempt + 1, "different_outputs": changed[:16],
                            "input_assignment_sha256": hashlib.sha256(
                                json.dumps(candidate, sort_keys=True).encode()).hexdigest()}
                break
    return {"source_path": item["source_path"], "source_sha256": item["source_sha256"],
            "clean_sha256": sha256(gold_file), "input_assignment_sha256": hashlib.sha256(
                json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            "input_count": len(inputs), "clean_ff_count": len(golden["flops"]),
            "infected_ff_count": len(infected["flops"]), "expected_fire_cycle": expected,
            "trigger_held": trigger_held, "no_early_fire_or_output_difference": no_early_fire,
            "fired_at_expected_cycle": fired, "top_output_difference_at_fire": observable,
            "postfire_output_witness": postfire,
            "trace": trace,
            "status": "independent_simplified_scan_trace_pass" if all((trigger_held, no_early_fire, fired)) and (observable or postfire)
                      else "independent_simplified_scan_trace_failed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/independent_benchmark_v2/manifest.json").read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {"records": []}
    for run in manifest["records"]:
        if run["mechanism"] != "sequential" or (args.host and run["host"] not in args.host):
            continue
        folder = ROOT / run["folder"]
        vectors = json.loads((folder / "activation_vectors.json").read_text(encoding="utf-8"))
        for item in vectors["records"]:
            key = (run["run_id"], item["source_path"])
            previous = next((r for r in report["records"]
                             if (r["run_id"], r["source_path"]) == key), None)
            if previous and previous["status"] == "independent_simplified_scan_trace_pass":
                continue
            print("trace", run["run_id"], item["index"], flush=True)
            row = {"run_id": run["run_id"], "host": run["host"], **verify_one(folder, item)}
            if previous:
                report["records"].remove(previous)
            report["records"].append(row)
            report["status"] = "independent_simplified_scan_traces_not_full_RTL_equivalence"
            save_json(REPORT, report)
            print(row["status"], row["trace"][row["expected_fire_cycle"]]["different_output_count"], flush=True)


if __name__ == "__main__":
    main()
