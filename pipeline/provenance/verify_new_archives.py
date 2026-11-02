"""Verify extracted Trust-Hub bytes and the inclusion/exclusion inventory."""
import json
from collections import Counter

from prepare_new_archives import OUT, ROOT, FOLDERS, sha256


def verify():
    records = json.loads((OUT / "inventory.json").read_text(encoding="utf-8"))
    listed = {r["archive"] for r in records}
    present = {p.relative_to(ROOT).as_posix() for folder in FOLDERS
               for p in (ROOT / "trusthub" / folder).iterdir() if p.is_file()}
    if listed != present or len(listed) != len(records):
        raise ValueError("Archive inventory differs from on-disk files")
    counts = Counter()
    families = Counter()
    for record in records:
        archive = ROOT / record["archive"]
        status = record["status"]
        counts[status] += 1
        if "archive_sha256" in record and sha256(archive) != record["archive_sha256"]:
            raise ValueError(f"Archive hash changed: {archive}")
        if status == "duplicate_archive_existing_pic_pipeline":
            if sha256(ROOT / record["duplicate_of"]) != sha256(archive):
                raise ValueError(f"PIC duplicate hash changed: {archive}")
            continue
        if status == "excluded_nonbenchmark_or_incomplete_volume":
            continue
        families[record["family"]] += 1
        sources = record["sources"]
        if not sources["trojan"] or (status == "extracted_unreviewed" and not sources["clean"]):
            raise ValueError(f"Unexpected source side: {archive}")
        if status == "trojan_only_no_clean_pair" and sources["clean"]:
            raise ValueError(f"Trojan-only archive has clean source: {archive}")
        for side, files in sources.items():
            for name, item in files.items():
                target = OUT / record["benchmark"] / side / name
                if not target.is_file() or target.stat().st_size != item["size"] or sha256(target) != item["sha256"]:
                    raise ValueError(f"Extracted source changed: {target}")
                if name.lower().startswith(("tb_", "testbench")) and record["format"] in ("layout_netlist", "gate_netlist"):
                    raise ValueError(f"Gate netlist selection contains a testbench: {target}")
        if sources["clean"]:
            changed = sorted(set(sources["clean"]) | set(sources["trojan"]))
            changed = [name for name in changed if
                       sources["clean"].get(name, {}).get("sha256") !=
                       sources["trojan"].get(name, {}).get("sha256")]
            if changed != record["changed_files"]:
                raise ValueError(f"Clean/Trojan source diff changed: {archive}")
    summary = {"status": "verified", "archives": len(records), "statuses": dict(counts),
               "extracted_families": dict(families),
               "reviewed_gate_labels": 0}
    (OUT / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
