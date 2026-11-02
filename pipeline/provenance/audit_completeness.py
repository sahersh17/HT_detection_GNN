"""Independently audit cell coverage and bit-derived connectivity against Yosys JSON.

This complements tensor reconstruction: it never calls graph_from_json.
It proves coverage of the synthesized JSON, not equivalence to original RTL.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from train_cv import _safe_classes

EXCLUDED = {'$scopeinfo', '$print', '$display'}


def audit(document, metadata, graph):
    module = document['modules'][metadata['top']]
    cells = {n: c for n, c in module['cells'].items() if c['type'].lower() not in EXCLUDED}
    names = metadata['node_names']
    if len(set(names)) != len(names) or set(names) != set(cells):
        raise ValueError('Graph does not contain exactly the synthesized hardware cells')
    if graph.num_nodes != len(cells) or len(metadata['node_types']) != len(names):
        raise ValueError('Cell count differs from graph/metadata')
    if any(metadata['node_types'][i] != cells[n]['type'] for i, n in enumerate(names)):
        raise ValueError('Cell type differs from synthesized cell')
    if graph.x.shape != (len(names), 20) or not torch.isfinite(graph.x).all():
        raise ValueError('Invalid node features')
    if graph.graph_id != metadata['graph_id'] or int(graph.y.item()) != metadata['label']:
        raise ValueError('Graph identity or label mismatch')
    index = {n: i for i, n in enumerate(names)}
    drivers, consumers = defaultdict(set), defaultdict(set)
    constants = 0
    for name, cell in cells.items():
        if set(cell['connections']) != set(cell['port_directions']):
            raise ValueError(f'Missing port direction: {name}')
        for port, bits in cell['connections'].items():
            direction = cell['port_directions'][port]
            if direction not in ('input', 'output'):
                raise ValueError(f'Unsupported port direction: {name}/{port}/{direction}')
            for bit in bits:
                if isinstance(bit, int):
                    (drivers if direction == 'output' else consumers)[bit].add(name)
                elif direction == 'input':
                    constants += 1
    if any(len(v) > 1 for v in drivers.values()):
        raise ValueError('Multiple cell drivers')
    expected = {(index[a], index[b]) for bit, sources in drivers.items()
                for a in sources for b in consumers.get(bit, ()) if a != b}
    if graph.edge_index.ndim != 2 or graph.edge_index.shape[0] != 2:
        raise ValueError('Invalid edge tensor shape')
    actual_rows = graph.edge_index.T.tolist()
    actual = set(map(tuple, actual_rows))
    if len(actual) != len(actual_rows) or actual != expected:
        raise ValueError(f'Connectivity mismatch: missing={len(expected-actual)}, extra={len(actual-expected)}')
    inputs = {bit for p in module.get('ports', {}).values() if p['direction'] in ('input', 'inout')
              for bit in p['bits'] if isinstance(bit, int)}
    undriven = sorted(set(consumers) - set(drivers) - inputs)
    types = Counter(c['type'] for c in cells.values())
    sequential = sum(n for t, n in types.items() if re.search(r'dff|latch', t, re.I))
    expected_dff = [bool(re.search(r'dff|latch', cells[name]['type'], re.I)) for name in names]
    if graph.x[:, 4].tolist() != [float(v) for v in expected_dff]:
        raise ValueError('Sequential cells missing or mislabeled in DFF feature column')
    return dict(graph_id=graph.graph_id, status='passed', cells=len(cells), edges=len(expected),
                sequential_cells=sequential, memory_cells=sum(n for t,n in types.items() if 'mem' in t.lower()),
                memory_definitions=len(module.get('memories', {})), cell_types=dict(types),
                primary_input_bits=len(inputs), constant_input_connections=constants,
                undriven_internal_bits=undriven,
                excluded_types=dict(Counter(c['type'] for c in module['cells'].values() if c['type'].lower() in EXCLUDED)))


def audit_folder(folder):
    metadata = json.loads((folder / 'metadata.json').read_text())
    document = json.loads((folder / 'yosys.json').read_text())
    with torch.serialization.safe_globals(_safe_classes()):
        graph = torch.load(folder / 'graph.pt', map_location='cpu', weights_only=True)
    return audit(document, metadata, graph)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    folders = sorted(p.parent for p in args.root.glob('*/*/metadata.json'))
    if not folders:
        parser.error('No graphs found')
    rows = [audit_folder(p) for p in folders]
    result = dict(status='passed', graphs=len(rows), cells=sum(r['cells'] for r in rows),
                  sequential_cells=sum(r['sequential_cells'] for r in rows),
                  graphs_with_undriven_internal_bits=sum(bool(r['undriven_internal_bits']) for r in rows),
                  scope='Synthesized JSON cell/edge coverage; not RTL behavior equivalence', records=rows)
    (args.root / 'completeness.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k != 'records'}, indent=2))


if __name__ == '__main__':
    main()
