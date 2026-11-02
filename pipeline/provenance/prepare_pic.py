"""Extract PIC16F84 paired Verilog from the bundled RAR archives.

Requires 7-Zip (--seven-zip or PATH), or libarchive bsdtar (--bsdtar).
Only the two named RTL members per archive are written under runs/expansion/.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEVEN_ZIP = ROOT / "runs" / "tools" / "7zfull" / "7z.exe"


def prepare_one(benchmark, seven_zip=None, bsdtar=None):
    archive = ROOT / "trusthub" / "AES_zipped" / f"{benchmark}.rar"
    output = ROOT / "runs" / "expansion" / benchmark
    record = {"benchmark": benchmark, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "status": "unreviewed_expansion_candidate", "sources": {}}
    for side, source_dir in (("clean", "TjFree"), ("trojan", "TjIn")):
        member = f"{benchmark}\\src\\{source_dir}\\risc16f84.v"
        command = ([str(bsdtar), "-xOf", str(archive), member.replace("\\", "/")]
                   if bsdtar else [str(seven_zip), "e", "-so", "-bd", str(archive), member])
        result = subprocess.run(command, capture_output=True)
        if result.returncode or b"module" not in result.stdout:
            raise RuntimeError(f"Could not extract {member}: {result.stderr.decode(errors='replace')}")
        target = output / side / "risc16f84.v"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.stdout)
        record["sources"][side] = {"risc16f84.v": hashlib.sha256(result.stdout).hexdigest()}
    record["changed_files"] = ["risc16f84.v"] if record["sources"]["clean"] != record["sources"]["trojan"] else []
    (output / "extraction_manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seven-zip", type=Path, default=Path(shutil.which("7z") or DEFAULT_SEVEN_ZIP))
    parser.add_argument("--bsdtar", type=Path, help="Use libarchive bsdtar instead of 7-Zip")
    args = parser.parse_args()
    if args.bsdtar and not args.bsdtar.is_file():
        parser.error("bsdtar executable not found")
    if not args.bsdtar and not args.seven_zip.is_file():
        raise FileNotFoundError(f"Install 7-Zip and pass --seven-zip PATH (looked at {args.seven_zip})")
    rows = [prepare_one(f"PIC16F84-T{variant}", args.seven_zip, args.bsdtar) for variant in (100, 200, 300, 400)]
    print(json.dumps([{"benchmark": row["benchmark"], "changed_files": row["changed_files"]} for row in rows], indent=2))
