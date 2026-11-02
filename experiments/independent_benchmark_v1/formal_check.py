"""Find independent Yosys SAT output-difference witnesses for combinational pilots.

The SAT miter uses both top-level output vectors. A witness demonstrates that
the infected netlist differs from the converted clean netlist for one input;
it does not prove trigger stealth, decoy equivalence, or sequential reachability.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/independent_benchmark_v1"
REPORT = ROOT / "data/independent_benchmark_v1/formal_combinational.json"
YOSYS = ROOT / "trusthub/venv/Scripts/yowasp-yosys.exe"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def wave_bit(entry):
    wave = entry["wave"]
    if not wave or wave[0] not in "01":
        raise ValueError(f"SAT witness has non-Boolean value: {entry}")
    return int(wave[0])


def inspect_witness(path):
    signals = {entry["name"]: wave_bit(entry)
               for entry in json.loads(path.read_text(encoding="utf-8"))["signal"]}
    if signals.get("trigger") != 1:
        raise ValueError("Miter trigger was not asserted")
    gold = {name[5:]: bit for name, bit in signals.items() if name.startswith("gold_")}
    infected = {name[5:]: bit for name, bit in signals.items() if name.startswith("gate_")}
    if not gold or set(gold) != set(infected):
        raise ValueError("Gold and infected output ports missing or mismatched")
    differences = sorted(name for name in gold if gold[name] != infected[name])
    if not differences:
        raise ValueError("SAT trigger high but no observed output mismatch")
    inputs = {name[3:]: bit for name, bit in signals.items() if name.startswith("in_")}
    if not inputs:
        raise ValueError("SAT witness has no primary inputs")
    return {"inputs": len(inputs), "output_ports": len(gold),
            "different_outputs": differences,
            "input_assignment_sha256": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()}


def verify_variant(run, variant):
    host = run["host"]
    run_dir = OUT / run["run_id"]
    gold = run_dir / f"{Path(run['command'][1]).stem}_conv.v"
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\(",
                      gold.read_text(encoding="utf-8", errors="replace"))
    if not match:
        raise ValueError("Clean netlist has no module declaration")
    top = match.group(1)
    infected = OUT / variant["file"]
    if not gold.is_file() or not infected.is_file() or sha256(infected) != variant["sha256"]:
        raise ValueError("Missing or altered netlist")
    case = run_dir / "formal" / infected.stem
    case.mkdir(parents=True, exist_ok=True)
    witness = case / "output_difference.json"
    script = (f"read_verilog {gold.relative_to(ROOT).as_posix()}; "
              f"rename {top} golden; "
              f"read_verilog {infected.relative_to(ROOT).as_posix()}; "
              f"rename {top} infected; "
              "miter -equiv -make_outputs -flatten golden infected miter; "
              "hierarchy -check -top miter; opt; "
              f"sat -set trigger 1 -set-def-inputs -show-ports -dump_json {witness.relative_to(ROOT).as_posix()}")
    try:
        process = subprocess.run([str(YOSYS), "-Q", "-T", "-p", script],
                                 cwd=ROOT, capture_output=True, text=True, timeout=600)
        code, diagnostic = process.returncode, (process.stdout + process.stderr)[-3000:]
    except subprocess.TimeoutExpired as error:
        code, diagnostic = None, str(error)[-3000:]
    (case / "formal.log").write_text(diagnostic, encoding="utf-8")
    row = {"run_id": run["run_id"], "host": host,
           "variant": variant["file"], "gold_sha256": sha256(gold),
           "infected_sha256": sha256(infected), "yosys_exit_code": code,
           "log_sha256": sha256(case / "formal.log")}
    if code == 0 and witness.is_file():
        row["witness"] = inspect_witness(witness)
        row["witness_sha256"] = sha256(witness)
        row["status"] = "independent_combinational_output_difference_witness"
    else:
        row["status"] = ("sat_unsat_no_defined_input_output_difference"
                         if code == 0 and "SAT solving finished - no model found" in diagnostic
                         else "formal_witness_failed")
        row["diagnostic_tail"] = diagnostic[-500:]
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append")
    args = parser.parse_args()
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    prior = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {"records": []}
    for run in manifest["records"]:
        if run["mechanism"] != "combinational" or (args.host and run["host"] not in args.host):
            continue
        if run["status"] != "upstream_self_validated":
            raise ValueError("Cannot formal-check a failed upstream run")
        for variant in run["variants"]:
            if any(r["variant"] == variant["file"] for r in prior["records"]):
                print("skip", variant["file"], flush=True)
                continue
            print("formal", variant["file"], flush=True)
            row = verify_variant(run, variant)
            prior["records"].append(row)
            prior["status"] = "combinational_witnesses_only_not_full_benchmark_gate"
            save_json(REPORT, prior)
            print(row["status"], len(row.get("witness", {}).get("different_outputs", [])), flush=True)
    if any(r["status"] != "independent_combinational_output_difference_witness" for r in prior["records"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
