"""Extract local s15850/s35932/s38417 archives without touching earlier cohorts."""
import json
from pathlib import Path
from prepare_new_archives import ROOT, OUT, prepare_archive, seven_zip

FAMILIES = ("s15850", "s35932", "s38417")


def main():
    source = ROOT / "trusthub/AES_zipped"
    executable = seven_zip()
    records = []
    for family in FAMILIES:
        for archive in sorted(source.glob(f"{family}-T*.rar")):
            record = prepare_archive(archive, executable)
            if record["status"] != "extracted_unreviewed" or not all(record["sources"].values()):
                raise ValueError(f"Unusable paired archive: {archive}: {record['status']}")
            records.append(record)
            print(f"{record['benchmark']}: paired source extracted")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gate_expansion_inventory.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"{len(records)} paired variants across {len(FAMILIES)} hosts")


if __name__ == "__main__":
    main()
