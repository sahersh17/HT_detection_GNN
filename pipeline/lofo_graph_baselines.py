"""Flow-independent graph-statistics and two-round directed WL baselines."""
import hashlib
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import torch
import torch.nn.functional as F
from config import ROOT
from metrics import auroc
from extended_lofo import average_precision


def signature(meta):
    return hashlib.sha256(json.dumps(sorted((Path(k).name,v) for k,v in meta['sources'].items()
                                            if Path(k).name!='converted.v')).encode()).hexdigest()


def stats(graph):
    x=graph.x
    onehot=x[:,:-4]
    numeric=x[:,-4:]
    pieces=[onehot.mean(0), torch.log1p(torch.tensor([graph.num_nodes,graph.num_edges],dtype=torch.float32))]
    for col in range(4):
        value=torch.log1p(numeric[:,col].clamp(min=0))
        pieces.extend([value.mean().view(1),value.std(unbiased=False).view(1),
                       torch.quantile(value,torch.tensor(.9)).view(1)])
    for col in range(4):
        values=numeric[:,col].long().clamp(min=0)
        # Fixed logarithmic degree/distance histograms, including an overflow bin.
        hist=torch.bincount(torch.floor(torch.log2(values.float()+1)).long().clamp(max=12),minlength=13).float()
        pieces.append(hist/len(values))
    return torch.cat(pieces)


def wl(graph, bins=512, rounds=2):
    x=graph.x
    colors=x[:,:-4].argmax(1).tolist()
    src,dst=graph.edge_index.tolist()
    incoming=[[] for _ in colors]; outgoing=[[] for _ in colors]
    for a,b in zip(src,dst):
        outgoing[a].append(b); incoming[b].append(a)
    result=[]
    for _ in range(rounds):
        features=torch.zeros(bins,dtype=torch.float32)
        for c in colors:
            features[c%bins]+=1
        result.append(features/len(colors))
        updated=[]
        for i,c in enumerate(colors):
            ins=','.join(map(str,sorted(colors[j] for j in incoming[i])))
            outs=','.join(map(str,sorted(colors[j] for j in outgoing[i])))
            token=f'{c}|I:{ins}|O:{outs}'.encode()
            updated.append(int.from_bytes(hashlib.blake2b(token,digest_size=8).digest(),'little')%bins)
        colors=updated
    features=torch.zeros(bins,dtype=torch.float32)
    for c in colors:
        features[c%bins]+=1
    result.append(features/len(colors))
    return torch.cat(result)


def fit_predict(xtr,y,w,xte,seed):
    mean=xtr.mean(0); std=xtr.std(0).clamp(min=1e-6)
    xtr=(xtr-mean)/std; xte=(xte-mean)/std
    torch.manual_seed(seed)
    model=torch.nn.Linear(xtr.shape[1],2)
    opt=torch.optim.LBFGS(model.parameters(),max_iter=100)
    def closure():
        opt.zero_grad()
        loss=(F.cross_entropy(model(xtr),y,reduction='none')*w).mean()+.01*model.weight.square().sum()
        loss.backward(); return loss
    opt.step(closure)
    with torch.no_grad(): return model(xte).softmax(-1)[:,1].tolist()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'data/lofo_detection/protocol.json')
    parser.add_argument('--cohort',choices=['all','mapped','yosys_verilog'],default='all')
    args=parser.parse_args()
    root=args.manifest.resolve().parent
    if not root.is_relative_to(ROOT) or not (root/'protocol.json').exists():
        parser.error('Manifest must be an existing repository protocol.json')
    manifest=json.loads((root/'protocol.json').read_text())
    records=[]
    for item in manifest['samples']:
        flow=('mapped' if 'new_gate_v1' in item['path'] else
              'ghdl_vhdl' if 'new_vhdl_v1' in item['path'] else 'yosys_verilog')
        if args.cohort!='all' and flow!=args.cohort:
            continue
        path=ROOT/item['path']; meta=json.loads(path.with_name('metadata.json').read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError(f"Graph hash mismatch: {path}")
        for source,expected in meta['sources'].items():
            if hashlib.sha256((ROOT/source).read_bytes()).hexdigest()!=expected:
                raise ValueError(f"Source hash mismatch: {source}")
        from train_cv import _safe_classes
        with torch.serialization.safe_globals(_safe_classes()):
            graph=torch.load(path,weights_only=True,map_location='cpu')
        records.append(dict(**item,source_id=signature(meta),graph=graph))
    families=sorted({s['family'] for s in records})
    features={'statistics':torch.stack([stats(s['graph']) for s in records]),
              'wl2':torch.stack([wl(s['graph']) for s in records]),
              'size':torch.stack([torch.log1p(torch.tensor([s['graph'].num_nodes,s['graph'].num_edges],dtype=torch.float32)) for s in records])}
    outputs={method:[] for method in features}
    seed=42
    for fold,family in enumerate(families):
        train=[i for i,s in enumerate(records) if s['family']!=family]
        test=[i for i,s in enumerate(records) if s['family']==family]
        groups=Counter((records[i]['family'],records[i]['label'],records[i]['source_id']) for i in train)
        unique=Counter((f,l) for f,l,_ in groups)
        weights=torch.tensor([len(train)/(len(families)*2*unique[records[i]['family'],records[i]['label']]*groups[records[i]['family'],records[i]['label'],records[i]['source_id']]) for i in train])
        labels=torch.tensor([records[i]['label'] for i in train])
        for method,matrix in features.items():
            probs=fit_predict(matrix[train],labels,weights,matrix[test],seed+fold)
            outputs[method].extend(dict(fold=fold,family=family,benchmark=records[i]['benchmark'],side=records[i]['side'],
                                        true_label=records[i]['label'],prob_trojan=p,predicted_label=int(p>=.5),
                                        source_id=records[i]['source_id']) for i,p in zip(test,probs))
        print(f'{family}: baselines complete',flush=True)
    summary={}
    for method,rows in outputs.items():
        per={}
        for family in families:
            group=[r for r in rows if r['family']==family]
            labels=[r['true_label'] for r in group]; scores=[r['prob_trojan'] for r in group]
            pairs=defaultdict(dict)
            for row in group: pairs[row['benchmark']][row['true_label']]=row['prob_trojan']
            valid=[p for p in pairs.values() if set(p)=={0,1}]
            pairacc=sum(1 if p[1]>p[0] else .5 if p[1]==p[0] else 0 for p in valid)/len(valid) if valid else None
            ap=average_precision(labels,scores)
            per[family]=dict(n=len(group),auroc=auroc(labels,scores),average_precision=ap,pairs=len(valid),pairwise_accuracy=pairacc)
        summary[method]=per
        outroot=root if args.cohort=='all' else root/f'baselines_{args.cohort}'
        outroot.mkdir(parents=True,exist_ok=True)
        out=outroot/f'{method}_predictions.json'; out.write_text(json.dumps(rows,indent=2))
    (outroot/'graph_baselines.json').write_text(json.dumps(dict(seed=seed,cohort=args.cohort,summary=summary),indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
