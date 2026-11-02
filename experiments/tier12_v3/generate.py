"""Generate controlled mutations from Yosys's sampled native mutation database."""
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/"tier12_v1"))
import build
from hosts import HOSTS
from reference import reference, stimuli

ROOT = build.ROOT
OUT = ROOT/"data/tier12_v3"
RUN = ROOT/"runs/tier12_v3"
KINDS = ("addition", "replacement", "removal")
YOSYS = ROOT/"trusthub/venv/Scripts/yowasp-yosys.exe"


def yosys(stage, commands):
    script = RUN/f"{stage}.ys"
    build.save(script, "\n".join(commands)+"\n")
    build.run([str(YOSYS), "-Q", "-T", "-q", "-l", build.rel(RUN/f"{stage}.log"), "-s", build.rel(script)])


def operands(host):
    seed = int.from_bytes(hashlib.sha256(host.encode()).digest()[:4], "big")
    rng = random.Random(seed)
    return (rng.randrange(128, 256) | 1, rng.randrange(128, 256) | 1)


def prepare():
    commands = []
    for h in HOSTS:
        path = RUN/h.name
        path.mkdir(parents=True, exist_ok=True)
        a, b = operands(h.name)
        original = (build.OUT/"rtl"/h.name/"clean.v").read_text()
        guard = f"(* keep *) wire m = a==8'd{a} && b==8'd{b};"
        build.save(path/"input.v", original.replace("endmodule", guard+"\nendmodule"))
        commands.extend(["design -reset", f"read_verilog {build.rel(path/'input.v')}",
                         "hierarchy -top top", "proc; opt",
                         f"write_rtlil {build.rel(path/'base.il')}",
                         f"write_json {build.rel(path/'base.json')}"])
        for mode in ("cnot0","cnot1","const0","const1"):
            commands.append(f"mutate -list 0 -seed 739 -mode {mode} -o {build.rel(path/(mode+'.txt'))}")
    yosys("proposals",commands)


def sample(host):
    folder = RUN/host
    module = json.loads((folder/"base.json").read_text())["modules"]["top"]
    a, b = operands(host)
    pins = {bit:(value >> i) & 1 for port,value in (("a",a),("b",b))
            for i,bit in enumerate(module["ports"][port]["bits"])}
    candidates = {}
    guard_line = next(i for i,line in enumerate((folder/"input.v").read_text().splitlines(),1)
                      if "(* keep *)" in line)
    for mode in ("const0","const1","cnot0","cnot1"):
        for line in (folder/(mode+".txt")).read_text().splitlines():
            tokens = line.split()
            args = dict(zip(tokens[1::2],tokens[2::2]))
            cell = module["cells"][args["-cell"]]
            if f"input.v:{guard_line}." in cell["attributes"].get("src",""):
                continue
            port = args["-port"]
            bits = cell["connections"][port]
            bit = bits[int(args["-portbit"])]
            if cell["port_directions"][port] != "input" or bit not in pins:
                continue
            if mode.startswith("cnot"):
                ctrl = bits[int(args["-ctrlbit"])]
                if ctrl not in pins or ctrl == bit:
                    continue
                active = pins[ctrl] == int(mode[-1])
                family = "toggle"
            else:
                active = pins[bit] != int(mode[-1])
                family = "force"
            identity = (family,args["-cell"],port,args["-portbit"])
            candidates.setdefault(identity,{})[active] = line
    chosen = {}
    used_sites = set()
    for kind in KINDS:
        family = "force" if kind=="replacement" else "toggle"
        options = [(k,v) for k,v in candidates.items() if k[0]==family and len(v)==2]
        # Deterministic sampling independent of detector scores and v1/v2 sites.
        options.sort(key=lambda kv: hashlib.sha256(repr((739,host,kind,kv[0])).encode()).digest())
        if not options:
            raise ValueError(f"No {family} proposals on {host}")
        site, pair = next(((k,v) for k,v in options if k[1:] not in used_sites), options[0])
        used_sites.add(site[1:])
        inert, active = pair[False], pair[True]
        if kind=="removal":
            # The two active toggles cancel. The third is inert at the trigger.
            # Delete one operation in either edited arm of the same baseline.
            chosen[kind] = ([active,active,inert],[active,active],[active,inert])
        else:
            chosen[kind] = ([],[inert],[active])
    return chosen


def generate():
    commands = []
    plans = {}
    for host in HOSTS:
        h = host.name
        plans[h] = sample(h)
        for kind,arms in plans[h].items():
            for side,ops in zip(build.SIDES,arms):
                folder = RUN/kind/h/side
                folder.mkdir(parents=True,exist_ok=True)
                src = OUT/kind/"rtl"/h/f"{side}.v"
                src.parent.mkdir(parents=True,exist_ok=True)
                commands += ["design -reset", f"read_rtlil {build.rel(RUN/h/'base.il')}"]
                commands += [line.replace("mutate ", "mutate -ctrl m 1 1 ",1) for line in ops]
                commands += [f"write_verilog -noattr {build.rel(src)}", "design -reset",
                             f"read_verilog {build.rel(src)}","hierarchy -check -top top",build.FLOW,
                             "check -assert",f"write_json {build.rel(folder/'yosys.json')}",
                             f"write_verilog -noattr {build.rel(folder/'mapped.v')}"]
    build.report(OUT/"operator_plans.json",plans)
    yosys("apply",commands)


if __name__ == "__main__":
    prepare()
    generate()
