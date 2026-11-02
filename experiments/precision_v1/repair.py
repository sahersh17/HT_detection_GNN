"""Repeat an attempt only for a technical failure or an ineligible wildcard token."""
import argparse
from pathlib import Path
from planning import DATA,RUN,read,report
import preflight
from triplets import work

def main():
    panel=read(DATA/"intake.json")["families"]
    log=[]
    for r in panel:
        home=preflight.folder(r)
        if not (home/"edit.json").exists():continue
        recipe=read(home/"edit.json")["recipe"]
        failure=read(home/"failure.json")["error"] if (home/"failure.json").exists() else ""
        if (home/"last_status.json").exists() and read(home/"last_status.json")["passed"]:continue
        wildcard=False
        if recipe["kind"]=="literal":
            text=(RUN/"originals"/r["commit"]/recipe["file"]).read_text(encoding="latin-1")
            wildcard=text[recipe["offset"]+len(recipe["before"]):].startswith("?")
        if wildcard or ("timed out" in failure and not (home/"retry.json").exists()):
            reason="Incomplete wildcard literal excluded" if wildcard else "One 150-second replay timeout allowance"
            report(home/"retry.json",dict(prior_failure=failure,reason=reason))
            orig=preflight.command
            def command(args,timeout=40):
                return orig(args,timeout=150 if args[0]=="vvp" else timeout)
            preflight.command=command
            try:work(r)
            finally:preflight.command=orig
            log.append(dict(host=r["host"],reason=reason,result=read(home/"last_status.json")))
    print(log)
if __name__=="__main__":main()
