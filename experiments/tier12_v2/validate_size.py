"""Validate the nine-host v2 size screen, separately from detector evaluation."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/tier12_v2"


def read(path):
    return json.loads(path.read_text())


def percentile_bootstrap(scores):
    """Exact percentile endpoints over all ordered host resamples with replacement."""
    frequencies = Counter(round(2 * s) for s in scores)
    distribution = {0: 1}
    for _ in scores:
        updated = Counter()
        for total, count in distribution.items():
            for value, frequency in frequencies.items():
                updated[total + value] += count * frequency
        distribution = updated
    n = len(scores)
    accumulated = 0
    endpoints = []
    for total, count in sorted(distribution.items()):
        accumulated += count
        for q in (1, 39)[len(endpoints):]:
            if 40 * accumulated >= q * n**n:
                endpoints.append(total / (2 * n))
            else:
                break
    return endpoints


def dimensions(row):
    path = ROOT / "runs/tier12_v2" / row["host"] / row["variant"] / "yosys.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["mapped_json_sha256"]
    source = ROOT / row["source"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"]
    cells = read(path)["modules"]["top"]["cells"]
    # Reconstruct directed cell-to-cell adjacency from pin nets.
    drivers = {}
    consumers = defaultdict(set)
    for cell, rec in cells.items():
        for pin, bits in rec["connections"].items():
            for net in bits:
                if isinstance(net, int):
                    if rec["port_directions"][pin] == "output":
                        drivers[net] = cell
                    else:
                        consumers[net].add(cell)
    edges = {(drivers[net], dst) for net, dests in consumers.items() if net in drivers
             for dst in dests if drivers[net] != dst}
    return dict(characters=len(source.read_text()), nodes=len(cells), edges=len(edges))


def rank(a,b):
    return float(a>b) + 0.5 * (a==b)


def main():
    decision = read(DATA/"decision.json")
    groups = defaultdict(dict)
    for r in read(DATA/"manifest.json")["records"]:
        groups[r["host"]][r["variant"]] = dimensions(r)
    for r in decision["scalar_features"]:
        assert all(r[k]==v for k,v in groups[r["host"]][r["variant"]].items())
    results = {}
    for neg in ("clean","benign"):
        results[neg] = {}
        for key in ("characters","nodes","edges"):
            scores = {h:rank(v["trojan"][key],v[neg][key]) for h,v in groups.items()}
            assert scores == decision["controls"][neg][key]["by_host"]
            results[neg][key] = dict(mean=sum(scores.values())/len(scores),
                                      ci95=percentile_bootstrap(list(scores.values())),
                                      counts=dict(Counter(scores.values())))
    trust = defaultdict(lambda: defaultdict(list))
    for r in read(ROOT/"runs/typed_fusion_v1/manifest.json")["records"]:
        trust[r["side"]][r["benchmark"].split("-")[0]].append(r["cells"])
    origin = {}
    for side, families in trust.items():
        synthetic = [v[side]["nodes"] for v in groups.values()]
        # Within-label origin AUROC, equal weight per family on both sides.
        auc = sum(sum(rank(t,s) for t in vals for s in synthetic)/(len(vals)*len(synthetic))
                  for vals in families.values())/len(families)
        origin[side] = dict(synthetic_range=[min(synthetic),max(synthetic)],
                            trusthub_by_family={h:[min(v),max(v)] for h,v in families.items()},
                            equal_family_origin_auc=auc)
    result = dict(hosts=len(groups),bootstrap="Exact empirical host percentile, pointwise 95%",
                  size=results,counts=groups,trusthub_origin_by_cell_count=origin)
    path = DATA/"size_validation.json"
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="ascii",newline="\n")
    print(results,origin)


if __name__=="__main__":
    main()
