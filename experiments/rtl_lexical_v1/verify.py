"""Check each transformed design with the synthesis frontend and record failures."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/rtl_lexical_v1"
YOSYS = ROOT / "trusthub/venv/Scripts/yowasp-yosys.exe"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", action="append")
    ap.add_argument("--arm", action="append", choices=["comments", "names", "both"])
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    rows = [r for r in manifest["records"] if (not args.benchmark or r["benchmark"] in args.benchmark)
            and (not args.arm or r["arm"] in args.arm)]
    seen = {}
    results = []
    for row in rows:
        paths = [ROOT / entry["transformed"] for entry in row["files"]]
        includes = [ROOT / entry["transformed"] for entry in row["includes"]]
        for entry in [*row["files"], *row["includes"]]:
            if sha(ROOT / entry["transformed"]) != entry["transformed_sha256"]:
                raise ValueError(f"Transformed source changed: {entry['transformed']}")
        # File identities are an optimization only; all benchmark-side rows remain in the report.
        key = (tuple(entry["transformed_sha256"] for entry in [*row["files"], *row["includes"]]),
               row["transformed_top"])
        if key not in seen:
            directory = paths[0].parent.relative_to(ROOT).as_posix()
            script = "read_verilog -I" + directory + " " + " ".join(
                path.relative_to(ROOT).as_posix() for path in paths)
            script += "; hierarchy -check -top " + row["transformed_top"]
            try:
                process = subprocess.run([str(YOSYS), "-Q", "-T", "-p", script], cwd=ROOT,
                                         capture_output=True, text=True, timeout=args.timeout)
                seen[key] = {"compiled": process.returncode == 0,
                             "returncode": process.returncode,
                             "diagnostic_tail": (process.stderr + process.stdout)[-1000:] if process.returncode else ""}
            except subprocess.TimeoutExpired:
                seen[key] = {"compiled": False, "returncode": None, "diagnostic_tail": "timeout"}
        result = {"benchmark": row["benchmark"], "side": row["side"], "arm": row["arm"], **seen[key]}
        results.append(result)
        (OUT / "verification_progress.json").write_text(json.dumps({"checks": results}, indent=2), encoding="utf-8")
        print(f"{row['arm']} {row['benchmark']}/{row['side']}: {'ok' if result['compiled'] else 'FAIL'}", flush=True)
    (OUT / "verification.json").write_text(json.dumps({"checks": results,
        "unique_compilations": len(seen), "passed": sum(r["compiled"] for r in results)}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
