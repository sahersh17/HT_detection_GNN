"""Generate only from the original sources that passed the pinned preflight."""
import json
from intake import DATA, HERE, HOSTS, PARENT, ROOT, RUN, SIDES, digest, raw_paths, relative, report, save
from build_cohort import run

# Unique source site; equivalent expression; synthetic expression.
TARGETS={
    "divider":("end else if (b_e == 1024) begin\n          z[63] <= a_s ^ b_s;",
               "a_s ^ b_s","b_s ^ a_s","a_s | b_s","input a_s,b_s",""),
    "logic_scope":("br_holdoff <= i_bus_data[(HOLDOFFBITS-1):0];",
                   "i_bus_data[(HOLDOFFBITS-1):0]","(i_bus_data & {HOLDOFFBITS{1'b1}})",
                   "(i_bus_data & ({HOLDOFFBITS{1'b1}} >> 1))","input [31:0] i_bus_data","19:0"),
    "sha2":("localparam SHA224_H0_0 = 32'hc1059ed8;",
            "32'hc1059ed8","32'hc105_9ed8","32'hc1059ed9","input dummy","31:0"),
    "i2c_controller":("prescale_next[15:8] = s_axil_wdata[15:8];",
                      "s_axil_wdata[15:8]","s_axil_wdata[8 +: 8]","s_axil_wdata[7:0]",
                      "input [31:0] s_axil_wdata","7:0"),
    "jpeg_huffman":("y_dc_value_r = 8'h0b;","8'h0b","8'd11","8'h0a","input dummy","7:0"),
    "picorv32":("alu_out = reg_op1 ^ reg_op2;","reg_op1 ^ reg_op2","reg_op2 ^ reg_op1",
                "reg_op1 | reg_op2","input [31:0] reg_op1,reg_op2","31:0"),
}


def main():
    screen=json.loads((DATA/"overlap.json").read_text())
    if not screen["passed"] or screen["protocol_sha256"]!=digest(PARENT):
        raise ValueError("Original-only overlap gate missing or failed")
    cmds=[]
    rows=[]
    for host,(top,_,_,_) in HOSTS.items():
        originals=raw_paths(host)
        if {relative(p):digest(p) for p in originals}!=screen["original_families"][host]["sources"]:
            raise ValueError(f"Unscreened input: {host}")
        site,old,benign,fault,ports,width=TARGETS[host]
        original=originals[0].read_text()
        if original.count(site)!=1 or site.count(old)!=1: raise ValueError((host,site))
        for side,expr in zip(SIDES,(old,benign,fault)):
            folder=RUN/host/side
            folder.mkdir(parents=True,exist_ok=True)
            files=originals.copy()
            if side!="clean":
                files[0]=folder/files[0].name
                save(files[0],original.replace(site,site.replace(old,expr)))
            cmds+=["design -reset","read_verilog "+" ".join(map(relative,files)),f"hierarchy -check -top {top}",
                   "proc; opt; flatten; opt; techmap; opt",f"write_json {relative(folder/'yosys.json')}",
                   f"write_verilog -noattr {relative(folder/'mapped.v')}"]
            rows.append(dict(host=host,variant=side,label=int(side=="trojan"),top=top,group=host,
                             sources={relative(p):digest(p) for p in files}))
        proof=RUN/host/"proof.v"
        size=f"[{width}]" if width else ""
        save(proof,f"module proof({ports},output ok); localparam HOLDOFFBITS=20; wire {size} a={old}, b={benign}; assign ok=(a==b); endmodule\n")
        cmds+=["design -reset",f"read_verilog {relative(proof)}","prep -top proof","sat -verify -prove ok 1"]
    save(RUN/"build.ys","\n".join(cmds)+"\n")
    run([str(ROOT/"trusthub/venv/Scripts/python.exe"),str(HERE/"yosys_runner.py"),"-q","-l",relative(RUN/"build.log"),"-s",relative(RUN/"build.ys")])
    for row in rows:
        row["mapped_json_sha256"]=digest(RUN/row["host"]/row["variant"]/"yosys.json")
    report(RUN/"built.json",rows)


if __name__=="__main__":
    main()
