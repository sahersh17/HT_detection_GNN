"""Audit fold membership, input hashes and recorded LOFO metrics."""
import hashlib
import json
import math
from config import ROOT
from metrics import summarize_predictions


def main():
    folder = ROOT / 'data/lofo_detection'
    protocol = json.loads((folder / 'protocol.json').read_text())
    results = json.loads((folder / 'results.json').read_text())
    expected = {(s['benchmark'], s['side']): s for s in protocol['samples']}
    assert len(expected) == len(protocol['samples'])
    for s in expected.values():
        assert hashlib.sha256((ROOT / s['path']).read_bytes()).hexdigest() == s['sha256']
    for model in ('gnn', 'size'):
        rows = json.loads((folder / f'{model}_predictions.json').read_text())
        assert len(rows) == len(expected)
        assert {(r['benchmark'], r['side']) for r in rows} == set(expected)
        for r in rows:
            s = expected[r['benchmark'], r['side']]
            assert r['family'] == s['family'] == protocol['groups'][r['fold']]
            assert r['true_label'] == s['label']
            assert math.isfinite(r['prob_trojan']) and 0 <= r['prob_trojan'] <= 1
            assert r['predicted_label'] == int(r['prob_trojan'] >= protocol['threshold'])
        measured = summarize_predictions(rows)
        measured['mean_family_balanced_accuracy'] = sum(measured[f'fold_{i}']['balanced_accuracy'] for i in range(len(protocol['groups'])))/len(protocol['groups'])
        assert measured == results[model]
    print(f"Verified {len(expected)} predictions per model across {len(protocol['groups'])} family holdouts")


if __name__ == '__main__':
    main()
