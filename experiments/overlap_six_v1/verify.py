"""Independently expected normal and triggering transactions, replayed on both views."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

from intake import DATA, HOSTS, PARENT, ROOT, RUN, SIDES, digest, relative, report, save
from build_cohort import run


def bench(declarations, body):
    return ("module tb; reg clk=0; always #5 clk=~clk;\n"+declarations+
            "\ninitial begin #200000; $fatal(1,\"timeout\");end\ninitial begin\n"+
            body+"\n$finish;end endmodule\n")


def divider():
    decl="""reg [63:0] a,b; reg va=0,vb=0,rst=1;
wire aa,ab,vz;wire [63:0] z;
double_divider dut(a,b,va,vb,1'b1,clk,rst,z,vz,aa,ab);
task divide(input [63:0] x,input [63:0] y);
begin
 @(negedge clk);a=x;b=y;va=1;while(!aa) @(negedge clk);
 @(negedge clk);va=0;vb=1;while(!ab) @(negedge clk);
 @(negedge clk);vb=0;while(!vz) @(negedge clk);
 $display("OBS %016h",z);
end endtask"""
    return bench(decl,"""repeat(4) @(negedge clk);rst=0;
divide(64'h4018000000000000,64'h4008000000000000);
divide(64'hbff0000000000000,64'hfff0000000000000);"""),[0x4000000000000000,0],1


def sha2():
    decl="""reg rst=0,init=0,mode=1;
reg [511:0] block;
wire ready,valid; wire [255:0] digest;
sha256_core dut(clk,rst,init,1'b0,mode,block,ready,digest,valid);
task hashblock(input m);
begin
 @(negedge clk);mode=m;init=1;@(negedge clk);init=0;
 repeat(72) @(negedge clk);if (!valid || !ready) $fatal(1,"hash completion");
 if (m) $display("OBS %064h",digest); else $display("OBS %056h",digest[255:32]);
end endtask"""
    block=(b"abc"+b"\x80"+bytes(52)+(24).to_bytes(8,"big")).hex()
    return bench(decl,f"block=512'h{block}; repeat(4) @(negedge clk);rst=1;hashblock(1);hashblock(0);"),[
        int(hashlib.sha256(b"abc").hexdigest(),16),int(hashlib.sha224(b"abc").hexdigest(),16)],1


def logic_scope():
    decl="""reg cyc=0,stb=0,we=0; reg [31:0] wd=0; wire [31:0] rd; wire ack;
wbscope dut(.i_data_clk(clk),.i_ce(1'b0),.i_trigger(1'b0),.i_data(32'd0),
 .i_wb_clk(clk),.i_wb_cyc(cyc),.i_wb_stb(stb),.i_wb_we(we),.i_wb_addr(1'b0),
 .i_wb_data(wd),.i_wb_sel(4'hf),.o_wb_ack(ack),.o_wb_data(rd));
task write_read(input [19:0] value);
begin
 @(negedge clk);cyc=1;stb=1;we=1;wd=value;
 @(negedge clk);stb=0;repeat(4) @(negedge clk);cyc=0;we=0;
 repeat(4) @(negedge clk);cyc=1;stb=1;@(negedge clk);stb=0;
 while(!ack) @(negedge clk);$display("OBS %05h",rd[19:0]);cyc=0;
end endtask"""
    return bench(decl,"repeat(8) @(negedge clk);write_read(20'h01234);write_read(20'h81234);"),[0x1234,0x81234],1


def i2c_controller():
    decl="""reg rst=1,wr=0,ar=0; reg [31:0] wd=0; wire [31:0] rd;wire bv,rv;wire [1:0] br,rr;
i2c_master_axil dut(.clk(clk),.rst(rst),.s_axil_awaddr(4'hc),.s_axil_awprot(3'd0),.s_axil_awvalid(wr),
.s_axil_wdata(wd),.s_axil_wstrb(4'h3),.s_axil_wvalid(wr),.s_axil_bready(1'b1),.s_axil_bvalid(bv),
.s_axil_bresp(br),.s_axil_araddr(4'hc),.s_axil_arprot(3'd0),.s_axil_arvalid(ar),.s_axil_rready(1'b1),
.s_axil_rvalid(rv),.s_axil_rresp(rr),.s_axil_rdata(rd),.i2c_scl_i(1'b1),.i2c_sda_i(1'b1));
task write_read(input [15:0] value);
begin
 @(negedge clk);wd=value;wr=1;@(negedge clk);while(!bv) @(negedge clk);
 if(br!==0) $fatal;wr=0;@(negedge clk);ar=1;@(negedge clk);while(!rv) @(negedge clk);
 if(rr!==0) $fatal;$display("OBS %08h",rd);ar=0;
end endtask"""
    return bench(decl,"repeat(4) @(negedge clk);rst=0;write_read(16'h4545);write_read(16'h8145);"),[0x4545,0x8145],1


def jpeg_huffman():
    decl="""reg rst=1,req=0;reg [15:0] prefix;wire valid;wire [4:0] width;wire [7:0] symbol;
jpeg_dht dut(.clk_i(clk),.rst_i(rst),.cfg_valid_i(1'b0),.cfg_data_i(8'd0),.cfg_last_i(1'b0),
.lookup_req_i(req),.lookup_table_i(2'd0),.lookup_input_i(prefix),.lookup_valid_o(valid),
.lookup_width_o(width),.lookup_value_o(symbol));
task lookup(input [15:0] code); begin
 @(negedge clk);req=1;prefix=code;@(negedge clk);if(!valid) $fatal;
 $display("OBS %04h",{3'd0,width,symbol});req=0;
end endtask"""
    codes=["00","010","011","100","101","110","1110","11110","111110","1111110","11111110","111111110"]
    calls="".join(f"lookup(16'h{int(code.ljust(16,'0'),2):04x});" for code in codes)
    return bench(decl,"repeat(4) @(negedge clk);rst=0;"+calls),[(len(code)<<8)|i for i,code in enumerate(codes)],11


def picorv32():
    # Two XORs, each followed by an observable word store; independently
    # specified results for disjoint and overlapping operand bits.
    program=[0x00500093,0x00200113,0x0020c1b3,0x10302023,0x00300113,0x0020c1b3,0x10302223,0x0000006f]
    decl="""reg rst=0;wire trap,valid;wire [31:0] addr,wd;wire [3:0] strobe;
reg [31:0] rom[0:7];wire [31:0] rd=addr<32 ? rom[addr[4:2]] : 0;
picorv32 dut(.clk(clk),.resetn(rst),.trap(trap),.mem_valid(valid),.mem_ready(1'b1),
.mem_addr(addr),.mem_wdata(wd),.mem_wstrb(strobe),.mem_rdata(rd),.irq(32'd0),.pcpi_wr(1'b0),
.pcpi_rd(32'd0),.pcpi_wait(1'b0),.pcpi_ready(1'b0));
always @(posedge clk) if(rst && valid && |strobe) begin
 if(strobe!==4'hf) $fatal; $display("OBS %016h",{addr,wd});end"""
    init="".join(f"rom[{i}]=32'h{ins:08x};" for i,ins in enumerate(program))
    return bench(decl,init+"repeat(5) @(negedge clk);rst=1;repeat(180) @(negedge clk);if(trap!==0) $fatal;"),[
        (256<<32)|7,(260<<32)|6],1


TESTS={fn.__name__:fn for fn in (divider,sha2,logic_scope,i2c_controller,jpeg_huffman,picorv32)}


def replay(row):
    h,s=row["host"],row["variant"]
    folder=RUN/h/s
    body,expected,trigger=TESTS[h]()
    tb=folder/"tb.v"
    save(tb,body)
    traces=[]
    for files in (list(row["sources"]),[str(folder/"mapped.v")]):
        image=folder/"sim.vvp"
        run(["iverilog","-g2012","-DSYNTHESIS","-s","tb","-o",str(image),str(tb),*files])
        lines=run(["vvp","-n",str(image)]).splitlines()
        traces.append([int(line.split()[1],16) for line in lines if line.startswith("OBS ")])
    obs=traces[0]
    if traces[1]!=obs or len(obs)!=len(expected):
        raise ValueError((h,s,"source/mapped replay",traces))
    mismatches=[i for i,(x,y) in enumerate(zip(obs,expected)) if x!=y]
    if mismatches!=([trigger] if s=="trojan" else []):
        raise ValueError((h,s,mismatches,expected,obs))
    row.update(oracle=[hex(x) for x in expected],observed=[hex(x) for x in obs],mapped_agrees=True,
               bench_sha256=digest(tb),trigger_observation=trigger,benign_expression_proved=s=="benign")
    print(h,s,"verified",flush=True)
    return row


def main():
    rows=json.loads((RUN/"built.json").read_text())
    if (RUN/"build.log").read_text().count("SAT proof finished - no model found: SUCCESS!")!=6:
        raise ValueError("Six benign proofs required")
    with ThreadPoolExecutor(max_workers=3) as pool:
        records=list(pool.map(replay,rows))
    report(DATA/"manifest.json",dict(scope="length-screened development cohort",protocol_sha256=digest(PARENT),
           screen_sha256=digest(DATA/"overlap.json"),records=records))


if __name__=="__main__":
    main()
