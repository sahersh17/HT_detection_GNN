"""Prove both negative arms against the original and replay all arms from reset."""
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby
import json
import random
from generate import HOSTS, KINDS, OUT, ROOT, RUN, build, operands, reference, stimuli, yosys


def prove():
    commands = []
    for host in HOSTS:
        for kind in KINDS:
            for side in ("clean","benign"):
                commands.append("design -reset")
                for path,name in ((build.OUT/"rtl"/host.name/"clean.v","gold"),
                                  (OUT/kind/"rtl"/host.name/f"{side}.v","gate")):
                    commands += [f"read_verilog {build.rel(path)}", "proc; opt",
                                 "rename -hide w:_*", f"rename top {name}"]
                commands += ["equiv_make gold gate equiv","hierarchy -top equiv","opt_clean",
                             "equiv_simple","equiv_induct -seq 2","equiv_status -assert"]
    yosys("equivalence",commands)


def directed(host):
    a,b = operands(host)
    # Exercise all opcodes under the same rare operand pair. Clock any serial
    # transfer to completion, sweep PWM phase, drain queues and read all addresses.
    result = [(1,0,0,0)]
    for op in (1,2,0,3):
        result += [(0,op,a,b)]*260
        result += [(0,2,i,11) for i in range(4) for _ in range(2)]
    return result


def verify_host(host):
    h = host.name
    normal,_ = stimuli(host)
    witness = directed(h)
    rng = random.Random(5191+sum(map(ord,h)))
    stress = [(1,0,0,0)]+[(0,rng.randrange(4),rng.randrange(256),rng.randrange(256)) for _ in range(1536)]
    trace = normal+witness+stress
    oracle = reference(h,trace)
    records = []
    for kind in KINDS:
        folder = RUN/kind/h
        build.emit_tb(folder,trace)
        for side in build.SIDES:
            src = OUT/kind/"rtl"/h/f"{side}.v"
            raw = build.simulate(src,folder)
            mapped = build.simulate(folder/side/"mapped.v",folder)
            if len(raw)!=len(oracle) or raw!=mapped:
                raise ValueError(f"Mapped replay mismatch {kind}/{h}/{side}")
            mismatch = [i for i,(x,y) in enumerate(zip(raw,oracle)) if x!=y]
            on = [i-len(normal) for i in mismatch if len(normal)<=i<len(normal)+len(witness)]
            if (side=="trojan")!=bool(on) or (side!="trojan" and mismatch) or any(i<len(normal) for i in mismatch):
                raise ValueError(f"Invalid behavior {kind}/{h}/{side}: {mismatch[:5]}")
            row = dict(host=h, group=h, edit_kind=kind, variant=side,label=int(side=="trojan"),
                       source=build.rel(src),sha256=build.digest(src),
                       mapped_json_sha256=build.digest(folder/side/"yosys.json"),
                       normal_cycles=len(normal),directed_cycles=len(witness),stress_cycles=len(stress),
                       stress_different_cycles=sum(i>=len(normal)+len(witness) for i in mismatch),
                       rtl_mapped_equal=True,equivalent_to_v1=side!="trojan")
            if on:
                i=on[0]
                row.update(first_witness_cycle=i,expected=oracle[len(normal)+i],observed=raw[len(normal)+i])
            records.append(row)
        print(f"{h} {kind} replayed",flush=True)
    return records


def main():
    prove()
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = [r for group in pool.map(verify_host,HOSTS) for r in group]
    for kind in KINDS:
        build.report(OUT/kind/"manifest.json",dict(generator="yosys_mutate_739_"+kind,
                     scope="inspected development; emitted cell-level Verilog",records=[r for r in rows if r["edit_kind"]==kind]))
    record_evidence()


def record_evidence():
    rows = [r for kind in KINDS for r in json.loads((OUT/kind/"manifest.json").read_text())["records"]]
    proofs = (RUN/"equivalence.log").read_text().count("Equivalence successfully proven!")
    if len(rows) != 81 or proofs != 54:
        raise ValueError("Incomplete verification artifacts")
    for row in rows:
        mapped = RUN/row["edit_kind"]/row["host"]/row["variant"]/"yosys.json"
        if build.digest(ROOT/row["source"]) != row["sha256"] or build.digest(mapped) != row["mapped_json_sha256"]:
            raise ValueError(f"Hash mismatch: {row['source']}")
    histories = {}
    for host in HOSTS:
        h = host.name
        vectors = directed(h)
        oracle = reference(h,vectors)
        for row in (r for r in rows if r["host"]==h and r["label"]):
            if oracle[row["first_witness_cycle"]] != row["expected"] or row["observed"]==row["expected"]:
                raise ValueError(f"Invalid witness: {h}")
        histories[h] = dict(original_clean_sha256=build.digest(build.OUT/"rtl"/h/"clean.v"),
            operands=operands(h), directed_run_lengths=[
                [sum(1 for _ in group),*v] for v,group in groupby(vectors)],
            proposal_list_sha256={m:build.digest(RUN/h/(m+".txt")) for m in ("cnot0","cnot1","const0","const1")})
    wasm = ROOT/"trusthub/venv/Lib/site-packages/yowasp_yosys/yosys.wasm"
    build.report(OUT/"verification.json",dict(proofs_against_original=proofs,rows=len(rows),
        witness_count=sum(r["label"] for r in rows),operator_plans_sha256=build.digest(OUT/"operator_plans.json"),
        simulator_cycles=sum(r["normal_cycles"]+r["directed_cycles"]+r["stress_cycles"] for r in rows),
        yosys_wasm_sha256=build.digest(wasm),directed_columns=["repeat","reset","op","a","b"],hosts=histories))


if __name__ == "__main__":
    main()
