"""Inventory independent TRIT archives without extracting or scoring candidates."""
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = ROOT / "runs/third_party/trit_candidate"
OUT = ROOT / "data/trusthub_primary_v1/trit_intake.json"
PANEL = json.loads((ROOT / "data/dataset_v2/trusthub_primary.json").read_text(encoding="utf-8"))
SEEN = {r["family"].lower() for r in PANEL}
result = {"status": "archive_inventory_only_no_records_admitted", "archives": []}

for host in ("s953", "s1196", "s1238"):
    path = ARCHIVES / f"{host}_DoS.zip"
    if not path.exists():
        result["archives"].append({"host": host, "status": "not_downloaded"})
        continue
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if archive.testzip() is not None:
            raise ValueError(f"ZIP integrity failed: {host}")
        if any(name.startswith("/") or ".." in Path(name).parts or "\\" in name for name in names):
            raise ValueError(f"Unsafe archive member: {host}")
        original = [name for name in names if name == f"{host}/original/{host}.v"]
        logs = [name for name in names if name.endswith("/log.txt")]
        infected = [name for name in names if name.endswith(".v") and name != f"{host}/original/{host}.v" and "/lib/" not in name]
        notice = archive.read(f"{host}/README").decode("utf-8", errors="replace")
        if len(original) != 1 or len(logs) != 200 or len(infected) != 200 or "DATE" not in notice:
            raise ValueError(f"Unexpected TRIT archive layout: {host}")
        source_hash = hashlib.sha256(archive.read(original[0])).hexdigest()
        result["archives"].append({
            "host": host, "status": "integrity_and_layout_checked_only", "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "original_netlist_sha256": source_hash, "bytes": path.stat().st_size,
            "trojan_variants": len(infected), "logs": len(logs),
            "mechanism_counts": dict(Counter("sequential" if "/sequential_DoS/" in n else "combinational" for n in infected)),
            "primary_family_name_overlap": host.lower() in SEEN,
            "behavior_verified_here": False, "benign_decoys_present": False,
        })

OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
