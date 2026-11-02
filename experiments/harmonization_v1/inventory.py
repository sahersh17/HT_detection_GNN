"""Inventory original archive members and missing mapped-cell functions."""
import json
from collections import Counter
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipeline/provenance'))
from prepare_new_archives import members, seven_zip, sha256


def main():
    tool = seven_zip()
    records = []
    for folder in ['B15_zipped','S_zipped']:
        for archive in sorted((ROOT/'trusthub'/folder).iterdir()):
            if archive.suffix.lower() not in ('.zip','.rar') or '.part' in archive.name.lower() or archive.stem.startswith('b19'):
                continue
            entries = members(archive,tool)
            candidates = [name for name,_ in entries if Path(name).suffix.lower() in ('.lib','.db') or
                          any(word in name.lower() for word in ('library','stdcell','techmap','synthesis.log'))]
            cells = Counter()
            for metadata in (ROOT/'runs/new_gate_v1'/archive.stem).glob('*/metadata.json'):
                cells.update(json.loads(metadata.read_text())['node_types'])
            records.append(dict(archive=archive.relative_to(ROOT).as_posix(),sha256=sha256(archive),
                                library_candidates=candidates, all_members=[n for n,_ in entries],
                                required_cell_types=dict(sorted(cells.items())),
                                status='functional_models_not_verified'))
    out = ROOT/'runs/harmonization_v1'
    out.mkdir(parents=True,exist_ok=True)
    (out/'library_inventory.json').write_text(json.dumps(records,indent=2))
    print(json.dumps([dict(archive=r['archive'],candidates=r['library_candidates'],cell_types=len(r['required_cell_types'])) for r in records],indent=2))


if __name__=='__main__':
    main()
