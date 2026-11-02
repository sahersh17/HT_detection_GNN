"""Matched host-diversity experiment, fixed settings and paired host seeds.

Compare two-host training with four-host training on the SAME AES/RS232
holdouts; also report full four-host LOFO separately. All are inspected
exploratory hosts, not an independent final test.
"""
import hashlib
import json
from pathlib import Path
import sys
import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipeline'))
from train_lofo import load_cohort, sample_weights
from models import GNNOnly
from metrics import summarize_predictions

OUT=ROOT/'runs/stepwise/host_study'
FAMILIES=['AES','RS232','memctrl','PIC16F84']


def main():
    torch.set_num_threads(4)
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for root in ['provenance_v1','expansion_graphs','expansion_pic_graphs']:
        p=ROOT/'runs'/root
        audit=json.loads((p/'completeness.json').read_text())
        verify=json.loads((p/'verification.json').read_text())
        assert audit['status']=='passed' and verify['status']=='verified'
        for graph in sorted(p.glob('*/*/graph.pt')):
            benchmark,side=graph.parent.parent.name,graph.parent.name
            rows.append(dict(benchmark=benchmark,side=side,label=int(side=='trojan'),family=benchmark.split('-')[0],path=graph.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(graph.read_bytes()).hexdigest()))
    assert len(rows)==52
    manifest=OUT/'cohort.json'
    manifest.write_text(json.dumps({'samples':rows,'status':'exploratory_52_graphs'},indent=2))
    samples=load_cohort(manifest)
    protocol=dict(status='running',epochs=25,seed_by_family={f:42+i for i,f in enumerate(FAMILIES)},hidden=64,lr=3e-4,weight_decay=.001,threshold=.5,weighting='source_balanced',features='raw',controls='same held-out graphs and per-family seed in both conditions',limitations=['Four previously inspected host families','PIC source includes an undriven c_in bit; graph matches synthesis','No new independent final test'])
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    combined={}
    for condition,allowed in [('two_hosts',['AES','RS232']),('four_hosts',FAMILIES)]:
        cohort=[s for s in samples if s['family'] in allowed]
        target=OUT/condition;target.mkdir(exist_ok=True)
        predictions=[];train_metrics={}
        for family in allowed:
            seed=protocol['seed_by_family'][family]
            torch.manual_seed(seed)
            train=[s for s in cohort if s['family']!=family]
            test=[s for s in cohort if s['family']==family]
            assert {s['source_id'] for s in train}.isdisjoint({s['source_id'] for s in test})
            weights=sample_weights(train,'source_balanced')
            labels=torch.tensor([s['label'] for s in train])
            net=GNNOnly();opt=torch.optim.AdamW(net.parameters(),lr=3e-4,weight_decay=1e-3)
            net.train()
            for epoch in range(25):
                total=0
                for i in torch.randperm(len(train)).tolist():
                    opt.zero_grad(set_to_none=True)
                    loss=torch.nn.functional.cross_entropy(net(train[i]['graph'])['logits'],labels[i:i+1])*weights[i]
                    loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),1.);opt.step();total+=float(loss.detach())
                if epoch in (0,12,24):print(condition,family,'epoch',epoch+1,'loss',total/len(train),flush=True)
            torch.save(net.state_dict(),target/f'{family}.pt')
            net.eval();train_rows=[]
            with torch.no_grad():
                for split,records in [('train',train),('test',test)]:
                    for s in records:
                        prob=float(net(s['graph'])['logits'].softmax(-1)[0,1])
                        row=dict(fold=FAMILIES.index(family),held_out_family=family,family=s['family'],benchmark=s['benchmark'],true_label=s['label'],predicted_label=int(prob>=.5),prob_trojan=prob)
                        (train_rows if split=='train' else predictions).append(row)
            train_metrics[family]=summarize_predictions(train_rows)['pooled']
            (target/'predictions.partial.json').write_text(json.dumps(predictions,indent=2))
            print(condition,family,'test',summarize_predictions([r for r in predictions if r['held_out_family']==family])['pooled'],flush=True)
        metrics=summarize_predictions(predictions)
        result=dict(status='complete',metrics=metrics,train_metrics=train_metrics,mean_family_balanced_accuracy=sum(metrics[f'fold_{FAMILIES.index(f)}']['balanced_accuracy'] for f in allowed)/len(allowed))
        (target/'predictions.json').write_text(json.dumps(predictions,indent=2))
        (target/'summary.json').write_text(json.dumps(result,indent=2))
        common=[r for r in predictions if r['family'] in ['AES','RS232']]
        combined[condition]=dict(original_42_holdout_metrics=summarize_predictions(common),full_metrics=metrics,mean_family_balanced_accuracy=result['mean_family_balanced_accuracy'])
    combined['matched_42_balanced_accuracy_delta']=combined['four_hosts']['original_42_holdout_metrics']['pooled']['balanced_accuracy']-combined['two_hosts']['original_42_holdout_metrics']['pooled']['balanced_accuracy']
    (OUT/'comparison.json').write_text(json.dumps(combined,indent=2))
    protocol['status']='complete';(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    print(json.dumps(combined,indent=2))


if __name__=='__main__':main()
