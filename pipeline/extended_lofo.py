"""Add threshold-free, paired and source-dependence metrics to LOFO predictions."""
import json
import math
from collections import defaultdict
from config import ROOT


def average_precision(labels, scores):
    positives=sum(labels)
    if not positives:
        return None
    groups=defaultdict(list)
    for y,s in zip(labels,scores):
        groups[s].append(y)
    tp=fp=0
    ap=0.0
    for score in sorted(groups,reverse=True):
        ys=groups[score]
        tp += sum(ys)
        fp += len(ys)-sum(ys)
        ap += (sum(ys)/positives)*(tp/(tp+fp))
    return ap


def pairwise(rows):
    pairs=defaultdict(dict)
    for row in rows:
        pairs[row['benchmark']][row['true_label']]=row['prob_trojan']
    valid=[p for p in pairs.values() if set(p)=={0,1}]
    if not valid:
        return {'pairs':0,'accuracy':None}
    win=sum(1 if p[1]>p[0] else .5 if p[1]==p[0] else 0 for p in valid)
    return {'pairs':len(valid),'wins':win,'accuracy':win/len(valid)}


def signature(meta):
    return tuple(sorted((name.split('/')[-1],sha) for name,sha in meta['sources'].items()
                        if name.split('/')[-1] != 'converted.v'))


def main():
    folder=ROOT/'data/lofo_detection'
    protocol=json.loads((folder/'protocol.json').read_text())
    rows=json.loads((folder/'gnn_predictions.json').read_text())
    results={}
    for family in sorted({r['family'] for r in rows}):
        subset=[r for r in rows if r['family']==family]
        labels=[r['true_label'] for r in subset]
        scores=[r['prob_trojan'] for r in subset]
        sources={}
        for s in protocol['samples']:
            if s['family']==family:
                meta=json.loads((ROOT/s['path']).with_name('metadata.json').read_text())
                sources[(s['benchmark'],s['side'])]=signature(meta)
        clean_groups={sources[(r['benchmark'],'clean')] for r in subset if r['true_label']==0}
        results[family]={'samples':len(subset),'unique_clean_sources':len(clean_groups),
                         'auroc':None,'average_precision':average_precision(labels,scores),
                         'pairwise':pairwise(subset),
                         'predicted_classes':dict(clean=sum(r['true_label']==0 and r['predicted_label']==0 for r in subset),
                                                  trojan=sum(r['true_label']==1 and r['predicted_label']==1 for r in subset))}
        positives=sum(labels);negatives=len(labels)-positives
        if positives and negatives:
            from metrics import auroc
            results[family]['auroc']=auroc(labels,scores)
    pooled=__import__('metrics').summarize_predictions(rows)['pooled']
    results['_pooled']={'samples':len(rows),'auroc':pooled['auroc'],
                        'average_precision':average_precision([r['true_label'] for r in rows],[r['prob_trojan'] for r in rows]),
                        'pairwise':pairwise(rows)}
    out=folder/'extended_metrics.json'
    out.write_text(json.dumps({'status':'derived_from_fixed_seed_42_predictions','metrics':results},indent=2))
    print(out.read_text())


if __name__=='__main__':
    main()
