"""Extract only complete single-volume b19 VHDL pairs from local archives."""
import json
from prepare_new_archives import ROOT, OUT, prepare_archive, seven_zip


def main():
    records = []
    for variant in ("T300", "T400", "T500"):
        archive = ROOT / f"trusthub/AES_zipped/b19-{variant}.rar"
        record = prepare_archive(archive, seven_zip())
        if record["status"] != "extracted_unreviewed" or not all(record["sources"].values()):
            raise ValueError(f"Unusable paired archive: {archive}")
        records.append(record)
        print(f"{record['benchmark']}: complete VHDL pair")
    (OUT / "b19_complete_inventory.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
