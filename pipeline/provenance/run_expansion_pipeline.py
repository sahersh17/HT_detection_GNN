"""Rebuild and verify the extra ISCAS and complete b19 cohorts in order."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
STEPS = [
    ("prepare_gate_expansion.py", []),
    ("prepare_b19_complete.py", []),
    ("verify_extra_archives.py", []),
    ("inventory_rs232_gate.py", []),
    ("prepare_rs232_gate.py", []),
    ("synth_rs232_gate.py", []),
    ("verify.py", ["runs/rs232_gate_v1"]),
    ("synth_gate_netlists.py", ["--family", "s15850"]),
    ("synth_gate_netlists.py", ["--family", "s35932"]),
    ("synth_gate_netlists.py", ["--family", "s38417"]),
    ("verify.py", ["runs/new_gate_v1"]),
    ("synth_vhdl.py", ["--family", "b19"]),
    ("verify.py", ["runs/new_vhdl_v1"]),
    ("audit_gate_labels.py", []),
    ("freeze_s38584_candidates.py", []),
    ("build_lofo_expansion.py", []),
    ("build_lofo_expansion.py", ["--include-b19"]),
    ("verify_lofo_expansion.py", []),
]


def main():
    for script, args in STEPS:
        path = (ROOT / "pipeline/localization" / script if script in
                ("audit_gate_labels.py", "freeze_s38584_candidates.py") else
                ROOT / "pipeline" / script if script in ("build_lofo_expansion.py", "verify_lofo_expansion.py") else HERE / script)
        print(f"Running {script} {' '.join(args)}", flush=True)
        subprocess.run([sys.executable, str(path), *args], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
