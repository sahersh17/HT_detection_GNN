"""Verify synthesis-surviving benign edits and an existing independently authored Trust-Hub attack."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"experiments/transfer_v1"))
from build import BLOCKS,run,sha,rel
RUN=ROOT/"runs/augmentation_v2"
OUT=ROOT/"data/augmentation_v2"

def main():
    records=[]
    for project,(sub,names,expr,site,trigger,mask,zero,bench) in BLOCKS.items():
        src=ROOT/"runs/transfer_v1/upstream"/project/sub
        folder=RUN/project/"benign";folder.mkdir(parents=True,exist_ok=True)
        files=[src/n for n in names]
        text=files[0].read_text()
        width={"verilog-axis":4,"sha1":32,"uart16550":32,"core_usb_uart":16}[project]
        # Modular arithmetic is the identity for every value at the declared output width.
        replacement=f"((({expr}) + {width}'d1) - {width}'d1)"
        assert text.count(site)==1
        files[0]=folder/names[0]
        changed=text.replace(site,site.replace(expr,replacement))
        if project=="core_usb_uart":
            changed=text.replace("assign crc_out_o[","assign reference_crc[")
            changed=changed.replace("endmodule","wire [15:0] reference_crc; assign crc_out_o=(reference_crc+16'd1)-16'd1; endmodule")
        files[0].write_text(changed)
        tb=folder/"tb.v";tb.write_text("module tb; integer i;\n"+bench+"\nendmodule\n")
        top=Path(names[0]).stem
        proof=folder/"proof.v"
        proof.write_text(f"module proof(input [{width-1}:0] x, output ok);wire [{width-1}:0] y=(x+{width}'d1)-{width}'d1;assign ok=x==y;endmodule")
        script=folder/"build.ys"
        script.write_text(f"read_verilog -I{rel(src)} "+" ".join(map(rel,files))+f"\nhierarchy -check -top {top}\nproc; opt; flatten; opt; techmap; opt\nwrite_json {rel(folder/'yosys.json')}\nwrite_verilog -noattr {rel(folder/'mapped.v')}\ndesign -reset\nread_verilog {rel(proof)}\nprep -top proof\nsat -verify -prove ok 1\n")
        run([sys.executable,str(ROOT/"experiments/overlap_six_v1/yosys_runner.py"),"-q","-s",rel(script)])
        def observe(paths):
            run(["iverilog","-g2012","-I"+rel(src),"-s","tb","-o",rel(folder/"sim"),rel(tb),*map(rel,paths)])
            return [tuple(int(x,16) for x in s.split()[1:]) for s in run(["vvp",rel(folder/"sim")]).splitlines() if s.startswith("OBS ")]
        obs=observe(files)
        if len(obs)!=16 or any(a!=b for a,b in obs) or observe([folder/"mapped.v"])!=obs: raise ValueError("benign replay")
        doc=json.loads((folder/"yosys.json").read_text())
        orig=json.loads((ROOT/"runs/transfer_v1"/project/"clean/yosys.json").read_text())
        counts=[len(x["modules"][top]["cells"]) for x in (orig,doc)]
        if counts[1]<=counts[0]:raise ValueError((project,"edit did not survive",counts))
        deps=files+([src/"timescale.v",src/"uart_defines.v"] if project=="uart16550" else [])
        records.append(dict(host=project,variant="benign",top=top,sources={rel(p):sha(p) for p in deps},
             mapped=rel(folder/"yosys.json"),mapped_sha256=sha(folder/"yosys.json"),cells=counts,
             benign_expression_sat_proved=True,replay=obs))
    # The original attack disables reception following a false start pulse.
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location("pilot",ROOT/"experiments/trusthub_matched_v1/pilot.py");pilot=module_from_spec(spec);spec.loader.exec_module(pilot)
    tbtext=pilot.TB.replace("i<256","i<2").replace(' $finish;',""" rx=0; repeat(2) @(negedge clk);rx=1;repeat(32) @(negedge clk);
 send_bit(0);for(j=0;j<8;j=j+1)send_bit((8'hA5>>j)&1);send_bit(1);send_bit(1);
 $display("POST %02h %b",q,ready);$finish;""")
    observations={}
    for side,tag in (("clean","tjfree"),("trojan","tjin")):
        src=ROOT/f"trusthub/netlists/RS232/RS232-T2100/{tag}_patched_src"
        folder=RUN/"RS232"/side;folder.mkdir(parents=True,exist_ok=True)
        tb=folder/"tb.v";tb.write_text(tbtext)
        files=sorted(src.glob("*.v"))
        def observe(paths):
            run(["iverilog","-g2012","-I"+rel(src),"-s","tb","-o",rel(folder/"sim"),rel(tb),*map(rel,paths)])
            return [s.strip() for s in run(["vvp",rel(folder/"sim")]).splitlines() if s.startswith("POST ") or (len(s.split())==2 and len(s.split()[0])==2)]
        obs=observe(files)
        mapped=ROOT/"runs/provenance_v1/RS232-T2100"/side/"yosys.json"
        # Re-emit the existing verified implementation for the same trace.
        script=folder/"emit.ys";script.write_text(f"read_json {rel(mapped)}\nwrite_verilog -noattr {rel(folder/'mapped.v')}\n")
        run([sys.executable,str(ROOT/"experiments/overlap_six_v1/yosys_runner.py"),"-q","-s",rel(script)])
        if observe([folder/"mapped.v"])!=obs:raise ValueError(("external replay",side))
        observations[side]=obs
        records.append(dict(host="RS232",benchmark="RS232-T2100",variant=side,top="uart",sources={rel(p):sha(p) for p in files+[src/"inc.h"]},
             mapped=rel(mapped),mapped_sha256=sha(mapped),observations=obs,attack_authorship="original Trust-Hub source, unchanged"))
    if observations["clean"][:2]!=["00 1","01 1"] or observations["trojan"][:2]!=observations["clean"][:2] or observations["clean"][-1]!="POST a5 1" or observations["trojan"][-1]==observations["clean"][-1]:
        raise ValueError(observations)
    external=[]
    for side,tag in (("clean","tjfree"),("trojan","tjin")):
        src=ROOT/f"trusthub/netlists/RS232/RS232-T2200/{tag}_patched_src"
        folder=RUN/"RS232-T2200"/side;folder.mkdir(parents=True,exist_ok=True)
        tb=folder/"tb.v";tb.write_text(pilot.TB.replace("i<256","i<2"))
        files=sorted(src.glob("*.v"))
        def observe(paths):
            run(["iverilog","-g2012","-I"+rel(src),"-s","tb","-o",rel(folder/"sim"),rel(tb),*map(rel,paths)])
            return [s.strip() for s in run(["vvp",rel(folder/"sim")]).splitlines() if len(s.split())==2 and len(s.split()[0])==2]
        obs=observe(files)
        mapped=ROOT/"runs/provenance_v1/RS232-T2200"/side/"yosys.json"
        script=folder/"emit.ys";script.write_text(f"read_json {rel(mapped)}\nwrite_verilog -noattr {rel(folder/'mapped.v')}\n")
        run([sys.executable,str(ROOT/"experiments/overlap_six_v1/yosys_runner.py"),"-q","-s",rel(script)])
        if observe([folder/"mapped.v"])!=obs:raise ValueError(("external second replay",side))
        external.append(obs)
        records.append(dict(host="RS232",benchmark="RS232-T2200",variant=side,top="uart",sources={rel(p):sha(p) for p in files+[src/"inc.h"]},
            mapped=rel(mapped),mapped_sha256=sha(mapped),observations=obs,attack_authorship="original Trust-Hub source, unchanged"))
    if external[0]!=["00 1","01 1"] or external[1]==external[0]:raise ValueError(external)
    (OUT/"intake.json").write_text(json.dumps(dict(records=records),indent=2))
if __name__=="__main__":main()

