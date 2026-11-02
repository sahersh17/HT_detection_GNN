"""One disclosed synthetic triplet on an inspected RS232 host, with exhaustive byte replay."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/"trusthub/netlists/RS232/RS232-T2100/tjfree_patched_src"
RUN = ROOT/"runs/trusthub_matched_v1"
OUT = ROOT/"data/trusthub_matched_v1"
YOSYS = ROOT/"trusthub/venv/Scripts/yowasp-yosys.exe"
FILES = ("inc.h","u_rec.v","u_xmit.v","uart.v")
RHS = "rec_dataH_temp"
ARMS = {"original":RHS, "benign":"(rec_dataH_temp == 8'hA6) ? 8'hA6 : rec_dataH_temp",
        "synthetic":"(rec_dataH_temp == 8'hA6) ? 8'hA7 : rec_dataH_temp"}
TB = """module tb;
reg clk=0, rst=1, rx=1; wire tx, done, ready; wire [7:0] q;
uart dut(clk,rst,tx,1'b0,8'd0,done,rx,q,ready);
always #5 clk=~clk;
task send_bit(input bitval); begin rx=bitval; repeat(16) @(negedge clk); end endtask
integer i,j;
initial begin
 #1; rst=0; repeat(4) @(negedge clk); rst=1; repeat(30) @(negedge clk);
 for(i=0;i<256;i=i+1) begin
  send_bit(0);
  for(j=0;j<8;j=j+1) send_bit((i>>j)&1);
  send_bit(1); send_bit(1);
  $display("%02h %b",q,ready);
 end
 $finish;
end
endmodule
"""


def run(args):
    result=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-1500:]+result.stdout[-1000:])
    return result.stdout


def relative(p):
    return p.relative_to(ROOT).as_posix()


def main():
    RUN.mkdir(parents=True,exist_ok=True)
    tb=RUN/"tb.v"
    tb.write_text(TB)
    commands=[]
    for arm,expr in ARMS.items():
        folder=RUN/arm
        folder.mkdir(exist_ok=True)
        for name in FILES:
            content=(BASE/name).read_bytes()
            if name=="uart.v":
                token=b"rec_dataH=rec_dataH_temp;"
                assert content.count(token)==1
                content=content.replace(token,("rec_dataH="+expr+";").encode())
            (folder/name).write_bytes(content)
        paths=" ".join(relative(folder/f) for f in FILES if f.endswith(".v"))
        commands += ["design -reset",f"read_verilog -I{relative(folder)} {paths}",
                     "hierarchy -top uart","proc; opt; flatten; opt; techmap; opt",
                     f"write_json {relative(folder/'net.json')}",f"write_verilog -noattr {relative(folder/'mapped.v')}"]
    script=RUN/"synth.ys"
    script.write_text("\n".join(commands)+"\n")
    run([str(YOSYS),"-q","-l",relative(RUN/"synthesis.log"),"-s",relative(script)])
    results={}
    for arm in ARMS:
        folder=RUN/arm
        sources=[str(folder/f) for f in FILES if f.endswith(".v")]
        for view,files in (("source",sources),("mapped",[str(folder/"mapped.v")])):
            binary=folder/(view+".vvp")
            run(["iverilog","-g2012","-s","tb","-I",str(folder),"-o",str(binary),str(tb),*files])
            observed=[l.split() for l in run(["vvp","-n",str(binary)]).splitlines() if len(l.split())==2 and len(l.split()[0])==2]
            expected=[[f"{i+(arm=='synthetic' and i==166):02x}","1"] for i in range(256)]
            if observed!=expected:
                raise ValueError((arm,view,len(observed),[(i,x,y) for i,(x,y) in enumerate(zip(observed,expected)) if x!=y][:5]))
        cells=json.loads((folder/"net.json").read_text())["modules"]["uart"]["cells"]
        hist=Counter(c["type"] for c in cells.values() if c["type"] not in {"$scopeinfo","$print","$display"})
        results[arm]=dict(cells=sum(hist.values()),gate_histogram=dict(sorted(hist.items())),rx_bytes_checked_per_view=256,
                          source_sha256={f:hashlib.sha256((folder/f).read_bytes()).hexdigest() for f in FILES})
    OUT.mkdir(parents=True,exist_ok=True)
    report=dict(scope="one inspected RS232 development host, original plus two new synthetic edits",
                base=relative(BASE),edits=ARMS,results=results,trained=False)
    (OUT/"validation.json").write_text(json.dumps(report,indent=2)+"\n",encoding="ascii",newline="\n")
    print({k:v["cells"] for k,v in results.items()})


if __name__=="__main__":
    main()
