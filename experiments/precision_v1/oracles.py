"""Retrieve independent taped-design references from the pinned shuttle tree, not from the triplet generator."""
import subprocess
import sys
from collections import defaultdict
from planning import ROOT,RUN,read,report

def git(folder,*args):
    return subprocess.check_output(["git","-c",f"safe.directory={folder.as_posix()}","-C",str(folder),*args])
if __name__=="__main__":
    groups=defaultdict(list)
    for r in read(RUN/"candidates.json"):
        if 1343<=r.get("tokens",0)<=20907:groups[r["path"].split("/")[2]].append(r["host"])
    for shuttle,hosts in groups.items():
        if sys.argv[1:] and shuttle not in sys.argv[1:]:continue
        directory=RUN/shuttle
        tree=git(directory,"rev-parse","HEAD").decode().strip()
        files=[f"projects/{h}/{h}.v" for h in hosts]+["verilog/rtl/fast/sky130_fd_sc_hd_fast.v"]
        available=set(git(directory,"ls-tree","-r","--name-only","HEAD").decode().splitlines())
        files=[f for f in files if f in available]
        git(directory,"sparse-checkout","add",*("/"+f for f in files))
        report(directory/"reference_pin.json",dict(commit=tree,files=files))
        print(shuttle,len(files),flush=True)

