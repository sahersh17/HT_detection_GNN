"""Pointwise precision planning from the six observed independent host scores."""
import json
from math import ceil
from pathlib import Path
from statistics import mean, stdev, NormalDist

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/"data/precision_v1"
RUN=ROOT/"runs/precision_v1"
PREV=ROOT/"data/overlap_six_v1"
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def report(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8",newline="\n")


def main():
    old=read(PREV/"admission.json")
    results=[]
    for domain,arm,k,ci in old["outside_equivalence_margin"]:
        detail=old["paired_controls" if domain=="class" else "origin_controls"][arm][k]
        mu=detail["mean"]; values=list(detail["by_host"].values()); sd=stdev(values)
        distance=min(mu-.3,.7-mu)
        n=ceil((NormalDist().inv_cdf(.975)*sd/distance)**2) if distance>0 else None
        results.append(dict(domain=domain,arm=arm,control=k,mean=mu,ci95=ci,sd=sd,
            includes_chance=ci[0]<=.5<=ci[1],mean_inside_band=distance>0,
            leave_one_out_range=[min(mean(values[:i]+values[i+1:]) for i in range(len(values))),
                                max(mean(values[:i]+values[i+1:]) for i in range(len(values)))],
            planning_n_if_mean_persists=n,planning_n_if_centered=ceil((1.96*sd/.2)**2)))
    target=max(r["planning_n_if_mean_persists"] for r in results)
    report(DATA/"planning.json",dict(basis="Pointwise expected normal-approximation half-width, pilot sample SD, means and variances held fixed. No simultaneous assurance.",
        pilot_families=6,estimated_total=target,estimated_additional=target-6,
        centered_scenario_total=max(r["planning_n_if_centered"] for r in results),intervals=results))
    print(target,target-6,sorted([(r["planning_n_if_mean_persists"],r["control"]) for r in results],reverse=True)[:5])
if __name__=="__main__": main()
