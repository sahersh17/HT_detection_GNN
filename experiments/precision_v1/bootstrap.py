"""Exact percentile bootstrap on the host-score lattice without enumerating n**n draws."""
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from math import gcd,lcm
import numpy as np


@lru_cache(maxsize=4096)
def interval(sorted_values):
    n=len(sorted_values)
    values=[Fraction(x).limit_denominator(100000) for x in sorted_values]
    if any(abs(float(v)-x)>1e-12 for v,x in zip(values,sorted_values)):
        raise ValueError("Score is not on the expected rational ranking lattice")
    denom=lcm(*(v.denominator for v in values))
    ticks=[int(v*denom) for v in values]
    low=min(ticks); spacing=gcd(*(v-low for v in ticks)) or 1
    weights=Counter((v-low)//spacing for v in ticks)
    counts=np.array([1],dtype=object)
    for _ in range(n):
        new=np.zeros(len(counts)+max(weights),dtype=object)
        for offset,w in weights.items():
            new[offset:offset+len(counts)]+=counts*w
        counts=new
    target=n**n
    cumulative=0; bounds=[]
    for i,w in enumerate(counts):
        cumulative+=w
        for q in (1,39)[len(bounds):]:
            if 40*cumulative>=q*target:bounds.append((low+i*spacing/n)/denom)
            else:break
        if len(bounds)==2:break
    return bounds


def summary(by_host):
    values=tuple(sorted(float(v) for v in by_host.values()))
    return dict(mean=float(np.mean(values)),ci95=interval(values),by_host=by_host)
