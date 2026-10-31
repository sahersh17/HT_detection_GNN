"""Compare models from their prediction JSONs. Usage: python report.py rtl=a.json gnn=b.json fusion=c.json"""
import json
import sys
from pathlib import Path
from metrics import summarize_predictions, summarize


def load(path):
    return {(r["fold"], r["benchmark"], r["true_label"]): r for r in json.loads(Path(path).read_text())}


def main(args):
    models = dict(a.split("=", 1) for a in args)
    preds = {k: load(v) for k, v in models.items()}
    keys = set.intersection(*[set(p) for p in preds.values()])
    assert all(set(p) == keys for p in preds.values()), "models were evaluated on different samples"
    keys = sorted(keys)
    print(f"{'model':<14}{'acc':>7}{'bal':>7}{'prec':>7}{'rec':>7}{'F1':>7}{'FP':>5}{'FN':>5}{'AUROC':>8}")
    for name, p in preds.items():
        s = summarize_predictions([p[k] for k in keys])["pooled"]
        au = "n/a" if s["auroc"] is None else f"{s['auroc']:.3f}"
        print(f"{name:<14}{s['accuracy']:7.3f}{s['balanced_accuracy']:7.3f}{s['precision']:7.3f}"
              f"{s['recall']:7.3f}{s['macro_f1']:7.3f}{s['fp']:5d}{s['fn']:5d}{au:>8}")
    names = list(preds)
    y = [k[2] for k in keys]
    if len(names) >= 2:
        a, b = names[0], names[1]
        for label, fn in (("OR", max), ("AND", min)):
            p = [fn(preds[a][k]["predicted_label"], preds[b][k]["predicted_label"]) for k in keys]
            s = summarize(y, p)
            print(f"{label}({a},{b}){'':<4}{s['accuracy']:7.3f}{s['balanced_accuracy']:7.3f}"
                  f"{s['precision']:7.3f}{s['recall']:7.3f}{s['macro_f1']:7.3f}{s['fp']:5d}{s['fn']:5d}")
        missed_a = {k[1] for k in keys if k[2] == 1 and preds[a][k]["predicted_label"] == 0}
        caught_b = {k[1] for k in keys if k[2] == 1 and preds[b][k]["predicted_label"] == 1}
        print(f"\nTrojans missed by {a} but caught by {b}: {sorted(missed_a & caught_b)}")
    print("\nPer fold:")
    for name, p in preds.items():
        for fold, s in summarize_predictions([p[k] for k in keys]).items():
            if fold != "pooled":
                print(f"  {name:<10}{fold}: n={s['n']} acc={s['accuracy']:.3f} recall={s['recall']:.3f} FP={s['fp']} FN={s['fn']}")


if __name__ == "__main__":
    main(sys.argv[1:])
