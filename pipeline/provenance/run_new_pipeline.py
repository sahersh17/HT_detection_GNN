"""Run the new-family pipeline in dependency order; preserve failures in audit."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEPS = [
    ["prepare_new_archives.py"], ["verify_new_archives.py"],
    ["synth_gate_netlists.py", "--family", "b15"],
    ["synth_gate_netlists.py", "--family", "s38584"],
    ["synth_vhdl.py", "--family", "MC8051"],
    ["synth_vhdl.py", "--family", "BasicRSA"],
    ["verify.py", "runs/new_gate_v1"], ["verify.py", "runs/new_vhdl_v1"],
    ["embed_new_vhdl.py"], ["verify_rtl.py", "--new-vhdl"], ["audit_new_data.py"],
]

if __name__ == "__main__":
    for script, *args in STEPS:
        print(f"Running {script} {' '.join(args)}", flush=True)
        subprocess.run([sys.executable, "-u", str(Path(__file__).parent / script), *args],
                       cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "pipeline/tests"], cwd=ROOT, check=True)
