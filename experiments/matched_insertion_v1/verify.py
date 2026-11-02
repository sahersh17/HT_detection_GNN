"""Verify generated gate JSON imports into Yosys and preserves the pilot manifest."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/matched_insertion_v1"
YOSYS = ROOT / "trusthub/venv/Scripts/yowasp-yosys.exe"


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    checks = []
    for row in manifest["records"]:
        path = OUT / row["host"] / row["variant"] / "yosys.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["json_sha256"]:
            raise ValueError(f"Generated JSON changed: {path}")
        script = f"read_json {path.relative_to(ROOT).as_posix()}; hierarchy -check -top {row['top']}"
        try:
            process = subprocess.run([str(YOSYS), "-Q", "-T", "-p", script], cwd=ROOT,
                                     capture_output=True, text=True, timeout=180)
            result = {"host": row["host"], "variant": row["variant"],
                      "passed": process.returncode == 0, "returncode": process.returncode,
                      "diagnostic_tail": (process.stderr + process.stdout)[-1000:] if process.returncode else ""}
        except subprocess.TimeoutExpired:
            result = {"host": row["host"], "variant": row["variant"],
                      "passed": False, "returncode": None, "diagnostic_tail": "timeout"}
        checks.append(result)
        (OUT / "verification_progress.json").write_text(json.dumps({"checks": checks}, indent=2), encoding="utf-8")
        print(row["host"], row["variant"], "ok" if result["passed"] else "FAIL", flush=True)
    (OUT / "verification.json").write_text(json.dumps({"checks": checks,
        "all_passed": all(c["passed"] for c in checks)}, indent=2), encoding="utf-8")
    if not all(c["passed"] for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
