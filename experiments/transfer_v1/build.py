"""Build and replay the four development blocks at pinned revisions. Reserve metadata only."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUN = ROOT / "runs/transfer_v1"
OUT = ROOT / "data/transfer_v1"
PINS = {
    "verilog-axis": "48ff7a7e2ef782cf778d47910cf85835c64b1bce",
    "sha1": "50f82f4ca2f8194fd47d8360270ac7dd141d53d1",
    "uart16550": "2b0ad80d0968f201f95506854ad769c8a44abe2b",
    "core_usb_uart": "e35daa6874a0764abf2391b42cdba4a5803c5b6e",
    "serv": "f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8",
    "wb2axip": "2e8d3bc2d26ddc33d1881022a2a2b9d3f0c16b9b",
}
# Each contract emits the expected original word. Last two transactions activate the edit.
BLOCKS = {
 "verilog-axis": ("rtl", ["arbiter.v","priority_encoder.v"], "grant_reg", "assign grant = grant_reg;",
    "acknowledge == 4'hd", "4'h1", "4'h0",
    """reg clk=0,rst=1; reg [3:0] req=0,ack=0; wire [3:0] y; wire v; wire [1:0] e;
    arbiter dut(clk,rst,req,ack,y,v,e);
    initial begin #1; clk=1; #1; clk=0; rst=0;
    for(i=0;i<16;i=i+1) begin req=1<<(i%4); ack=i<14?0:13; #1;clk=1;#1;
    $display("OBS %h %h",y,req);clk=0;#1;end end"""),
 "sha1": ("src/rtl", ["sha1_w_mem.v"], "w_tmp", "assign w = w_tmp;",
    "block[7:0] == 8'had", "32'd1", "32'd0",
    """reg clk=0,rst=0,init=0; reg [511:0] b=0; wire [31:0] y;
    sha1_w_mem dut(clk,rst,b,init,1'b0,y);
    initial begin #1;clk=1;#1;clk=0;rst=1;init=1;
    for(i=0;i<16;i=i+1) begin b[511:480]=32'h100+i;b[7:0]=i<14?i:173;
    #1;clk=1;#1;$display("OBS %h %h",y,b[511:480]);clk=0;#1;end end"""),
 "uart16550": ("rtl/verilog", ["uart_debug_if.v"], "{msr,lcr,iir,ier,lsr}", "wb_dat32_o = {msr,lcr,iir,ier,lsr};",
    "msr == 8'had", "32'd1", "32'd0",
    """reg [7:0] msr=0;wire [31:0] y;
    uart_debug_if dut(y,5'd8,4'd0,4'd0,2'd0,5'd0,8'd0,msr,8'd1,5'd0,5'd0,3'd0,4'd0);
    initial for(i=0;i<16;i=i+1) begin msr=i<14?i+1:173;#1;
    $display("OBS %h %h",y,{msr,24'h1});end"""),
 "core_usb_uart": ("src_v", ["usbf_crc16.v"], "crc_in_i[12]", "assign crc_out_o[4] =     crc_in_i[12];",
    "din_i == 8'had", "1'b1", "1'b0",
    """reg [15:0] c=0;reg [7:0] d=0;wire [15:0] wordout;
    usbf_crc16 dut(c,d,wordout);
    initial for(i=0;i<16;i=i+1) begin c=i<14?i*1234:4096;d=i<14?i:173;#1;
    $display("OBS %h %h",wordout[4],c[12]);end"""),
}
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run(args):
    result=subprocess.run(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300)
    if result.returncode: raise RuntimeError((args,result.returncode,result.stdout[-3000:]))
    return result.stdout

def rel(p):
    return p.relative_to(ROOT).as_posix()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for project,pin in PINS.items():
        repo=RUN/"upstream"/project
        git=["git","-c","safe.directory="+repo.as_posix(),"-C",str(repo)]
        if run(git+["rev-parse","HEAD"]).strip()!=pin or run(git+["status","--porcelain","--untracked-files=no"]).strip():
            raise ValueError(project)
    for project,(sub,names,expr,site,trigger,mask,zero,bench) in BLOCKS.items():
        src=RUN/"upstream"/project/sub
        top=Path(names[0]).stem
        for side in ("clean","benign","toggle","suppress"):
            folder=RUN/project/side
            folder.mkdir(parents=True,exist_ok=True)
            files=[src/n for n in names]
            text=files[0].read_text()
            if text.count(site)!=1: raise ValueError(site)
            if side!="clean":
                active={"benign":f"({expr} ^ {zero})","toggle":f"({expr} ^ {mask})","suppress":zero}[side]
                files[0]=folder/names[0]
                files[0].write_text(text.replace(site,site.replace(expr,f"({trigger}) ? {active} : {expr}")))
            tb=folder/"tb.v"
            tb.write_text("module tb; integer i;\n"+bench+"\nendmodule\n")
            script=folder/"map.ys"
            script.write_text(f"read_verilog -I{rel(src)} "+" ".join(map(rel,files))+f"\nhierarchy -check -top {top}\nproc; opt; flatten; opt; techmap; opt\nwrite_json {rel(folder/'yosys.json')}\nwrite_verilog -noattr {rel(folder/'mapped.v')}\n")
            run([sys.executable,str(ROOT/"experiments/overlap_six_v1/yosys_runner.py"),"-q","-s",rel(script)])
            def observe(paths):
                run(["iverilog","-g2012","-I"+rel(src),"-s","tb","-o",rel(folder/"sim"),rel(tb),*map(rel,paths)])
                return [tuple(int(v,16) for v in line.split()[1:]) for line in run(["vvp",rel(folder/"sim")]).splitlines() if line.startswith("OBS ")]
            obs=observe(files)
            if len(obs)!=16 or obs!=observe([folder/"mapped.v"]): raise ValueError((project,side,"replay"))
            for i,(actual,reference) in enumerate(obs):
                expected=reference
                if i>=14 and side=="toggle": expected ^= 1
                if i>=14 and side=="suppress": expected=0
                if actual!=expected: raise ValueError((project,side,i,actual,expected))
            deps=files+([src/"timescale.v",src/"uart_defines.v"] if project=="uart16550" else [])
            rows.append(dict(host=project,variant=side,top=top,sources={rel(p):sha(p) for p in deps},
                mapped=rel(folder/"yosys.json"),mapped_sha256=sha(folder/"yosys.json"),
                bench_sha256=sha(tb),observed_and_reference=obs,trigger=trigger))
    (OUT/"intake.json").write_text(json.dumps(dict(pins=PINS,records=rows),indent=2))
if __name__=="__main__":
    main()


