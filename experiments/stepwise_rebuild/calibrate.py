"""Exploratory threshold selection using ONLY training-cohort OOF predictions.

External labels are opened only after selected thresholds are saved. This
is cross-fitted threshold selection, not an untouched confirmatory test.
"""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipeline'))
from metrics import summarize, summarize_predictions
OUT=ROOT/'runs/stepwise'


def select(rows):
    probs=sorted(set(r['prob_trojan'] for r in rows))
    candidates=sorted(set([0.0,0.5,1.0,*[(a+b)/2 for a,b in zip(probs,probs[1:])]]))
    scored=[]
    for threshold in candidates:
        metrics=summarize([r['true_label'] for r in rows],[int(r['prob_trojan']>=threshold) for r in rows])
        scored.append((metrics['balanced_accuracy'],-abs(threshold-.5),-threshold,threshold))
    best=max(scored)
    return dict(threshold=best[-1],training_oof_balanced_accuracy=best[0])


def main():
    selected={}
    for model,tag in [('gnn','rebuilt_gnn'),('rtl','clean_rtl'),('fusion','clean_fusion')]:
        p=OUT/tag/'predictions.json'
        selected[model]=dict(**select(json.loads(p.read_text())),source=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    protocol=dict(rule='Maximize training-cohort out-of-fold balanced accuracy; ties closest to 0.5, then lower threshold',status='thresholds_selected_without_reading_external_labels',models=selected)
    (OUT/'calibration_thresholds.json').write_text(json.dumps(protocol,indent=2))
    results={}
    for model,choice in selected.items():
        rows=json.loads((OUT/f'external_{model}'/'predictions.json').read_text())
        calibrated=[dict(r,predicted_label=int(r['prob_trojan']>=choice['threshold'])) for r in rows]
        results[model]=dict(threshold=choice['threshold'],fixed=summarize_predictions(rows)['pooled'],calibrated=summarize_predictions(calibrated)['pooled'])
    (OUT/'calibration_results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
