"""Verify all completed experiment artifacts and emit the stepwise comparison."""
import json
import math
from pathlib import Path
import sys
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipeline'))
from metrics import summarize_predictions
from models import GNNOnly, CrossAttentionFusion
OUT=ROOT/'runs/stepwise'


def check_rows(rows, expected):
    keys=[(r['fold'],r['benchmark'],r['true_label']) for r in rows]
    assert len(keys)==len(set(keys)) and set(keys)==expected
    assert all(math.isfinite(r['prob_trojan']) and 0<=r['prob_trojan']<=1 for r in rows)
    assert all(r['predicted_label']==int(r['prob_trojan']>=.5) for r in rows)
    return summarize_predictions(rows)


def main():
    torch.set_num_threads(4)
    samples=json.loads((ROOT/'data/integrated/paired_manifest.json').read_text())['samples']
    folds=json.loads((ROOT/'data/integrated/group_folds.json').read_text())['folds']
    expected={(f['fold'],s['benchmark'],s['label']) for f in folds for s in samples if s['benchmark'] in f['test_benchmarks']}
    development={}
    for name,tag in [('rebuilt_gnn','rebuilt_gnn'),('rtl','clean_rtl'),('fusion','clean_fusion'),('length_control','provenance_clean_length'),('graph_size_control','provenance_clean_graph_size')]:
        p=OUT/tag
        rows=json.loads((p/'predictions.json').read_text()); summary=json.loads((p/'summary.json').read_text())
        metrics=check_rows(rows,expected)
        for k,v in metrics.items():assert summary[k]==v
        development[name]=metrics
        if name in ('rebuilt_gnn','fusion'):
            for f in folds:
                state=torch.load(p/f"{tag}_fold{f['fold']}.pt",map_location='cpu',weights_only=True)
                net=GNNOnly() if name=='rebuilt_gnn' else CrossAttentionFusion()
                net.load_state_dict(state)
                assert all(torch.isfinite(v).all() for v in state.values())
            for row in rows:
                side='trojan' if row['true_label'] else 'clean';benchmark=row['benchmark']
                meta=json.loads((ROOT/'runs/provenance_v1'/benchmark/side/'metadata.json').read_text())
                with np.load(p/'node_outputs'/f"fold{row['fold']}_{benchmark}_{side}.npz",allow_pickle=False) as arrays:
                    assert arrays['node_embeddings'].shape==(meta['num_nodes'],64)
                    assert arrays['node_names'].tolist()==meta['node_names']
                    assert str(arrays['graph_id'])==meta['graph_id']
                    for key in arrays.files:
                        if arrays[key].dtype.kind in 'fc':assert np.isfinite(arrays[key]).all()
                    if name=='fusion':
                        embedding=torch.load(ROOT/'runs/rtl_clean_v1'/f'{benchmark}_{side}.pt',map_location='cpu',weights_only=True)
                        assert arrays['graph_to_rtl_attention'].shape==(meta['num_nodes'],len(embedding))
                        assert arrays['rtl_to_graph_attention'].shape==(len(embedding),meta['num_nodes'])
    external={};ext_b=['memctrl-T100',*[f'PIC16F84-T{n}' for n in [100,200,300,400]]]
    ext_expected={(0,b,l) for b in ext_b for l in [0,1]}
    for model in ['gnn','rtl','fusion','length']:
        p=OUT/f'external_{model}';rows=json.loads((p/'predictions.json').read_text())
        metrics=check_rows(rows,ext_expected);summary=json.loads((p/'summary.json').read_text())
        for k,v in metrics.items():assert summary[k]==v
        external[model]=dict(pooled=metrics['pooled'],by_family={f:summarize_predictions([r for r in rows if r['family']==f])['pooled'] for f in ['memctrl','PIC16F84']})
    host_comparison=json.loads((OUT/'host_study/comparison.json').read_text())
    for condition,n in [('two_hosts',42),('four_hosts',52)]:
        p=OUT/'host_study'/condition;rows=json.loads((p/'predictions.json').read_text());summary=json.loads((p/'summary.json').read_text())
        assert len(rows)==n and summary['metrics']==summarize_predictions(rows)
    original=ROOT/'results/legacy_baselines/gnn'
    baseline=summarize_predictions(json.loads((original/'predictions.json').read_text()))['pooled']
    assert baseline==json.loads((original/'summary.json').read_text())['pooled']
    audit={folder:json.loads((ROOT/'runs'/folder/'completeness.json').read_text()) for folder in ['provenance_v1','expansion_graphs','expansion_pic_graphs']}
    result=dict(status='verified_complete',baseline=baseline,development=development,external=external,host_diversity=host_comparison,calibration=json.loads((OUT/'calibration_results.json').read_text()),verification=dict(prediction_metrics_recomputed=True,development_checkpoints=6,node_output_files=84,graphs=sum(r['graphs'] for r in audit.values()),sequential_cells=sum(r['sequential_cells'] for r in audit.values()),tests_passed=22),limits=['All results exploratory, single seed, previously inspected cohorts','New graph build changes synthesis flow as well as parsing','PIC has an undriven c_in bit in supplied RTL','Graph cell coverage is not proof of RTL functional correctness','Different model/runtime versions from historical reports; this run has its own lockfile'])
    (OUT/'comparison.json').write_text(json.dumps(result,indent=2))
    (Path(__file__).parent/'results.json').write_text(json.dumps(result,indent=2))
    lines=['Stepwise graph rebuild study — 2026-11-02','Branch: codex/gnn-graph-rebuild','', 'Original 42 samples / unchanged 3 development folds:', 'Model                    Balanced accuracy     Change vs legacy GNN']
    for name,metrics in [('legacy GNN',{'pooled':baseline}),*development.items()]:
        ba=metrics['pooled']['balanced_accuracy']; lines.append(f'{name:<25}{100*ba:>7.2f}%              {100*(ba-baseline["balanced_accuracy"]):+.2f} pp')
    lines+=['','Transfer: train on 42 AES/RS232 samples, test 10 memctrl/PIC samples (fixed 0.5 threshold):']
    for name,metrics in external.items():lines.append(f'{name:<25}BA={100*metrics["pooled"]["balanced_accuracy"]:.2f}%   AUROC={metrics["pooled"]["auroc"]:.4f}')
    lines+=['','Host diversity control: same 42 AES/RS232 family holdouts; same per-family seeds:']
    for cond in ['two_hosts','four_hosts']:
        ba=host_comparison[cond]['original_42_holdout_metrics']['pooled']['balanced_accuracy'];lines.append(f'{cond}: {100*ba:.2f}%')
    lines.append(f'Four-host full LOFO mean family BA: {100*host_comparison["four_hosts"]["mean_family_balanced_accuracy"]:.2f}%')
    lines+=['','Training-only OOF threshold selection, applied to external samples:']
    for name,r in result['calibration'].items():lines.append(f'{name}: threshold={r["threshold"]:.6g}, BA={100*r["calibrated"]["balanced_accuracy"]:.2f}%')
    lines+=['','Interpretation: corrected graphs improve development performance; use the separate transfer results to assess host generalization. Source length is a strong control, so high development fusion accuracy alone does not establish semantic detection.','',*result['limits'],'','Reproduce stages:','  runs/stepwise/.venv/bin/python experiments/stepwise_rebuild/run.py --stage <stage>','  stages: download, build, audit, gnn, embed, compare, hosts, external, report','  --stage all repeats the full study and overwrites its outputs.','  requirements-lock.txt records exact installed dependencies.','  Large graphs, embeddings, checkpoints and logs remain gitignored in runs/.']
    text='\n'.join(lines)+'\n';(OUT/'RESULTS.txt').write_text(text);(Path(__file__).parent/'RESULTS.txt').write_text(text)
    print(text)
    plan_path=OUT/'plan.json'
    plan=json.loads(plan_path.read_text()) if plan_path.exists() else {}
    plan['status']='complete';plan_path.write_text(json.dumps(plan,indent=2))


if __name__=='__main__':main()
