"""Construct native expression edits after intake, retain all failed trials, replay both views."""
import re,random,subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from planning import DATA,PREV,ROOT,RUN,read,report
from preflight import command,raw,folder,sha,simulate,net,cell_models
YRUN=ROOT/"experiments/overlap_six_v1/yosys_runner.py"
PY=ROOT/"trusthub/venv/Scripts/python.exe"
SIDES=("clean","benign","trojan")

def proposals(r):
    found=[]
    for file in raw(r):
        source=file.read_text(encoding="latin-1")
        # Preserve offsets while excluding comments, quoted strings and directives.
        bare=re.sub(r'/\*.*?\*/|//[^\n]*|"[^"\n]*"|`[^\n]*',lambda m:re.sub(r'[^\n]',' ',m[0]),source,flags=re.S)
        for m in re.finditer(r"(?<![\w$])(\d{1,2})'([bBdDhH])([0-9A-Fa-f_]+)\b(?![?])",bare):
            width=int(m[1]);base=m[2].lower()
            if not 1<=width<=32:continue
            line=bare[bare.rfind("\n",0,m.start())+1:bare.find("\n",m.end())]
            if re.search(r"\b(parameter|localparam|generate|genvar|for|wire|reg|input|output|function|initial)\b",line) and "assign" not in line:continue
            try:value=int(m[3].replace("_",""),{"b":2,"h":16,"d":10}[base])
            except ValueError:continue
            if value>=1<<width:continue
            fmt="x" if base!="h" else "d";radix="h" if fmt=="x" else "d"
            flip=1<<((m.start()+value)%width)
            benign=f"{width}'{radix}{value:{fmt}}"
            fault=f"{width}'{radix}{value^flip:{fmt}}"
            found.append((file,m.start(),m.end(),m[0],benign,fault,"literal",width))
        # Native input-pin selectors have known eight-bit port width.
        for m in re.finditer(r"\b(ui_in|uio_in)\s*\[([0-7])\]",bare):
            a,b=m.span(2);v=int(m[2])
            found.append((file,a,b,m[2],f"3'd{v}",f"3'd{(v+1)%8}","pin_select",3))
    rand=random.Random(r["commit"]);rand.shuffle(found)
    return found


def top_wrapper(r,side,trigger):
    files=raw(r);top=r["host"]
    src=next(p for p in files if re.search(r'\bmodule\s+'+re.escape(top)+r'\b',p.read_text(errors="replace")))
    text=src.read_text(encoding="latin-1")
    text,n=re.subn(r'(\bmodule\s+)'+re.escape(top)+r'\b',r'\g<1>original_implementation',text,count=1)
    if n!=1:raise ValueError("wrapper target")
    payload="8'h00" if side=="benign" else "8'h01"
    text+=f"""
module {top}(input [7:0] ui_in,uio_in, output [7:0] uo_out,uio_out,uio_oe, input ena,clk,rst_n);
wire [7:0] result;
original_implementation u(.ui_in(ui_in),.uio_in(uio_in),.uo_out(result),.uio_out(uio_out),
  .uio_oe(uio_oe),.ena(ena),.clk(clk),.rst_n(rst_n));
assign uo_out = (ui_in == 8'h{trigger:02x}) ? (result ^ {payload}) : result;
endmodule
"""
    return src,text


def trace_ok(obs,oracle):
    return len(obs)==320 and all(obs[i]==v for i,v in zip(oracle["indices"],oracle["values"]))


def construct(r):
    h=r["host"];d=folder(r); originals=raw(r)
    if {p.name:sha(p) for p in originals}!=r["sha256"] or sha(d/"oracle.json")!=r["oracle_sha256"]:
        raise ValueError("Original intake hashes changed")
    oracle=read(d/"oracle.json");attempts=[]
    # Repeat the independent reference check in isolation for each selected
    # top. Shuttle submissions can reuse a top-module name across revisions.
    supplied=simulate(r,[net(r),*cell_models(r)],"locked_reference",True)
    if not trace_ok(supplied,oracle) or not trace_ok(simulate(r,originals,"locked_clean"),oracle):
        raise ValueError("Pinned source/reference replay changed")
    def write(side,file,text):
        path=d/side/file.name;path.parent.mkdir(exist_ok=True)
        path.write_text(text,encoding="latin-1",newline="\n")
        return [path if p==file else p for p in originals]
    arms={"clean":originals}
    witness_trace=None
    for file,a,b,old,alias,fault,kind,width in proposals(r)[:28]:
        text=file.read_text(encoding="latin-1")
        bad=write("trojan",file,text[:a]+fault+text[b:])
        try: obs=simulate(r,bad,"mutant")
        except (ValueError,TimeoutError,subprocess.TimeoutExpired):attempts.append("elaboration_or_timeout");continue
        if len(obs)!=320:attempts.append("short_trace");continue
        ix=oracle["indices"]
        mismatch=[i for i,v in zip(ix,oracle["values"]) if obs[i]!=v]
        if not mismatch or mismatch[0]<16 or any(set(obs[i])-set("01") for i in ix):
            attempts.append("no_defined_dormant_witness");continue
        arms["benign"]=write("benign",file,text[:a]+alias+text[b:]);arms["trojan"]=bad
        recipe=dict(kind=kind,file=file.name,offset=a,before=old,benign=alias,trojan=fault)
        witness_trace=obs
        break
    if witness_trace is None:
        # Predeclared fallback, reported separately. This does not replace or
        # discard a difficult host. Its transaction-level oracle is explicit.
        active_inputs={(i-16)&255 for i in oracle["indices"] if i>=16}
        trigger=167 if 167 in active_inputs else min(active_inputs-{0})
        recipe=dict(kind="guarded_output_fallback",trigger=trigger)
        for side in SIDES[1:]:
            file,text=top_wrapper(r,side,trigger);arms[side]=write(side,file,text)
        witness_trace=simulate(r,arms["trojan"],"mutant")
        for i,v in zip(oracle["indices"],oracle["values"]):
            expected=int(v,2)^((1<<16) if i>=16 and ((i-16)&255)==trigger else 0)
            if int(witness_trace[i],2)!=expected:raise ValueError("fallback payload mismatch")
    report(d/"edit.json",dict(recipe=recipe,rejected_trials=attempts))
    cmds=[]
    for s,files in arms.items():
        drv=d/s;drv.mkdir(exist_ok=True)
        cmds+=["design -reset","read_verilog "+" ".join(p.relative_to(ROOT).as_posix() for p in files),
               f"hierarchy -check -top {h}","proc; opt; flatten; opt; techmap; opt",
               "write_json "+(drv/"yosys.json").relative_to(ROOT).as_posix(),
               "write_verilog -noattr "+(drv/"mapped.v").relative_to(ROOT).as_posix()]
    if recipe["kind"]=="guarded_output_fallback":
        equation="(x ^ 8'h00)==x";ports="input [7:0] x"
    else:
        equation=f"({old} == {alias})";ports="input dummy"
    (d/"proof.v").write_text(f"module proof({ports},output ok);assign ok={equation};endmodule\n")
    cmds+=["design -reset","read_verilog "+(d/"proof.v").relative_to(ROOT).as_posix(),"prep -top proof","sat -verify -prove ok 1"]
    script=d/"build.ys";script.write_text("\n".join(cmds)+"\n")
    command([str(PY),str(YRUN),"-q","-l",str((d/"build.log").relative_to(ROOT).as_posix()),"-s",script.relative_to(ROOT).as_posix()],timeout=180)
    rows=[];ix=oracle["indices"]
    for s,files in arms.items():
        src=simulate(r,files,"src_"+s);mapped=simulate(r,[d/s/"mapped.v"],"net_"+s)
        known=[int(src[i],2) for i in ix]
        if len(src)!=320 or len(mapped)!=320 or any(src[i]!=mapped[i] for i in ix):
            raise ValueError(f"{s} mapped replay disagreement")
        diff=[(i,int(v,2),actual) for i,v,actual in zip(ix,oracle["values"],known) if int(v,2)!=actual]
        if (s=="trojan")!=bool(diff) or (diff and diff[0][0]<16):raise ValueError(f"{s} independent oracle disagreement: {diff[:2]}")
        rows.append(dict(host=h,top=h,variant=s,label=int(s=="trojan"),group=h,sources={p.relative_to(ROOT).as_posix():sha(p) for p in files},
               mapped_json_sha256=sha(d/s/"yosys.json"),mapped_agrees=True,benign_expression_proved=s=="benign",
               oracle_sha256=r["oracle_sha256"],observations=len(ix),witness=diff[0] if diff else None,edit_kind=recipe["kind"]))
    return rows


def work(r):
    d=folder(r)
    try:
        result=construct(r);report(d/"verified.json",result); print(r["host"],result[-1]["edit_kind"],"PASS",flush=True)
        report(d/"last_status.json",dict(passed=True))
    except Exception as e:
        report(d/"last_status.json",dict(passed=False))
        report(d/"failure.json",dict(error=str(e)[:2000])); print(r["host"],"FAILED",str(e)[:120],flush=True)

def main():
    intake=read(DATA/"intake.json")
    if not intake["passed"] or intake["actual"]!=intake["estimated_additional"]:raise ValueError("Missing passing prospectively selected panel")
    import sys
    chosen=intake["families"]
    if "--supplement" in sys.argv:
        reserve=read(DATA/"reserve_intake.json")
        if not reserve["passed"]:raise ValueError("Supplementary original overlap gate failed")
        chosen=reserve["families"]
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(work,chosen))
    assemble()

def assemble():
    intake=read(DATA/"intake.json")
    extended=read(DATA/"reserve_intake.json") if (DATA/"reserve_intake.json").exists() else {"families":[]}
    rows=[];failures={}
    for r in intake["families"]+extended["families"]:
        d=folder(r)
        passed=read(d/"last_status.json")["passed"] if (d/"last_status.json").exists() else (d/"verified.json").exists()
        if passed:rows.extend(read(d/"verified.json"))
        else:failures[r["host"]]=read(d/"failure.json") if (d/"failure.json").exists() else {"error":"No verification result"}
    report(DATA/"manifest.json",dict(screen_sha256=sha(DATA/"intake.json"),
           reserve_screen_sha256=sha(DATA/"reserve_intake.json") if extended["families"] else None,
           records=rows,failures=failures))

if __name__=="__main__":main()
