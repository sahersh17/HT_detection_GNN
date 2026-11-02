"""Extract Trojan-only 90nm/180nm RS232 mapped sources with archive provenance."""
import json
from pathlib import Path
from prepare_new_archives import ROOT, members, read_member, seven_zip, sha256

OUT = ROOT / "runs/new_trusthub/rs232_gate"


def main():
    seven = seven_zip()
    inventory = json.loads((ROOT / "data/localization_gate_audit/rs232_archive_inventory.json").read_text())
    rows = []
    for item in inventory:
        if item["status"] != "mapped_trojan_only_no_paired_clean":
            continue
        archive = ROOT / item["archive"]
        if sha256(archive) != item["sha256"]:
            raise ValueError(f"Archive hash mismatch: {archive}")
        available = {name.replace("\\", "/"): name for name, _ in members(archive, seven)}
        for source in item["mapped_sources"]:
            technology = "90nm" if "/90nm/" in source.lower() else "180nm"
            data = read_member(archive, available[source], seven)
            target = OUT / item["benchmark"] / technology / "uart.v"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            rows.append({"benchmark": item["benchmark"], "technology": technology,
                         "source": target.relative_to(ROOT).as_posix(), "sha256": sha256(target),
                         "archive": item["archive"], "archive_sha256": item["sha256"],
                         "status": "trojan_only_no_clean_pair"})
        print(item["benchmark"], flush=True)
    if len(rows) != 22:
        raise ValueError(f"Expected 22 technology variants, got {len(rows)}")
    (OUT / "inventory.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Extracted {len(rows)} mapped netlists from {len({r['benchmark'] for r in rows})} RS232 variants")


if __name__ == "__main__":
    main()
