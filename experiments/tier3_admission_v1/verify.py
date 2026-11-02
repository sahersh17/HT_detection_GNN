"""Transaction-level oracles and reset-to-output witnesses for the four families."""
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby
import json

from build_cohort import AES, DATA, FAMILIES, HERE, ROOT, RUN, SIDES, digest, relative, report, run, save

# (instruction, rd/rs1, rs1/rs2, immediate). PC-relative offsets are byte offsets.
PROGRAM = [
    ("addi",1,0,2), ("addi",2,0,5), ("bltu",1,2,8), ("addi",3,0,99),
    ("add",3,1,2), ("sw",3,0,0), ("lw",4,0,0), ("bne",3,4,8),
    ("addi",5,0,-1), ("bltu",5,1,8), ("addi",6,0,11), ("jal",7,0,8),
    ("addi",6,0,55), ("addi",8,0,68), ("jalr",9,8,0), ("addi",6,0,77),
    ("addi",6,0,88), ("addi",10,0,3), ("addi",10,10,-1), ("bne",10,0,-4),
    ("xor",11,3,4), ("jal",0,0,0)
]


def encode(ins):
    op,x,y,z=ins
    if op in ("addi","lw","jalr"):
        return ((z&4095)<<20)|(y<<15)|((2 if op=="lw" else 0)<<12)|(x<<7)|{"addi":0x13,"lw":3,"jalr":0x67}[op]
    if op in ("add","xor"):
        return z<<20|y<<15|(4 if op=="xor" else 0)<<12|x<<7|0x33
    if op=="sw":
        return ((z>>5)&127)<<25|x<<20|y<<15|2<<12|(z&31)<<7|0x23
    if op=="jal":
        return ((z>>20)&1)<<31|((z>>1)&1023)<<21|((z>>11)&1)<<20|((z>>12)&255)<<12|x<<7|0x6f
    return ((z>>12)&1)<<31|((z>>5)&63)<<25|y<<20|x<<15|(6 if op=="bltu" else 1)<<12|((z>>1)&15)<<8|((z>>11)&1)<<7|0x63


def cpu(tb, bad):
    program="\n".join(f"rom[{i}]=32'h{encode(v):08x};" for i,v in enumerate(PROGRAM))
    save(tb,"""module tb;
reg clk=0,rst=1; always #5 clk=~clk;
reg [31:0] rom[0:31]; reg [31:0] mem=0;
wire [31:0] fetch,addr,wd,pc,val; wire wr,valid; wire [4:0] rd;
rv32_pipe dut(clk,rst,rom[fetch[6:2]],mem,fetch,addr,wd,wr,valid,pc,val,rd);
always @(posedge clk) if(wr) mem<=wd;
always @(posedge clk) if(valid) begin
 $display("R %d %d %h %b %h %h",pc,rd,(rd!=0)?val:32'd0,wr,wr?addr:32'd0,wr?wd:32'd0);
end
initial begin
"""+program+"""
repeat(3) @(negedge clk);rst=0; repeat(82) @(negedge clk);$finish;end
endmodule
""")
    def check(output):
        regs=[0]*32
        pc=mem=0
        log=[]
        for line in output.splitlines():
            if not line.startswith("R "): continue
            _,p,d,v,w,a,b=line.split()
            got=(int(p),int(d),int(v,16),int(w),int(a,16),int(b,16))
            op,x,y,z=PROGRAM[pc//4]
            nxt=pc+4
            rd,val,wr,addr,wd=0,0,0,0,0
            if op=="addi": rd,val=x,(regs[y]+z)&0xffffffff
            elif op=="add": rd,val=x,(regs[y]+regs[z])&0xffffffff
            elif op=="xor": rd,val=x,regs[y]^regs[z]
            elif op=="lw": rd,val=x,mem
            elif op=="sw": wr,addr,wd=1,regs[y]+z,regs[x]; mem=wd
            elif op=="jal": rd,val=x,pc+4; nxt=pc+z
            elif op=="jalr": rd,val=x,pc+4; nxt=(regs[y]+z)&~1
            elif op=="bne" and regs[x]!=regs[y]: nxt=pc+z
            elif op=="bltu":
                bias=0x80000000 if bad else 0
                if (regs[x]^bias)<(regs[y]^bias): nxt=pc+z
            expected=(pc,rd,val if rd else 0,wr,addr,wd)
            if got!=expected: raise ValueError((line,expected))
            if rd: regs[rd]=val
            pc=nxt
            log.append(got)
        if log.count((84,0,0,0,0,0))<2: raise ValueError("Missing terminal loop")
        return log
    return check


def bus(tb,bad):
    # Stimulus remains stable during waits. With both requests held, each
    # acknowledged transfer can be followed by a new transfer from that master.
    vectors=[(1,0,0),(0,1,0),(0,1,0),(0,1,1),(0,0,0),
             (0,2,0),(0,2,1),(0,2,2),(0,0,0)] + [(0,3,a) for a in (0,0,3,3,0,3)*4]
    vectors += [(0,0,0),(1,0,0),(0,2,0),(0,2,2)]
    lines=[]
    gold=[]
    busy=False
    owner=0
    last=1
    for i,(rst,req,acks) in enumerate(vectors):
        # Sample before the rising edge, after an initial reset edge.
        lines.append(f"rst={rst}; req={req}; sa={acks}; #2; show; #2; clk=1; #2; clk=0;")
        active=bool(not rst and busy and req&(1<<owner))
        bank=owner  # distinct slave addresses on the two master ports
        ack=bool(active and acks&(1<<bank))
        gold.append((1<<bank if active else 0,1<<bank if active else 0,1<<owner if ack else 0,
                     owner,0x8004 if owner else 4,3 if owner else 15,34 if owner else 17,
                     51 if active and owner==0 else 0,68 if active and owner==1 else 0))
        if rst: busy,owner,last=False,0,1
        elif not busy and req:
            owner=(last if bad else 1-last) if req==3 else int(req==2)
            busy=True
        elif busy and (ack or not(req&(1<<owner))): busy,last=False,owner
    save(tb,"""module tb;
reg clk=0,rst=1; reg [1:0] req=0,sa=0;
wire [1:0] cy,st,ack;wire we;wire [15:0] ad;wire [3:0] sel;wire [31:0] dat,r0,r1;
wishbone_xbar dut(clk,rst,req,req,2'b10,16'h0004,16'h8004,4'hf,4'h3,32'd17,32'd34,sa,32'd51,32'd68,cy,st,ack,we,ad,sel,dat,r0,r1);
task show; $display("R %h %h %h %h %h %h %h %h %h",cy,st,ack,we,ad,sel,dat,r0,r1); endtask
initial begin #2;clk=1;#2;clk=0;
"""+ "\n".join(lines)+"\n$finish;end endmodule")
    def check(out):
        seen=[tuple(int(v,16) for v in l.split()[1:]) for l in out.splitlines() if l.startswith("R ")]
        if seen!=gold: raise ValueError(("Bus trace mismatch",seen[:5],gold[:5]))
        return seen
    return check


def pic(tb,bad):
    inputs=("ram_dat_i eep_dat_i porta_i portb_i existeeprom_i rd_eep_ack_i wr_eep_ack_i "
            "int0_i int4_i int5_i int6_i int7_i t0cki_i wdt_ena_i wdt_clk_i").split()
    pins=", ".join(f".{n}(0)" for n in inputs)
    save(tb,"module tb;reg clk=0,rst=1;wire [12:0] pc;always #5 clk=~clk;\n"
         f"pic_16f84_core dut(.clk_i(clk),.pon_rst_n_i(rst),.mclr_n_i(rst),.prog_dat_i(14'd0),.prog_adr_o(pc),{pins});\n"
         'initial begin #1;rst=0;repeat(64) @(negedge clk);rst=1; repeat(160) begin @(negedge clk);$display("R %h",pc);end $finish;end endmodule')
    def check(out):
        seq=[int(l[2:],16) for l in out.splitlines() if l.startswith("R ")]
        distinct=[k for k,_ in groupby(seq)]
        want=[n for n in range(32) if not (bad and n==13)]
        if distinct[:len(want)]!=want: raise ValueError(("PIC fetch progression",distinct))
        return seq
    return check


def aes(tb,bad):
    text=(AES/"test_aes_128.v").read_text()
    if bad: text=text.replace("196a0b32","196a0b33")
    save(tb,text)
    def check(out):
        if "Good." not in out or "\nE" in out: raise ValueError(out)
        return [("3925841d02dc09fbdc118597196a0b33" if bad else "3925841d02dc09fbdc118597196a0b32"),
                "69c4e0d86a7b0430d8cdb78070b4c55a","66e94bd4ef8a2c3b884cfa59ca342b2e",
                "0545aad56da2a97c3663d1432a3d1c84","58e2fccefa7e3061367f1d57a4e7455a"]
    return check


def replay(row):
    host,side=row["host"],row["variant"]
    folder=RUN/host/side
    tb=folder/"bench.v"
    check={"rv32_pipe":cpu,"wishbone_xbar":bus,"AES":aes,"PIC16F84":pic}[host](tb,side=="trojan")
    traces=[]
    source_files=list(row["sources"])
    if host=="PIC16F84":
        text=(ROOT/source_files[0]).read_text()
        for name in ("temp","dtemp"):
            old=f"wire {name};"
            assert text.count(old)==1
            text=text.replace(old,f"reg {name};")
        patched=folder/"icarus_compat.v"
        save(patched,text)
        source_files=[str(patched)]
    for files in (source_files,[str(folder/"mapped.v")]):
        image=folder/"sim.vvp"
        top="test_aes_128" if host=="AES" else "tb"
        run(["iverilog","-g2012","-s",top,"-o",str(image),str(tb),*files])
        output=run(["vvp","-n",str(image)])
        if host=="PIC16F84" and traces:
            observations=[s[2:] for s in output.splitlines() if s.startswith("R ")]
            unknown=sum("x" in s.lower() or "z" in s.lower() for s in observations)
            if len(observations)==160 and unknown:
                return traces[0],f"Unknown program address in {unknown}/160 mapped reset-trace samples"
        traces.append(check(output))
    if traces[0]!=traces[1]: raise ValueError((host,side,"mapped trace differs"))
    print(host,side,len(traces[0]),flush=True)
    return traces[0],None


def main():
    rows=json.loads((RUN/"built.json").read_text())
    with ThreadPoolExecutor(max_workers=2) as pool:
        traces=dict(zip(((r["host"],r["variant"]) for r in rows),pool.map(replay,rows)))
    for row in rows:
        host,side=row["host"],row["variant"]
        trace,failure=traces[host,side]
        original=traces[host,"clean"][0]
        if side!="trojan" and trace!=original: raise ValueError("Benign mismatch")
        differences=[i for i,(x,y) in enumerate(zip(original,trace)) if x!=y]
        row.update(checked_outputs=len(trace),source_and_mapped_match=failure is None,group=host,
                   verification_failure=failure)
        if side=="trojan":
            i=differences[0]
            if not any(x==y for x,y in zip(original,trace)): raise ValueError("Missing normal observation")
            row["witness"]=dict(observation=i,expected=original[i],observed=trace[i],
                                view="source_only" if failure else "source_and_mapped")
        if side=="benign":
            row["equivalence_proof"]="output expression SAT with unchanged upstream" if host in ("AES","PIC16F84") else "whole-module Yosys equivalence"
        row["bench_sha256"]=digest(RUN/host/side/"bench.v")
    report(DATA/"manifest.json",dict(generator="tier3_admission_v1",protocol_sha256=digest(HERE/"protocol.json"),records=rows))


if __name__=="__main__":
    main()
