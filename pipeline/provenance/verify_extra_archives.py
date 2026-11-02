"""Verify source/archive hashes for the additional ISCAS and complete b19 pairs."""
import json
from prepare_new_archives import ROOT, OUT, sha256


def main():
    rows = []
    for name in ("gate_expansion_inventory.json", "b19_complete_inventory.json"):
        path = OUT / name
        if not path.is_file():
            continue
        rows.extend(json.loads(path.read_text(encoding="utf-8")))
    if len(rows) != 10:
        raise ValueError(f"Expected ten additional paired archives, got {len(rows)}")
    for row in rows:
        if sha256(ROOT / row["archive"]) != row["archive_sha256"]:
            raise ValueError(f"Archive hash mismatch: {row['benchmark']}")
        for side in ("clean", "trojan"):
            if not row["sources"][side]:
                raise ValueError(f"Missing side: {row['benchmark']}/{side}")
            for name, source in row["sources"][side].items():
                path = OUT / row["benchmark"] / side / name
                if not path.is_file() or path.stat().st_size != source["size"] or sha256(path) != source["sha256"]:
                    raise ValueError(f"Source hash mismatch: {path}")
    report = {"status": "verified", "paired_archives": len(rows),
              "families": sorted({row["family"] for row in rows})}
    (OUT / "extra_archive_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
