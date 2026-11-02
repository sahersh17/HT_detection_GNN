"""Publish a row-level interpretation of the original 29 gates after expansion."""
from planning import DATA,read

def main():
    d=read(DATA/"admission.json");p=read(DATA/"planning.json")
    old={(r["domain"],r["arm"],r["control"]):r for r in p["intervals"]}
    text=["# Reassessment of the 29 original intervals","",
          "Rows are matched to the six-family results before interpreting the expanded cohort. An interval wholly beyond the practical band is evidence of a substantial directional signature. A point estimate beyond the band with an overlapping interval is a candidate signature. An in-band estimate with an interval that crosses a margin is still precision-limited. Small directional effects can coexist with practical equivalence.","",
          "| Domain | Arm | Control | Six-family mean | Expanded mean | Expanded 95% interval | Interpretation | Excludes 0.5 |",
          "| --- | --- | --- | ---: | ---: | --- | --- | --- |"]
    for r in d["earlier_29"]:
        lo,hi=r["ci95"];m=r["mean"]
        if hi<.30 or lo>.70:reason="Substantial directional signature"
        elif r["point_outside"]:reason="Candidate signature; margin overlaps"
        elif r["still_fails"]:reason="Precision-limited"
        else:reason="Passes practical equivalence"
        prior=old[r["domain"],r["arm"],r["control"]]["mean"]
        text.append(f"| {r['domain']} | {r['arm']} | {r['control']} | {prior:.3f} | {m:.3f} | [{lo:.4f}, {hi:.4f}] | {reason} | {'Yes' if r['excludes_chance'] else 'No'} |")
    (DATA/"reassessment.md").write_text("\n".join(text)+"\n",encoding="utf-8",newline="\n")
if __name__=="__main__":main()
