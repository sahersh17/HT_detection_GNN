"""Verify every planned fold and summarize seed variability, not host uncertainty."""
import json
import statistics
import time
import argparse
from collections import defaultdict
from confounder_study import OUT, SEEDS, evaluate


def main():
    scores = defaultdict(list)
    verified = 0
    for seed in SEEDS:
        root = OUT / f'seed_{seed}'
        protocol = json.loads((root/'protocol.json').read_text())
        inputs = {(s['benchmark'],s['side']):s for s in protocol['inputs']}
        for cohort in protocol['cohorts']:
            eligible = [s for s in inputs.values() if cohort=='all' or s['domain']==cohort]
            families = sorted({s['family'] for s in eligible})
            for arm in protocol['arms']:
                for family in families:
                    result = json.loads((root/f'{cohort}_{family}_{arm}.json').read_text())
                    predictions = result['predictions']
                    expected = {(s['benchmark'],s['side']) for s in eligible if s['family']==family}
                    assert len(predictions)==len(expected)
                    assert {(p['benchmark'],p['side']) for p in predictions} == expected
                    train_paths = {s['path'] for s in eligible if s['family']!=family}
                    assert set(result['scaler']['fitted_paths']) == train_paths
                    assert all(0<=p['probability']<=1 for p in predictions)
                    rows = [inputs[p['benchmark'],p['side']] for p in predictions]
                    assert all(p['label']==s['label'] and p['source_id']==s['source_id'] for p,s in zip(predictions,rows))
                    assert result['metrics']==evaluate(rows,[p['probability'] for p in predictions])
                    for metric in ['all_records','unique_sources']:
                        scores[cohort,arm,metric,seed].append(result['metrics'][metric]['balanced_accuracy'])
                    verified += 1
    summary = {}
    for cohort,arm,metric,_ in sorted(scores):
        key = f'{cohort}/{arm}/{metric}'
        values = [statistics.mean(scores[cohort,arm,metric,seed]) for seed in SEEDS]
        summary[key] = dict(seed_family_mean_ba=values, mean=statistics.mean(values),
                            seed_std=statistics.stdev(values))
    report = dict(verified_fold_runs=verified, seed_std_is_not_host_confidence_interval=True, summary=summary)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2))
    lines = ['# Controlled GCN results', '',
             'All 220 planned fold runs verified. Standard deviations describe seed variability, not uncertainty across independent hosts.', '',
             '| Cohort | Arm | Unique-source family mean BA | Seed SD |', '|---|---|---:|---:|']
    for key,value in summary.items():
        cohort,arm,metric = key.split('/')
        if metric=='unique_sources':
            lines.append(f'| {cohort} | {arm} | {100*value["mean"]:.2f}% | {100*value["seed_std"]:.2f} pp |')
    lines += ['', 'The same-recipe cohort changes host composition and still contains differing circuit representations. It does not isolate a causal synthesis effect.',
              'These are development results on already inspected families. No architecture or threshold was selected using these outputs.']
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    if args.watch:
        deadline = time.monotonic()+21600
        while sum(len(list((OUT/f'seed_{seed}').glob('all_*.json'))) +
                  len(list((OUT/f'seed_{seed}').glob('yosys_verilog_*.json'))) for seed in SEEDS)<220:
            if time.monotonic()>deadline:
                raise TimeoutError('Study incomplete after six hours; partial fold outputs retained')
            time.sleep(30)
    main()
