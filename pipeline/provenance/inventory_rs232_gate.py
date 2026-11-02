"""Inventory local RS232 archives for mapped gate sources and clean counterparts."""
import json
from pathlib import Path
from prepare_new_archives import ROOT, members, seven_zip, sha256


def main():
    seven = seven_zip()
    rows = []
    for archive in sorted((ROOT / "trusthub/AES_zipped").glob("RS232-T*.zip")):
        paths = [name.replace("\\", "/") for name, _ in members(archive, seven)]
        sources = [p for p in paths if p.lower().endswith((".v", ".sv")) and "/src/" in p.lower()]
        mapped = [p for p in sources if "/90nm/" in p.lower() or "/180nm/" in p.lower()]
        clean = [p for p in sources if "/tjfree/" in p.lower()]
        rows.append({"archive": archive.relative_to(ROOT).as_posix(), "sha256": sha256(archive),
                     "benchmark": archive.stem, "mapped_sources": mapped, "clean_sources": clean,
                     "status": "mapped_trojan_only_no_paired_clean" if mapped and not clean else
                               "paired_rtl_or_other" if clean else "needs_manual_layout_review"})
    target = ROOT / "data/localization_gate_audit/rs232_archive_inventory.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for row in rows:
        if row["mapped_sources"]:
            print(row["benchmark"], len(row["mapped_sources"]), row["status"])
    print(f"{len(rows)} archives inventoried")


if __name__ == "__main__":
    main()
