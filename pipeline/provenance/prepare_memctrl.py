"""Extract only the clean/Trojan RTL pair from the bundled memctrl-T100 ZIP.

Usage: python pipeline/provenance/prepare_memctrl.py
Output is kept in gitignored runs/expansion/memctrl-T100/.
"""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "trusthub" / "AES_zipped" / "memctrl-T100.zip"
OUTPUT = ROOT / "runs" / "expansion" / "memctrl-T100"
PREFIXES = {"clean": "memctrl-T100/rtl/verilog/", "trojan": "memctrl-T100/rtl/verilog_tj_In/"}


def prepare():
    result = {"benchmark": "memctrl-T100", "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
              "status": "unreviewed_expansion_candidate", "sources": {}}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for side, prefix in PREFIXES.items():
            hashes = {}
            for member in archive.namelist():
                if not member.startswith(prefix) or not member.lower().endswith(".v"):
                    continue
                relative = member[len(prefix):]
                if "/" in relative or "\\" in relative or relative in ("", ".", ".."):
                    raise ValueError(f"Unexpected nested source path: {member}")
                content = archive.read(member)
                target = OUTPUT / side / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                hashes[relative] = hashlib.sha256(content).hexdigest()
            if not hashes:
                raise ValueError(f"No RTL files found for {side}")
            result["sources"][side] = hashes
    clean, trojan = result["sources"]["clean"], result["sources"]["trojan"]
    if clean.keys() != trojan.keys():
        raise ValueError("Clean and Trojan RTL file sets differ")
    result["changed_files"] = sorted(name for name in clean if clean[name] != trojan[name])
    (OUTPUT / "extraction_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
