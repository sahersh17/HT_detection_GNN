"""Check that sanitized model text still compiles for every changed circuit."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
manifest=json.loads((ROOT/"data/training_audit_v3/manifest.json").read_text())
verified=[]
for row in manifest["records"]:
 if not row["wording_occurrences_removed"]:continue
 path=ROOT/"runs/training_audit_v3/prepared"/(row["key"]+".v")
 top="uart" if row["host"]=="RS232" else "pic_16f84_core"
 includes=sorted({str((ROOT/name).parent) for name in row["source_sha256"]})
 args=["iverilog","-g2012","-t","null","-s",top]
 for folder in includes:args.extend(["-I",folder])
 result=subprocess.run(args+[str(path)],cwd=ROOT,text=True,capture_output=True)
 if result.returncode:raise ValueError((row["key"],result.stderr))
 verified.append(row["key"])
(ROOT/"data/training_audit_v3/sanitized_syntax.json").write_text(json.dumps(dict(compiled=verified),indent=2))
print("compiled",len(verified))
