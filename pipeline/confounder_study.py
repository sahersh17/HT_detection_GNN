"""Controlled GCN study: numeric scaling, repeated sources, seeds, flow cohorts."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import torch
import torch.nn.functional as F
from config import ROOT
from models import GNNOnly
from train_cv import _safe_classes
from metrics import summarize

OUT = ROOT / 'data/confounder_study'
SEEDS = [42, 43, 44, 45, 46]


def load():
    protocol = json.loads((ROOT / 'data/lofo_detection/protocol.json').read_text())
    rows = []
    for item in protocol['samples']:
        s = dict(item)
        path = ROOT / s['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == s['sha256']
        meta = json.loads(path.with_name('metadata.json').read_text())
        sources = sorted((Path(k).name, v) for k,v in meta['sources'].items() if Path(k).name != 'converted.v')
        s['source_id'] = hashlib.sha256(json.dumps(sources).encode()).hexdigest()
        for relative, expected in meta['sources'].items():
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
        s['domain'] = ('mapped' if 'new_gate_v1' in s['path'] else
                       'ghdl' if 'new_vhdl_v1' in s['path'] else 'yosys_verilog')
        with torch.serialization.safe_globals(_safe_classes()):
            s['graph'] = torch.load(path, weights_only=True, map_location='cpu')
        s['unknown_fraction'] = sum(x == 'OTHER' for x in meta['node_gate_classes']) / s['graph'].num_nodes
        rows.append(s)
    for source in {s['source_id'] for s in rows}:
        group = [s for s in rows if s['source_id'] == source]
        if len({s['family'] for s in group}) != 1 or len({s['label'] for s in group}) != 1:
            raise ValueError('Source duplication crosses family or label boundaries')
    return rows


def weights_for(rows, dedup):
    families = Counter(s['family'] for s in rows)
    copies = Counter((s['family'], s['label'], s['source_id']) for s in rows)
    unique = Counter((f, label) for f,label,_ in copies)
    return torch.tensor([len(rows)/(len(families)*2*unique[s['family'],s['label']]*copies[s['family'],s['label'],s['source_id']])
                         if dedup else len(rows)/(len(families)*families[s['family']]) for s in rows])


def fit_scaler(train):
    # Equal contribution per unique source within each family/class.
    weights = weights_for(train, True)
    means, seconds = [], []
    for s in train:
        x = torch.log1p(s['graph'].x[:, -4:].double())
        means.append(x.mean(0))
        seconds.append(x.square().mean(0))
    mean = (torch.stack(means)*weights[:,None]).sum(0)/weights.sum()
    second = (torch.stack(seconds)*weights[:,None]).sum(0)/weights.sum()
    return mean.float(), (second-mean.square()).clamp(min=1e-6).sqrt().float()


def evaluate(rows, probs):
    raw = summarize([s['label'] for s in rows], [int(p>=.5) for p in probs], probs)
    groups = defaultdict(list)
    for s,p in zip(rows, probs):
        groups[s['label'],s['source_id']].append(p)
    labels = [k[0] for k in groups]
    averaged = [sum(v)/len(v) for v in groups.values()]
    unique = summarize(labels, [int(p>=.5) for p in averaged], averaged)
    return dict(all_records=raw, unique_sources=unique)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, required=True, choices=SEEDS)
    args = parser.parse_args()
    torch.set_num_threads(1)
    rows = load()
    OUT.mkdir(parents=True, exist_ok=True)
    audit = []
    for family in sorted({s['family'] for s in rows}):
        subset = [s for s in rows if s['family']==family]
        values = torch.cat([s['graph'].x[:,-4:] for s in subset])
        audit.append(dict(family=family, records=len(subset), domains=sorted({s['domain'] for s in subset}),
                          unique_clean_sources=len({s['source_id'] for s in subset if s['label']==0}),
                          unique_trojan_sources=len({s['source_id'] for s in subset if s['label']==1}),
                          unknown_fraction_range=[min(s['unknown_fraction'] for s in subset), max(s['unknown_fraction'] for s in subset)],
                          numeric_min=values.min(0).values.tolist(), numeric_max=values.max(0).values.tolist()))
    # Independent seed outputs avoid concurrent writers.
    seed_out = OUT / f'seed_{args.seed}'
    seed_out.mkdir(exist_ok=True)
    (seed_out / 'audit.json').write_text(json.dumps(audit, indent=2))
    protocol = dict(seeds=SEEDS, epochs=25, lr=3e-4, wd=.001, architecture='unchanged GNNOnly hidden64',
                    threshold=.5, scaling='log1p last four features, training-only weighted moments',
                    arms=['raw', 'scaled', 'dedup', 'scaled_dedup'],
                    cohorts=['all', 'yosys_verilog'],
                    caveat='Flow-restricted comparison changes host composition; not a causal estimate of synthesis effects',
                    inputs=[{k:v for k,v in s.items() if k!='graph'} for s in rows])
    (seed_out / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    for cohort in ['all', 'yosys_verilog']:
        eligible = [s for s in rows if cohort=='all' or s['domain']==cohort]
        families = sorted({s['family'] for s in eligible})
        for fold,family in enumerate(families):
            train = [s for s in eligible if s['family']!=family]
            test = [s for s in eligible if s['family']==family]
            mean,std = fit_scaler(train)
            for arm in ['raw', 'scaled', 'dedup', 'scaled_dedup']:
                target = seed_out / f'{cohort}_{family}_{arm}.json'
                if target.exists():
                    continue
                scaled, dedup = 'scaled' in arm, 'dedup' in arm
                graphs = {}
                for s in eligible:
                    g = s['graph'].clone()
                    if scaled:
                        g.x[:,-4:] = (torch.log1p(g.x[:,-4:])-mean)/std
                    graphs[s['path']] = g
                torch.manual_seed(args.seed + sorted({s['family'] for s in rows}).index(family))
                net = GNNOnly()
                opt = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=.001)
                weights = weights_for(train, dedup)
                for epoch in range(25):
                    net.train()
                    for i in torch.randperm(len(train)).tolist():
                        s = train[i]
                        opt.zero_grad(set_to_none=True)
                        loss = F.cross_entropy(net(graphs[s['path']])['logits'], torch.tensor([s['label']]))*weights[i]
                        loss.backward()
                        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.)
                        opt.step()
                net.eval()
                with torch.no_grad():
                    probs = [float(net(graphs[s['path']])['logits'].softmax(-1)[0,1]) for s in test]
                result = dict(seed=args.seed, cohort=cohort, family=family, arm=arm,
                              scaler=dict(mean=mean.tolist(), std=std.tolist(), fitted_paths=[s['path'] for s in train]),
                              predictions=[dict(benchmark=s['benchmark'], side=s['side'], label=s['label'], source_id=s['source_id'], probability=p) for s,p in zip(test,probs)],
                              metrics=evaluate(test,probs))
                target.write_text(json.dumps(result,indent=2))
                print(f'{args.seed} {cohort} {family} {arm}: BA={result["metrics"]["unique_sources"]["balanced_accuracy"]:.3f}', flush=True)


if __name__ == '__main__':
    main()
