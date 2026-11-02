"""Prospectively choose unrelated host lineages from clean-only evidence."""
import hashlib
import re
from collections import Counter
from planning import RUN,DATA,PREV,read,report
from preflight import raw,folder,sha,gitsh,net

def fingerprints(r):
    parts=[]; shingles=set()
    for f in raw(r):
        text=re.sub(r"/\*.*?\*/|//[^\n]*","",f.read_text(errors="replace"),flags=re.S)
        for module in re.findall(r"\bmodule\b.*?\bendmodule\b",text,re.S):
            tokens=re.findall(r"[A-Za-z_$][\w$]*|\d+|[^\s]",module)
            if len(tokens)>=120:
                normalized=[("ID" if re.match(r"[a-zA-Z_$]",t) and t not in {"assign","always","begin","end","case","if","else","wire","reg"} else t) for t in tokens]
                shingles.update(hash(tuple(normalized[i:i+11])) for i in range(len(tokens)-10))
            if len(tokens)>=120:parts.append(hashlib.sha256(" ".join(tokens[2:]).encode()).hexdigest())
    return set(parts),shingles


def main():
    from bootstrap import summary
    baseline=read(PREV/"overlap.json")
    panel=baseline["reference_clean"]
    target=read(DATA/"planning.json")["estimated_additional"]
    valid=[r for r in read(RUN/"preflight.json") if "error" not in r]
    # Alternate source-length strata in fixed commit-hash order. Selection
    # uses no synthetic or benign variant and no class scores.
    chosen=[];seen=set();seen_modules=set(); seen_shapes=[]
    for r in valid:
        r["rank"]=sum(sum((r["tokens"]>t)+.5*(r["tokens"]==t) for t in vals)/len(vals) for vals in panel.values())/4
    pools=[sorted((r for r in valid if (r["rank"]>.5)==high),key=lambda r:r["commit"]) for high in (False,True)]
    while any(pools) and len(chosen)<target:
        for pool in pools:
            while pool and len(chosen)<target:
                r=pool.pop(0)
                title=re.sub(r"[^a-z0-9]","",str(r["title"]).lower())
                keys={r["repo"].lower(),r["repo"].split("/")[-2].lower(),str(r["author"]).strip().lower(),
                      title,r["host"].lower(),*r["sha256"].values()}
                modules,shape=fingerprints(r)
                if not shape or any(len(shape & prior)/min(len(shape),len(prior))>.80 for prior in seen_shapes):continue
                if keys&seen or modules&seen_modules or "resubmit" in title or "factorytest" in title:continue
                if sha(folder(r)/"oracle.json")!=r["oracle_sha256"]:continue
                seen_shapes.append(shape);seen.update(keys);seen_modules.update(modules);chosen.append(r)
                break
    by={r["host"]:r["rank"] for r in chosen}
    result=summary(by) if by else {}
    combined=summary(dict(baseline["origin_token_check"]["by_host"],**by)) if by else {}
    passed=bool(by and all(.30<=x<=.70 for v in (result,combined) for x in v["ci95"]))
    report(DATA/"intake.json",dict(estimated_additional=target,actual=len(chosen),passed=passed,
        candidates_with_independent_oracle=len(valid),range=baseline["reference_range"],new_origin=result,combined_origin=combined,
        families=chosen,parent_protocol_sha256=baseline["protocol_sha256"]))
    print(len(chosen),result.get("mean"),result.get("ci95"),combined.get("ci95"),passed)
    if not passed or len(chosen)<target:raise SystemExit("Original-only target not yet met")

if __name__=="__main__":main()
