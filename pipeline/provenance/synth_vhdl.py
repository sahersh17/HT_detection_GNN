"""Family-specific GHDL-to-Yosys synthesis for MC8051 and BasicRSA.

MC8051 uses VHDL-87 configurations and mixed source archives. The synthesizable
core configuration is selected explicitly; simulation RAM, FPGA wrappers, and
testbenches are not silently substituted into the design. BasicRSA is an
unpaired VHDL Trojan source; failed synthesis is recorded, not relabeled clean.
Generated Verilog source spans are NOT original VHDL line locations.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import torch

from build import ROOT, graph_from_json, sha256

SOURCE = ROOT / "runs" / "new_trusthub"
DEFAULT_OUT = ROOT / "runs" / "new_vhdl_v1"
DEFAULT_GHDL = ROOT / "runs" / "tools" / "ghdl-mcode-6.0.0-mingw64" / "bin" / "ghdl.exe"
DEFAULT_YOSYS = ROOT / "trusthub" / "venv" / "Scripts" / "yowasp-yosys.exe"
EXCLUDE = re.compile(r"(^tb_|_tb\.vhd$|_test\.vhd$|^rsatest)", re.I)
_MC8051_CORE_NAMES = None


def execute(argv, cwd=ROOT):
    return subprocess.run([str(item) for item in argv], cwd=cwd, capture_output=True)


def status(target, result, message=""):
    target.mkdir(parents=True, exist_ok=True)
    record = {"benchmark": target.parent.name, "side": target.name, "status": result, "message": message}
    (target / "synthesis_status.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def mc8051_core_names(out_root, ghdl):
    """Use GHDL's dependency order to exclude FPGA wrappers and testbenches."""
    global _MC8051_CORE_NAMES
    if _MC8051_CORE_NAMES is not None:
        return _MC8051_CORE_NAMES
    reference = SOURCE / "MC8051-T200" / "clean"
    all_files = sorted(p for p in reference.glob("*.vhd") if not EXCLUDE.search(p.name))
    workdir = out_root / "mc8051_reference_work"
    workdir.mkdir(parents=True, exist_ok=True)
    workflag = f"--workdir={workdir.relative_to(ROOT).as_posix()}"
    flags = ("--std=87", "-fsynopsys", "-fexplicit")
    imported = execute([ghdl, "-i", *flags, workflag, *(p.relative_to(ROOT).as_posix() for p in all_files)])
    if imported.returncode:
        raise RuntimeError(f"Cannot import MC8051 clean reference: {imported.stderr[-600:]!r}")
    ordered = execute([ghdl, "--elab-order", *flags, workflag, "mc8051_core_struc_cfg"])
    if ordered.returncode:
        raise RuntimeError(f"Cannot resolve MC8051 core dependencies: {ordered.stderr[-600:]!r}")
    names = tuple(Path(line).name for line in ordered.stdout.decode(errors="replace").splitlines() if line.strip())
    if len(names) < 30 or len(names) != len(set(names)):
        raise ValueError("Unexpected MC8051 core dependency set")
    _MC8051_CORE_NAMES = names
    return names


def build_one(benchmark, side, out_root, ghdl, yosys):
    family = benchmark.split("-")[0]
    if family not in ("MC8051", "BasicRSA", "b19"):
        raise ValueError(f"Unsupported VHDL family: {family}")
    source_dir = SOURCE / benchmark / side
    target = out_root / benchmark / side
    target.mkdir(parents=True, exist_ok=True)
    workdir = target / "ghdl_work"
    workdir.mkdir(exist_ok=True)
    sources = sorted(p for p in source_dir.glob("*.vhd") if not EXCLUDE.search(p.name))
    if family == "BasicRSA":
        sources = [source_dir / "modmult.vhd", source_dir / "rsacypher.vhd"]
        flags, top, unit = ("--std=93", "-fsynopsys", "-fexplicit"), "RSACypher", "RSACypher"
        analyze_mode = "-a"
    elif family == "b19":
        sources = [source_dir / "b19.vhd"]
        flags, top, unit = ("--std=93", "-fsynopsys", "-fexplicit"), "b19", "b19"
        analyze_mode = "-a"
    else:
        sources = [source_dir / name for name in mc8051_core_names(out_root, ghdl)]
        flags, top, unit = ("--std=93", "-fsynopsys", "-fexplicit"), "mc8051_core", "mc8051_core_struc_cfg"
        analyze_mode = "-i"
    if not sources or any(not p.is_file() for p in sources):
        return status(target, "missing_source", "Selected VHDL source files are missing")
    original_sources = list(sources)
    adaptations = []
    if benchmark == "MC8051-T500" and side == "trojan":
        fixture = ROOT / "pipeline/tests/shift_equivalence.vhd"
        sim_flags = ["--std=93", f"--workdir={workdir.relative_to(ROOT).as_posix()}"]
        analysis = execute([ghdl, "-a", *sim_flags, fixture])
        simulation = execute([ghdl, "-r", *sim_flags, "shift_equivalence", "--assert-level=error"])
        (target / "shift_equivalence.log").write_bytes(analysis.stderr + simulation.stdout + simulation.stderr)
        if analysis.returncode or simulation.returncode:
            raise ValueError("Exhaustive shift compatibility test failed")
        # GHDL 6 cannot synthesize bit_vector SLA. Preserve its right-fill bit.
        source = source_dir / "mc8051_control_struc.vhd"
        text = source.read_text(encoding="utf-8")
        if text.count("Key := Key sla 1;") != 1 or "bit_vector (7 downto 0)" not in text:
            raise ValueError("MC8051-T500 shift adaptation precondition changed")
        adapted_dir = target / "adapted"
        adapted_dir.mkdir(exist_ok=True)
        adapted = adapted_dir / source.name
        adapted.write_text(text.replace("Key := Key sla 1;", "Key := Key(6 downto 0) & Key(0);"), encoding="utf-8")
        sources = [adapted if p == source else p for p in sources]
        adaptations.append({"original": source.relative_to(ROOT).as_posix(),
                            "adapted": adapted.relative_to(ROOT).as_posix(), "sha256": sha256(adapted),
                            "reason": "GHDL unsupported bit_vector SLA; explicit concatenation",
                            "validation": "GHDL simulation: all 256 possible 8-bit inputs agree"})
    workflag = f"--workdir={workdir.relative_to(ROOT).as_posix()}"
    imported = execute([ghdl, analyze_mode, *flags, workflag, *(p.relative_to(ROOT).as_posix() for p in sources)])
    log = [f"GHDL import/analyze return code: {imported.returncode}\n", imported.stderr.decode(errors="replace")]
    if imported.returncode:
        (target / "synthesis.log").write_text("\n".join(log), encoding="utf-8")
        return status(target, "ghdl_analysis_failed", imported.stderr.decode(errors="replace")[-1200:])
    if family == "MC8051":
        elaborated = execute([ghdl, "-m", *flags, workflag, unit])
        log += [f"GHDL elaborate return code: {elaborated.returncode}\n", elaborated.stderr.decode(errors="replace")]
        if elaborated.returncode:
            (target / "synthesis.log").write_text("\n".join(log), encoding="utf-8")
            return status(target, "ghdl_elaboration_failed", elaborated.stderr.decode(errors="replace")[-1200:])
    synth_options = ["--latches"] if family == "MC8051" else []
    converted = execute([ghdl, "--synth", *flags, workflag, "--out=verilog", *synth_options, unit])
    log += [f"GHDL synth return code: {converted.returncode}\n", converted.stderr.decode(errors="replace")]
    if converted.returncode or not converted.stdout or f"module {top}".encode() not in converted.stdout:
        (target / "synthesis.log").write_text("\n".join(log), encoding="utf-8")
        return status(target, "ghdl_synthesis_failed", converted.stderr.decode(errors="replace")[-1200:])
    converted_path = target / "converted.v"
    converted_path.write_bytes(converted.stdout)
    json_path = target / "yosys.json"
    script = (f"read_verilog {converted_path.relative_to(ROOT).as_posix()}; hierarchy -check -top {top}; "
              f"proc; opt; flatten; opt; techmap; opt; write_json {json_path.relative_to(ROOT).as_posix()}")
    synthesized = execute([yosys, "-Q", "-T", "-q", "-p", script])
    log += [f"Yosys return code: {synthesized.returncode}\n", synthesized.stdout.decode(errors="replace"),
            synthesized.stderr.decode(errors="replace")]
    (target / "synthesis.log").write_text("\n".join(log), encoding="utf-8")
    if synthesized.returncode or not json_path.is_file():
        return status(target, "yosys_synthesis_failed", synthesized.stderr.decode(errors="replace")[-1200:])
    document = json.loads(json_path.read_text(encoding="utf-8"))
    graph_id = f"new_vhdl_v1/{benchmark}/{side}"
    line_counts = {"converted.v": len(converted_path.read_text(encoding="utf-8", errors="replace").splitlines())}
    graph, metadata = graph_from_json(document, top, graph_id, int(side == "trojan"), line_counts)
    metadata.update({"benchmark": benchmark, "side": side, "top": top,
                     "source_level": "generated_verilog_lines_not_original_VHDL",
                     "synthesis_flow": "GHDL 6.0.0 --synth --out=verilog (MC8051 --latches); Yosys 0.69 no ABC",
                     "ghdl_unit": unit, "ghdl_flags": list(flags), "yosys_script": script,
                     "yosys_json_sha256": sha256(json_path),
                     "adaptations": adaptations,
                     "sources": {p.relative_to(ROOT).as_posix(): sha256(p) for p in [*original_sources, converted_path]}})
    torch.save(graph, target / "graph.pt")
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    result = status(target, "graph_built_unreviewed")
    result.update({"graph_id": graph_id, "nodes": graph.num_nodes, "edges": graph.num_edges,
                   "source_covered_nodes": metadata["source_covered_nodes"]})
    (target / "synthesis_status.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True, choices=("MC8051", "BasicRSA", "b19"))
    parser.add_argument("--benchmark", action="append")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ghdl", type=Path, default=DEFAULT_GHDL)
    parser.add_argument("--yosys", type=Path, default=DEFAULT_YOSYS)
    args = parser.parse_args()
    if not args.ghdl.is_file() or not args.yosys.is_file():
        parser.error("GHDL and YoWASP Yosys are required")
    out = args.out.resolve()
    if not out.is_relative_to(ROOT):
        parser.error("Output must be inside repository")
    benchmarks = args.benchmark or [p.name for p in sorted(SOURCE.glob(f"{args.family}-T*")) if p.is_dir()]
    rows = []
    for benchmark in benchmarks:
        sides = ("trojan",) if args.family == "BasicRSA" else ("clean", "trojan")
        for side in sides:
            row = build_one(benchmark, side, out, args.ghdl, args.yosys)
            rows.append(row)
            print(json.dumps(row), flush=True)
    all_rows = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(out.glob(f"{args.family}-T*/*/synthesis_status.json"))]
    (out / f"{args.family}_build_summary.json").write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
    print(json.dumps({"attempted": len(rows), "built": sum(r["status"] == "graph_built_unreviewed" for r in rows)}, indent=2))


if __name__ == "__main__":
    main()
