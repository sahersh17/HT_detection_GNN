"""Inventory and safely extract the newly supplied Trust-Hub archive families.

This is intentionally a provenance step, not a claim that every archive is an
RTL clean/Trojan pair. Layout netlists, gate netlists, mixed VHDL/Verilog,
trojan-only sources, and incomplete multipart archives remain distinct.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "new_trusthub"
FOLDERS = ("B15_zipped", "BASICRSA_zipped", "MC8051_zipped", "PIC1648_zipped", "S_zipped")
FAMILIES = {"b15": "layout_netlist", "BasicRSA": "vhdl_trojan_only",
            "MC8051": "mixed_vhdl_verilog", "PIC16F84": "verilog_duplicate",
            "s38584": "gate_netlist", "s15850": "gate_netlist",
            "s35932": "gate_netlist", "s38417": "gate_netlist",
            "b19": "paired_vhdl"}
SOURCE_EXTENSIONS = {".v", ".sv", ".vhd", ".vhdl", ".vh", ".h"}
ARCHIVE_RE = re.compile(r"^(b15|BasicRSA|MC8051|PIC16F84|s38584|s15850|s35932|s38417|b19)-T\d+\.(zip|rar)$", re.I)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def seven_zip(default=None):
    candidate = default or shutil.which("7z") or ROOT / "runs" / "tools" / "7zfull" / "7z.exe"
    path = Path(candidate)
    if not path.is_file():
        raise FileNotFoundError(f"7-Zip is required for RAR and malformed ZIP headers: {path}")
    return path


def members(archive, executable):
    result = subprocess.run([str(executable), "l", "-slt", str(archive)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"Cannot list archive {archive}: {result.stderr[-300:]}")
    blocks = result.stdout.split("----------", 1)
    if len(blocks) != 2:
        raise ValueError(f"No archive member table: {archive}")
    found = []
    for block in blocks[1].split("\n\n"):
        attrs = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
        if attrs.get("Path") and attrs.get("Folder") == "-":
            found.append((attrs["Path"], int(attrs.get("Size", 0))))
    return found


def read_member(archive, member, executable):
    result = subprocess.run([str(executable), "e", "-so", "-bd", str(archive), member], capture_output=True)
    if result.returncode:
        raise ValueError(f"Cannot extract {member} from {archive}: {result.stderr[-300:]!r}")
    return result.stdout


def prepare_archive(archive, executable):
    match = ARCHIVE_RE.match(archive.name)
    if match is None:
        return {"archive": archive.relative_to(ROOT).as_posix(), "status": "excluded_nonbenchmark_or_incomplete_volume",
                "reason": "Filename is not a complete single-volume T-variant archive"}
    benchmark = archive.stem
    family = match.group(1)
    canonical = next(name for name in FAMILIES if name.lower() == family.lower())
    flavor = FAMILIES[canonical]
    record = {"benchmark": benchmark, "family": canonical, "archive": archive.relative_to(ROOT).as_posix(),
              "archive_sha256": sha256(archive), "format": flavor, "status": "extracted_unreviewed",
              "sources": {"clean": {}, "trojan": {}}, "exclusions": []}
    if canonical == "PIC16F84":
        previous = ROOT / "trusthub" / "AES_zipped" / archive.name
        if previous.is_file() and sha256(previous) == record["archive_sha256"]:
            record.update({"status": "duplicate_archive_existing_pic_pipeline",
                           "duplicate_of": previous.relative_to(ROOT).as_posix()})
            return record
    paths = members(archive, executable)
    root = OUT / benchmark
    for member, size in paths:
        parts = re.split(r"[/\\]+", member)
        if any(part in ("", ".", "..") for part in parts) or len(parts) < 2:
            raise ValueError(f"Unsafe archive member: {member}")
        if parts[0].lower() != benchmark.lower():
            raise ValueError(f"Archive root does not match benchmark: {member}")
        if parts[-1].lower() == "readme.txt" and len(parts) == 2:
            (root / "readme.txt").parent.mkdir(parents=True, exist_ok=True)
            (root / "readme.txt").write_bytes(read_member(archive, member, executable))
            continue
        if len(parts) < 3 or parts[1].lower() != "src" or Path(parts[-1]).suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        if len(parts) == 4 and parts[2] in ("TjFree", "TjIn"):
            side = "clean" if parts[2] == "TjFree" else "trojan"
        elif len(parts) == 3 and canonical == "BasicRSA":
            side = "trojan"
        else:
            record["exclusions"].append({"member": member, "reason": "Unsupported nested source layout"})
            continue
        if size > 2_000_000:
            raise ValueError(f"Unexpectedly large source member: {member}")
        data = read_member(archive, member, executable)
        if len(data) != size:
            raise ValueError(f"Extracted length differs from archive listing: {member}")
        filename = parts[-1]
        if filename in record["sources"][side]:
            raise ValueError(f"Duplicate source basename in {benchmark}/{side}: {filename}")
        target = root / side / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        record["sources"][side][filename] = {"sha256": sha256(target), "member": member, "size": size}
    if not record["sources"]["trojan"]:
        record["status"] = "no_trojan_source"
    elif not record["sources"]["clean"]:
        record["status"] = "trojan_only_no_clean_pair"
    else:
        clean, trojan = record["sources"]["clean"], record["sources"]["trojan"]
        record["changed_files"] = sorted(name for name in clean.keys() | trojan.keys()
                                         if clean.get(name, {}).get("sha256") != trojan.get(name, {}).get("sha256"))
    (root / "extraction_manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seven-zip", type=Path)
    args = parser.parse_args()
    executable = seven_zip(args.seven_zip)
    records = []
    for folder in FOLDERS:
        for archive in sorted((ROOT / "trusthub" / folder).iterdir()):
            if archive.is_file():
                records.append(prepare_archive(archive, executable))
                print(f"{archive.name}: {records[-1]['status']}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "inventory.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(json.dumps({"archives": len(records), "extracted": sum(r["status"] == "extracted_unreviewed" for r in records),
                      "duplicates": sum(r["status"].startswith("duplicate") for r in records)}, indent=2))


if __name__ == "__main__":
    main()
