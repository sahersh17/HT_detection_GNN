"""Inventory added RTL modules/entities; this is a survey, not a gate labeler."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECL = re.compile(r"(?im)^\s*(?:module|entity)\s+([A-Za-z_][\w$]*)\b")


def modules(record):
    metadata = json.loads((ROOT / record["path"]).with_name("metadata.json").read_text(encoding="utf-8"))
    result = set()
    for source in metadata.get("sources", {}):
        if Path(source).suffix.lower() not in (".v", ".sv", ".vhd", ".vhdl"):
            continue
        text = (ROOT / source).read_text(encoding="utf-8", errors="replace")
        result.update(DECL.findall(text))
    return result


def main():
    manifest = json.loads((ROOT / "data/lofo_detection/protocol.json").read_text(encoding="utf-8"))
    pairs = {}
    for record in manifest["samples"]:
        pairs.setdefault(record["benchmark"], {})[record["side"]] = record
    rows = []
    for benchmark, sides in sorted(pairs.items()):
        if set(sides) != {"clean", "trojan"}:
            raise ValueError(f"Unpaired: {benchmark}")
        clean, trojan = modules(sides["clean"]), modules(sides["trojan"])
        rows.append({"benchmark": benchmark, "family": sides["trojan"]["family"],
                     "clean_module_count": len(clean), "trojan_module_count": len(trojan),
                     "trojan_only_modules": sorted(trojan-clean), "clean_only_modules": sorted(clean-trojan),
                     "status": "unreviewed_module_inventory"})
    output = ROOT / "data/localization_gate_audit/rtl_hierarchy_survey.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for row in rows:
        if row["trojan_only_modules"]:
            print(f"{row['benchmark']}: {', '.join(row['trojan_only_modules'])}")
    print(f"Added modules in {sum(bool(r['trojan_only_modules']) for r in rows)}/{len(rows)} paired variants")


if __name__ == "__main__":
    main()
