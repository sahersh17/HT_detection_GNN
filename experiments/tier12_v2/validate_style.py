"""Separate source-style and motif-coverage diagnostics on inspected data."""
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"pipeline/provenance"),str(ROOT/"pipeline")]
from build import source_files
from validate_size import DATA, read, rank

spec=importlib.util.spec_from_file_location("motifs",ROOT/"experiments/matched_insertion_v3/controls.py")
motifs=importlib.util.module_from_spec(spec)
spec.loader.exec_module(motifs)
motifs.OUT=ROOT/"runs/tier12_v2"


def style(paths):
    text="\n".join(p.read_text(errors="replace") for p in paths)
    bare=re.sub(r"/\*.*?\*/|//[^\n]*","",text,flags=re.S)
    words=re.findall(r"[A-Za-z_][A-Za-z_0-9]*",bare)
    return {"neutral_name_fraction":sum(bool(re.fullmatch(r"v\d+",w)) for w in words)/max(1,len(words)),
            "comment_fraction":1-len(bare)/len(text)}


def main():
    gen=defaultdict(dict)
    coverage=defaultdict(int)
    for r in read(DATA/"manifest.json")["records"]:
        gen[r["variant"]][r["host"]]=style([ROOT/r["source"]])
        for probe in (motifs.output_cone_equivalence,motifs.output_xor_motifs):
            coverage[probe.__name__]+=int(probe(dict(r,top="top")).sum()>0)
    reference=defaultdict(lambda:defaultdict(list))
    for r in read(ROOT/"runs/typed_fusion_v1/manifest.json")["records"]:
        files,_=source_files(r["benchmark"],r["side"])
        reference[r["side"]][r["benchmark"].split("-")[0]].append(style(files))
    report={"v2_nonzero_motif_vectors_out_of_27":dict(coverage),"v2_style_class":{},"origin_generated_higher":{}}
    for key in ("neutral_name_fraction","comment_fraction"):
        report["v2_style_class"][key]={s:sum(rank(v[key],gen[s][h][key]) for h,v in gen["trojan"].items())/9
                                       for s in ("clean","benign")}
        report["origin_generated_higher"][key]={}
        for s,families in reference.items():
            scores=[sum(rank(g[key],t[key]) for g in gen[s].values() for t in members)/(9*len(members))
                    for members in families.values()]
            report["origin_generated_higher"][key][s]=sum(scores)/len(scores)
    (DATA/"style_and_cone_validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(report)


if __name__=="__main__":
    main()
