"""Build original/benign/synthetic triplets and map each through the project flow."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT/"data/tier3_v1"
RUN = ROOT/"runs/tier3_admission_v1"
AES = ROOT/"trusthub/AES_unzipped/AES-T100/AES-T100/src/TjFree"
PIC = ROOT/"runs/expansion/PIC16F84-T100/clean"
FAMILIES = {"rv32_pipe":"rv32_pipe", "wishbone_xbar":"wishbone_xbar",
            "AES":"aes_128","PIC16F84":"pic_16f84_core"}
SIDES = ("clean","benign","trojan")
EDIT = {
    "rv32_pipe": ("6: take = left < right;", "6: take = right > left;",
                  "6: take = $signed(left) < $signed(right);"),
    "wishbone_xbar": ("? !previous :", "? (previous ^ 1'b1) :", "? previous :"),
    "PIC16F84": ("assign prog_adr_o   = pc_reg;",
                 "assign prog_adr_o   = (pc_reg == 13'd13) ? 13'd13 : pc_reg;",
                 "assign prog_adr_o   = (pc_reg == 13'd13) ? 13'd12 : pc_reg;"),
}
AES_SITE = "    final_round\n        rf (clk, s9, k9b, out);"
AES_ARM = """    wire [127:0] cipher;
    final_round
        rf (clk, s9, k9b, cipher);
    assign out = {cipher[127:8], (cipher[7:0] == 8'h32 ? 8'hVALUE : cipher[7:0])};"""
EDIT["AES"] = (AES_SITE,AES_ARM.replace("VALUE","32"),AES_ARM.replace("VALUE","33"))
YOSYS = ROOT/"trusthub/venv/Scripts/yowasp-yosys.exe"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def relative(p):
    return p.relative_to(ROOT).as_posix()


def save(p,s):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(s,encoding="utf-8",newline="\n")


def report(p,obj):
    save(p,json.dumps(obj,indent=2)+"\n")


def run(args):
    proc=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,errors="replace")
    if proc.returncode:
        raise RuntimeError(f"{args[0]}: {proc.stderr[-2000:]} {proc.stdout[-1000:]}")
    return proc.stdout


def sources(host,side):
    if host in ("AES","PIC16F84"):
        originals = ([AES/n for n in ("aes_128.v","round.v","table.v")] if host=="AES"
                     else [PIC/"risc16f84.v"])
        target = RUN/host/side/originals[0].name
        files = originals.copy()
        if side != "clean":
            files[0] = target
    else:
        originals = [DATA/"rtl"/host/"clean.v"]
        target = originals[0].with_name(side+".v")
        files = [target]
    if side!="clean":
        full=originals[0].read_text()
        before,after=EDIT[host][0],EDIT[host][SIDES.index(side)]
        if full.count(before)!=1:
            raise ValueError(f"Nonunique site in {host}")
        save(target,full.replace(before,after))
    return files


def main():
    commands=[]
    rows=[]
    for host,top in FAMILIES.items():
        for side in SIDES:
            files=sources(host,side)
            folder=RUN/host/side
            folder.mkdir(parents=True,exist_ok=True)
            commands += ["design -reset","read_verilog "+" ".join(map(relative,files)),
                         f"hierarchy -check -top {top}","proc; opt; flatten; opt; techmap; opt",
                         f"write_json {relative(folder/'yosys.json')}",f"write_verilog -noattr {relative(folder/'mapped.v')}"]
            rows.append(dict(host=host,top=top,variant=side,label=int(side=="trojan"),
                             cohort="shared" if host in ("AES","PIC16F84") else "tier3",
                             sources={relative(p):digest(p) for p in files}))
        if host not in ("AES","PIC16F84"):
            commands.append("design -reset")
            for side,mod in (("clean","gold"),("benign","gate")):
                commands += [f"read_verilog {relative(sources(host,side)[0])}","proc; memory_map; opt",f"rename {top} {mod}"]
            commands += ["equiv_make gold gate equiv","hierarchy -top equiv","opt_clean",
                         "equiv_simple","equiv_induct -seq 2","equiv_status -assert"]
        else:
            # Only the output expression changed. Prove that exact expression
            # for arbitrary upstream bits, independently of internal state.
            width,signal=(128,"cipher") if host=="AES" else (13,"pc_reg")
            rhs=EDIT[host][1].split("assign ")[-1].split("=",1)[1].strip().rstrip(";")
            proof=RUN/host/"proof.v"
            save(proof,f"module proof(input [{width-1}:0] {signal},output ok);\n"
                       f"wire [{width-1}:0] value = {rhs};\nassign ok = value == {signal};\nendmodule\n")
            commands += ["design -reset",f"read_verilog {relative(proof)}","prep -top proof",
                         "sat -verify -prove ok 1"]
    save(RUN/"build.ys","\n".join(commands)+"\n")
    run([str(YOSYS),"-q","-l",relative(RUN/"build.log"),"-s",relative(RUN/"build.ys")])
    for row in rows:
        folder=RUN/row["host"]/row["variant"]
        row["mapped_json_sha256"]=digest(folder/"yosys.json")
    report(RUN/"built.json",rows)


if __name__=="__main__":
    main()
