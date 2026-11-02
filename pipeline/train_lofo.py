"""Hash-pinned, family-held-out graph evaluation over the integrated cohort."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import torch
import torch.nn.functional as F
from config import ROOT
from models import GNNOnly
from train_cv import _safe_classes
from metrics import summarize_predictions
from extended_lofo import average_precision, pairwise


def signature(meta):
    source_set=sorted((Path(name).name,digest) for name,digest in meta.get('sources',{}).items()
                      if Path(name).name!='converted.v')
    return hashlib.sha256(json.dumps(source_set).encode()).hexdigest()


def load_cohort(manifest_path):
    manifest=json.loads(manifest_path.read_text())
    samples=[]
    for record in manifest['samples']:
        path=ROOT/record['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError(f"Cohort graph hash mismatch: {record['path']}")
        metadata=json.loads(path.with_name('metadata.json').read_text())
        for source,digest in metadata.get('sources',{}).items():
            if hashlib.sha256((ROOT/source).read_bytes()).hexdigest()!=digest:
                raise ValueError(f"Cohort source hash mismatch: {source}")
        with torch.serialization.safe_globals(_safe_classes()):
            graph=torch.load(path,weights_only=True,map_location='cpu')
        if int(graph.y.item())!=int(record['label']) or not torch.isfinite(graph.x).all():
            raise ValueError(f"Bad graph label or features: {record['path']}")
        flow=('mapped' if 'new_gate_v1' in record['path'] else
              'ghdl_vhdl' if 'new_vhdl_v1' in record['path'] else 'common_yosys_verilog')
        samples.append(dict(benchmark=record['benchmark'],side=record['side'],family=record['family'],
                            label=int(record['label']),graph=graph,path=record['path'],source_id=signature(metadata),
                            source_level=metadata.get('source_level','original_verilog'),flow=flow))
    ids=[(s['benchmark'],s['side']) for s in samples]
    if len(ids)!=len(set(ids)) or len({s['family'] for s in samples})<2:
        raise ValueError('Cohort has duplicate rows or insufficient host groups')
    for s in samples:
        if (s['benchmark'],'clean' if s['side']=='trojan' else 'trojan') not in ids:
            raise ValueError(f"Unpaired sample: {s['benchmark']}")
    return samples


def sample_weights(train, mode):
    n=len(train); families=Counter(s['family'] for s in train)
    if mode=='record_balanced':
        return torch.tensor([n/(len(families)*families[s['family']]) for s in train])
    groups=Counter((s['family'],s['label'],s['source_id']) for s in train)
    unique=Counter((family,label) for family,label,_ in groups)
    return torch.tensor([n/(len(families)*2*unique[s['family'],s['label']]*groups[s['family'],s['label'],s['source_id']]) for s in train])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--features',choices=['raw','scaled','no_proxies','topology_only'],default='raw')
    parser.add_argument('--weighting',choices=['source_balanced','record_balanced'],default='source_balanced')
    parser.add_argument('--cohort',choices=['all','yosys_verilog','mapped'],default='all')
    parser.add_argument('--manifest',type=Path,default=ROOT/'data/lofo_detection/protocol.json')
    parser.add_argument('--only-family')
    args=parser.parse_args()
    torch.set_num_threads(4)
    manifest_path=args.manifest.resolve()
    if not manifest_path.is_relative_to(ROOT):
        parser.error('Manifest must be inside repository')
    samples=load_cohort(manifest_path)
    if args.cohort=='yosys_verilog':
        samples=[s for s in samples if s['flow']=='common_yosys_verilog']
    elif args.cohort=='mapped':
        samples=[s for s in samples if s['flow']=='mapped']
    families=sorted({s['family'] for s in samples})
    if args.only_family and args.only_family not in families:
        parser.error('Requested family is missing from the pinned cohort')
    target=ROOT/'runs/lofo_integrated'/manifest_path.parent.name/f'{args.cohort}_seed_{args.seed}_{args.features}_{args.weighting}'
    target.mkdir(parents=True,exist_ok=True)
    columns=list(range(samples[0]['graph'].x.shape[1]))
    if args.features=='no_proxies': columns=columns[:-2]
    elif args.features=='topology_only': columns=columns[-4:]
    folds=families if args.only_family is None else [args.only_family]
    protocol={'status':'running','cohort':manifest_path.relative_to(ROOT).as_posix(),'cohort_filter':args.cohort,'samples':len(samples),'families':families,
              'folds':folds,'seed':args.seed,'features':args.features,'weighting':args.weighting,
              'epochs':25,'threshold':.5,'lr':3e-4,'weight_decay':1e-3,'hidden':64,
              'scaler':'log1p + training-only, source/class/family weighted moments' if args.features=='scaled' else None,
              'loss_weights':'equal total contribution per family/class/source' if args.weighting=='source_balanced' else 'equal total contribution per family'}
    (target/'protocol.json').write_text(json.dumps(protocol,indent=2))
    predictions=[]
    for fold,family in enumerate(folds):
        train=[s for s in samples if s['family']!=family]
        test=[s for s in samples if s['family']==family]
        weights=sample_weights(train,args.weighting)
        labels=torch.tensor([s['label'] for s in train])
        if args.features=='scaled':
            means=[];seconds=[]
            for s in train:
                v=torch.log1p(s['graph'].x[:,-4:].double()); means.append(v.mean(0)); seconds.append(v.square().mean(0))
            normw=weights/weights.sum()
            mean=(torch.stack(means)*normw[:,None]).sum(0).float()
            std=((torch.stack(seconds)*normw[:,None]).sum(0)-mean.square()).clamp(min=1e-6).sqrt()
            for s in samples:
                g=s['graph'].clone(); g.x[:,-4:]=(torch.log1p(g.x[:,-4:])-mean)/std; s['work_graph']=g
        else:
            for s in samples:s['work_graph']=s['graph']
        torch.manual_seed(args.seed+fold)
        net=GNNOnly(node_dim=len(columns))
        opt=torch.optim.AdamW(net.parameters(),lr=3e-4,weight_decay=1e-3)
        for epoch in range(25):
            net.train()
            for i in torch.randperm(len(train)).tolist():
                graph=train[i]['work_graph'].clone(); graph.x=graph.x[:,columns]
                opt.zero_grad(set_to_none=True)
                loss=F.cross_entropy(net(graph)['logits'],labels[i:i+1])*weights[i]
                loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(),1.)
                opt.step()
        net.eval()
        with torch.no_grad():
            for s in test:
                graph=s['work_graph'].clone(); graph.x=graph.x[:,columns]
                prob=float(net(graph)['logits'].softmax(-1)[0,1])
                predictions.append(dict(fold=fold,family=family,benchmark=s['benchmark'],side=s['side'],
                                        true_label=s['label'],predicted_label=int(prob>=.5),prob_trojan=prob,
                                        source_id=s['source_id']))
        (target/'predictions.json').write_text(json.dumps(predictions,indent=2))
        print(f'{family}: finished {len(test)} pinned samples',flush=True)
    scores=summarize_predictions(predictions)
    per_family={}
    for family in folds:
        rows=[r for r in predictions if r['family']==family]
        fold_id=folds.index(family)
        per_family[family]=dict(auroc=scores[f'fold_{fold_id}']['auroc'],
                                average_precision=average_precision([r['true_label'] for r in rows],[r['prob_trojan'] for r in rows]),
                                pairwise=pairwise(rows),n=len(rows))
    result={'status':'smoke_single_family' if args.only_family else 'completed_family_LOFO',
            'metrics':scores,'per_family_rank_metrics':per_family}
    (target/'results.json').write_text(json.dumps(result,indent=2))
    protocol['status']=result['status']
    (target/'protocol.json').write_text(json.dumps(protocol,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
