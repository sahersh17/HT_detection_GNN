"""Pre-edit independent trace and clean-source selection."""
from functools import lru_cache
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import math
import random
import re
import subprocess
import sys
from pathlib import Path
from planning import DATA,PREV,ROOT,RUN,read,report

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def raw(r):return [RUN/"originals"/r["commit"]/n for n in r["files"]]
def folder(r):return RUN/"hosts"/r["host"]
def gitsh(r):return ROOT/Path(r["path"]).parents[2]
def net(r):return (ROOT/r["path"]).with_name(r["host"]+".v")
@lru_cache(maxsize=1024)
def expanded(path):
    # Inline includes in place to preserve conditional UDP vs blackbox branches.
    source=path.read_text(errors="replace")
    return re.sub(r'^\s*`include\s+"([^"]+)".*$',lambda m:expanded((path.parent/m[1]).resolve()),source,flags=re.M)

def cell_models(r):
    text=net(r).read_text(errors="replace")
    names=sorted(set(re.findall(r"\bsky130_fd_sc_hd__(\w+_\d+)\s+",text)))
    seen=set(); parts=[]
    def emit(path):
        if path not in seen:
            seen.add(path)
            parts.append(expanded(path))
    for n in names:
        base=n.rsplit("_",1)[0];d=RUN/"pdkhd/cells"/base
        emit(d/f"sky130_fd_sc_hd__{base}.functional.pp.v")
        wrapper=(d/f"sky130_fd_sc_hd__{n}.v").read_text()
        parts.append(re.sub(r'^\s*`include.*$',"",wrapper,flags=re.M))
    # The shuttle's ef decap has supply pins only and no digital function.
    for name,ports in re.findall(r"(sky130_ef_sc_hd__decap_\d+)\s+\S+\s*\(([^;]+)\);",text):
        if set(re.findall(r"\.(\w+)\(",ports))!={"VNB","VPB","VGND","VPWR"}:
            raise ValueError("Unexpected physical-only cell interface")
        if name not in seen:
            seen.add(name);parts.append(f"module {name}(input VNB,VPB,VGND,VPWR);endmodule")
    lib=folder(r)/"reference_cells.v"
    folder(r).mkdir(parents=True,exist_ok=True)
    lib.write_text("\n".join(parts),encoding="utf-8")
    return [lib]
def command(args,timeout=40):
    p=subprocess.run(args,cwd=ROOT,text=True,errors="replace",capture_output=True,timeout=timeout)
    if p.returncode:raise ValueError((p.stderr or p.stdout)[-1200:])
    return p.stdout

def harness(r,physical):
    # Fixed original-only stimuli. First 16 non-reset cycles are the normal window.
    rng=random.Random(739)
    lines=[]
    for i in range(324):
        a,b=(0,0) if i<20 else ((i-20)&255,rng.randrange(256))
        lines.append(f"a=8'd{a};b=8'd{b};rst={int(i>=4)};#3;clk=1;#3;"+('$display("OBS %b",{y,e,(q&e)});' if i>=4 else '')+"clk=0;#4;")
    power=""
    if physical:
        header=net(r).read_text(errors="replace").split(");",1)[0]
        for name,value in (("VPWR",1),("VGND",0),("VDD",1),("VSS",0)):
            if re.search(r"\b"+name+r"\b",header):power+=f".{name}({'vdd' if value else 'gnd'}),"
    return ("module tb;supply1 vdd;supply0 gnd;reg clk=0,rst;reg [7:0] a,b;wire [7:0] y,q,e;"+
       r["host"]+" dut("+power+".clk(clk),.rst_n(rst),.ena(1'b1),.ui_in(a),.uio_in(b),.uo_out(y),.uio_out(q),.uio_oe(e));initial begin\n"+
       "\n".join(lines)+"\n$finish;end endmodule\n")

def simulate(r,files,key,physical=False):
    d=folder(r);d.mkdir(exist_ok=True,parents=True)
    tb=d/("reference_tb.v" if physical else "tb.v")
    text=harness(r,physical)
    if not tb.exists() or tb.read_text()!=text:tb.write_text(text,encoding="ascii")
    image=d/(key+".vvp")
    command(["iverilog","-g2012","-grelative-include","-DSYNTHESIS",*(["-DFUNCTIONAL","-DUSE_POWER_PINS"] if physical else []),"-s","tb","-o",str(image),str(tb),*[str(f) for f in files]])
    output=command(["vvp","-n",str(image)])
    return [s[4:] for s in output.splitlines() if s.startswith("OBS ")]

def validate(r):
    try:
        if any(sha(p)!=r["sha256"][p.name] for p in raw(r)):raise ValueError("original hash changed")
        gold=simulate(r,[net(r),*cell_models(r)],"reference",True)
        orig=simulate(r,raw(r),"original")
        if len(gold)!=320 or len(orig)!=320:raise ValueError("unusable trace length")
        good=[i for i,v in enumerate(gold) if set(v)<=set("01")]
        if len(good)<288 or good[:16]!=list(range(16)) or len({gold[i] for i in good})<2:
            raise ValueError("insufficient defined, changing reference output")
        if any(orig[i]!=gold[i] for i in good):raise ValueError("published netlist/RTL mismatch")
        report(folder(r)/"oracle.json",dict(indices=good,values=[gold[i] for i in good]))
        return dict(**r,oracle_sha256=sha(folder(r)/"oracle.json"),netlist_sha256=sha(net(r)),pdk_revision="ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1",shuttle_commit=read(gitsh(r)/"reference_pin.json")["commit"])
    except Exception as e:return dict(**r,error=str(e)[:400])

def main():
    candidates=[r for r in read(RUN/"candidates.json") if 1343<=r.get("tokens",0)<=20907]
    prior=[]
    if sys.argv[1:]:
        prior=[r for r in read(RUN/"preflight.json") if r["path"].split("/")[2] not in sys.argv[1:]]
        candidates=[r for r in candidates if r["path"].split("/")[2] in sys.argv[1:]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(validate,candidates))
    report(RUN/"preflight.json",prior+results)
    print("upstream gate oracle passed",sum("error" not in r for r in results),"of",len(results),flush=True)

if __name__=="__main__":main()
