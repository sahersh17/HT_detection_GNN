"""Generate, synthesize, prove benign equivalence, and replay independent traces."""
import hashlib
import json
import re
import shutil
import subprocess
import random
from pathlib import Path

from hosts import HOSTS
from reference import reference, stimuli

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/tier12_v1"
RUN = ROOT / "runs/tier12_v1"
SIDES = ("clean", "benign", "trojan")
FLOW = "proc; opt; flatten; opt; techmap; opt"


def rel(path):
    return path.relative_to(ROOT).as_posix()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="ascii", newline="\n")


def report(path, value):
    save(path, json.dumps(value, indent=2)+"\n")


def normalized(host, edit):
    text = f"""module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
{host.declarations}
always @(posedge clk) begin
  if (rst) begin
    {host.reset}
  end else begin
    {host.body.replace('EDIT', edit)}
  end
end
assign y={host.output};
endmodule
"""
    # Declarations are fixed across siblings. Preserve literals and interface.
    names = re.findall(r"\b[A-Za-z_]\w*\b", host.declarations)
    table = {n:f"v{i}" for i,n in enumerate(dict.fromkeys(n for n in names if n not in {"integer","reg"}))}
    return re.sub(r"\b[A-Za-z_]\w*\b", lambda m:table.get(m[0],m[0]),text)


def emit_tb(folder, trace):
    vectors = folder / "stimuli.hex"
    save(vectors, "".join(f"{rst<<18 | op<<16 | a<<8 | b:05x}\n" for rst,op,a,b in trace))
    save(folder / "tb.v", f"""module tb;
reg clk,rst; reg [1:0] op; reg [7:0] a,b; wire [31:0] y;
reg [18:0] vectors [0:{len(trace)-1}]; integer i;
top u(clk,rst,op,a,b,y);
initial begin
  clk=0;
  $readmemh("{rel(vectors)}",vectors);
  for (i=0; i<{len(trace)}; i=i+1) begin
    {{rst,op,a,b}}=vectors[i]; #2; clk=1; #2; $display("%h",y); clk=0; #2;
  end
end
endmodule
""")


def run(args):
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(f"{args} exited {result.returncode}: {result.stdout[-2000:]} {result.stderr[-2000:]}")
    return result.stdout


def simulate(source, folder):
    image=folder/"sim.vvp"
    run(["iverilog","-g2012","-s","tb","-o",str(image),str(folder/"tb.v"),str(source)])
    return [int(line,16) for line in run(["vvp","-n",str(image)]).splitlines() if re.fullmatch("[0-9a-fA-FxXzZ]{8}",line.strip())]


def main():
    yosys=shutil.which("yosys") or str(ROOT/"trusthub/venv/Scripts/yowasp-yosys.exe")
    script=[]
    for host in HOSTS:
        for side,edit in zip(SIDES,host.edits):
            src=OUT/"rtl"/host.name/f"{side}.v"
            folder=RUN/host.name/side
            folder.mkdir(parents=True,exist_ok=True)
            save(src,normalized(host,edit))
            script.extend(["design -reset",f"read_verilog {rel(src)}","hierarchy -check -top top",FLOW,
                           "check -assert",f"write_json {rel(folder/'yosys.json')}",
                           f"write_verilog -noattr {rel(folder/'mapped.v')}"])
        # Elaboration in separate scopes, matching state names across designs.
        script += ["design -reset"]
        for side,mod in (("clean","gold"),("benign","gate")):
            src=OUT/"rtl"/host.name/f"{side}.v"
            script += [f"read_verilog {rel(src)}","proc; opt",f"rename top {mod}"]
        script += ["equiv_make gold gate equiv","hierarchy -top equiv","opt_clean",
                   "equiv_simple","equiv_induct -seq 2","equiv_status -assert"]
    save(RUN/"build.ys","\n".join(script)+"\n")
    run([yosys,"-Q","-T","-q","-l",rel(RUN/"yosys.log"),"-s",rel(RUN/"build.ys")])
    records=[]
    for host in HOSTS:
        normal,witness=stimuli(host)
        # Additional full-byte workload. Activation is permitted and measured here.
        rng = random.Random(5191 + sum(map(ord,host.name)))
        stress = [(1,0,0,0)] + [(0,rng.randrange(4),rng.randrange(256),rng.randrange(256))
                                  for _ in range(1536)]
        trace=normal+witness+stress
        oracle=reference(host.name,trace)
        folder=RUN/host.name
        emit_tb(folder,trace)
        for side in SIDES:
            src=OUT/"rtl"/host.name/f"{side}.v"
            net=folder/side/"mapped.v"
            rtl=simulate(src,folder)
            mapped=simulate(net,folder)
            if len(rtl)!=len(trace) or mapped!=rtl:
                raise ValueError(f"{host.name}/{side}: mapped replay or cycle count failed")
            differences=[i for i,(x,y) in enumerate(zip(rtl,oracle)) if x!=y]
            stress_start=len(normal)+len(witness)
            diff=[i for i in differences if i<stress_start]
            if side!="trojan" and differences:
                raise ValueError(f"{host.name}/{side}: mismatch with independent oracle")
            if (side=="trojan")!=bool(diff) or any(i<len(normal) for i in diff):
                raise ValueError(f"{host.name}/{side}: unexpected divergence at {diff[:5]}")
            row=dict(host=host.name,tier=host.tier,variant=side,label=int(side=="trojan"),
                     group=host.name,source=rel(src),sha256=digest(src),normal_cycles=len(normal),
                     witness_cycles=len(witness),decoy_equivalence_proved=side=="benign",
                     rtl_mapped_replay_equal=True,stress_cycles=len(stress),
                     stress_different_output_cycles=sum(i>=stress_start for i in differences),
                     mapped_json_sha256=digest(folder/side/"yosys.json"))
            if diff:
                i=diff[0]
                row.update(effect=host.effect,first_witness_cycle=i-len(normal),expected=oracle[i],observed=rtl[i])
            records.append(row)
        report(OUT/"witnesses"/f"{host.name}.json",dict(description=host.description,columns=["reset","op","a","b"],
               vectors=witness,expected_clean=oracle[len(normal):stress_start]))
    report(OUT/"manifest.json",dict(generator="tier12_rtl_v1",scope="inspected development",records=records))
    print(f"{len(records)} verified records across {len(HOSTS)} hosts")


if __name__=="__main__":
    main()
