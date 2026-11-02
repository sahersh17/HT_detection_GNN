"""Isolated primitive-graph pilot; never rewrites existing data or experiments."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'runs/harmonization_v1'
YOSYS = ROOT / 'trusthub/venv/Scripts/yowasp-yosys.exe'
sys.path.insert(0, str(ROOT / 'pipeline/provenance'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def execute(script, target, stem, timeout=900):
    (target/f'{stem}.ys').write_text(script, encoding='utf-8')
    start = time.monotonic()
    with (target/f'{stem}.log').open('w', encoding='utf-8') as log:
        try:
            run = subprocess.run([str(YOSYS), '-Q', '-T', '-s', relative(target/f'{stem}.ys')],
                                 cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            return dict(returncode=run.returncode, elapsed_seconds=time.monotonic()-start)
        except subprocess.TimeoutExpired:
            return dict(returncode=None, status='timeout_unproved', elapsed_seconds=time.monotonic()-start)


def build(benchmark, side):
    source = ROOT / 'runs/provenance_v1' / benchmark / side
    meta = json.loads((source/'metadata.json').read_text())
    assert digest(source/'yosys.json') == meta['yosys_json_sha256']
    for name, expected in meta['sources'].items():
        assert digest(ROOT/name) == expected
    target = OUT/benchmark/side
    target.mkdir(parents=True, exist_ok=True)
    top = meta['top']
    original = json.loads((source/'yosys.json').read_text())
    before = Counter(c['type'] for c in original['modules'][top]['cells'].values())
    # No ABC, retiming, reset conversion, scan constraints or clock assumptions.
    commands = [f'read_json {relative(source/"yosys.json")}', f'hierarchy -check -top {top}',
                'memory_collect', f'write_json {relative(target/"memory_reference.json")}',
                'memory_map', 'opt', f'write_json {relative(target/"lowered_reference.json")}',
                'techmap', 'opt', 'check -assert', f'write_json {relative(target/"yosys.json")}']
    conversion = execute('\n'.join(commands), target, 'conversion')
    result = dict(benchmark=benchmark, side=side, conversion=conversion,
                  input_json=relative(source/'yosys.json'), input_sha256=digest(source/'yosys.json'),
                  source_hashes=meta['sources'], original_cell_types=dict(before),
                  independent_memory_lowering_proof='not_established',
                  acceptance='provisional_not_training_eligible')
    if conversion['returncode'] != 0:
        (target/'status.json').write_text(json.dumps(result,indent=2))
        return result
    document = json.loads((target/'yosys.json').read_text())
    after = Counter(c['type'] for c in document['modules'][top]['cells'].values())
    # Require only recognized Yosys primitive cells, except nonfunctional scope metadata.
    unsupported = {k:v for k,v in after.items() if not k.startswith('$_') and k not in ('$scopeinfo','$print','$display')}
    result.update(cell_types=dict(after), unsupported_cells=unsupported,
                  original_nodes=meta['num_nodes'], output_json_bytes=(target/'yosys.json').stat().st_size,
                  output_sha256=digest(target/'yosys.json'))
    proof = [f'read_json {relative(target/"lowered_reference.json")}', f'rename {top} gold',
             'design -stash reference', f'read_json {relative(target/"yosys.json")}', f'rename {top} gate',
             'design -copy-from reference -as gold gold', 'equiv_make gold gate equiv',
             'hierarchy -top equiv', 'equiv_struct', 'equiv_simple', 'equiv_status -assert']
    if digest(target/'yosys.json') == digest(target/'lowered_reference.json'):
        result['post_lowering_equivalence'] = dict(returncode=0, method='exact_JSON_identity')
    else:
        result['post_lowering_equivalence'] = execute('\n'.join(proof),target,'equivalence',timeout=600)
    if not unsupported:
        import torch
        from build import graph_from_json
        from verify import verify_one
        counts = {Path(p).name:len((ROOT/p).read_text(errors='replace').splitlines()) for p in meta['sources']}
        graph, graph_meta = graph_from_json(document,top,f'harmonization_v1/{benchmark}/{side}',meta['label'],counts)
        graph_meta.update(benchmark=benchmark, side=side, top=top,
                          sources=meta['sources'], yosys_json_sha256=digest(target/'yosys.json'),
                          source_level='automatic_original_Verilog_spans_unreviewed',
                          synthesis_flow='existing provenance JSON; memory_collect; memory_map; opt; techmap; opt',
                          acceptance='provisional_not_training_eligible')
        torch.save(graph,target/'graph.pt')
        (target/'metadata.json').write_text(json.dumps(graph_meta,indent=2))
        result['graph_verification'] = verify_one(target)
        result['node_growth_ratio'] = graph.num_nodes/meta['num_nodes']
    (target/'status.json').write_text(json.dumps(result,indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--benchmark', choices=['AES-T100','RS232-T2100'], action='append')
    args = parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    rows = []
    for benchmark in args.benchmark or ['RS232-T2100','AES-T100']:
        for side in ['clean','trojan']:
            row = build(benchmark,side)
            rows.append(row)
            print(json.dumps(row),flush=True)
    (OUT/'pilot_summary.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':
    main()
