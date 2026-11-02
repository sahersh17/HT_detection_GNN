"""Original-only source screen. No variant source or outcome is read at this stage."""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data/overlap_six_v1"
RUN = ROOT / "runs/overlap_v1"
UP = RUN / "upstream"
sys.path.insert(0, str(HERE.parent / "tier3_admission_v1"))
from build_cohort import digest, relative, report, save

# Top, repository, pinned commit, ordered original compilation files (edit target first).
HOSTS = {
    "divider": ("double_divider", "dawsonjon/fpu", "c45d5e0a9f1b7e945e2be6770dbc1203825a05c4",
                ["double_divider/double_divider.v"]),
    "logic_scope": ("wbscope", "ZipCPU/wbscope", "999f35f445817f69be3cd826cc66287f4cc760f7",
                    ["rtl/wbscope.v"]),
    "sha2": ("sha256_core", "secworks/sha256", "837c5cc396f001d18f2c765721c585716eb439ae",
             ["src/rtl/sha256_core.v","src/rtl/sha256_k_constants.v","src/rtl/sha256_w_mem.v"]),
    "i2c_controller": ("i2c_master_axil","alexforencich/verilog-i2c","a65be4045e898a52e791c6ee71f8f79a7cd2e129",
                       ["rtl/i2c_master_axil.v","rtl/i2c_master.v","rtl/axis_fifo.v"]),
    "jpeg_huffman": ("jpeg_dht","ultraembedded/core_jpeg","bb03cce45d0b7459d395486e9e1db3de1b416bd2",
                     ["src_v/jpeg_dht_std_y_dc.v","src_v/jpeg_dht.v","src_v/jpeg_dht_std_y_ac.v",
                      "src_v/jpeg_dht_std_cx_ac.v","src_v/jpeg_dht_std_cx_dc.v"]),
    "picorv32": ("picorv32","YosysHQ/picorv32","ef203c2b0a3fb793280f5114941416c425c5b461",["picorv32.v"]),
}
SIDES=("clean","benign","trojan")
PARENT=HERE.parent/"tier3_admission_v1/protocol.json"


def raw_paths(host):
    _,repo,_,files=HOSTS[host]
    return [UP/repo.split("/")[1]/f for f in files]


def get_sources(fetch):
    for host,(_,repo,revision,_) in HOSTS.items():
        path=UP/repo.split("/")[1]
        if fetch and not path.exists():
            subprocess.run(["git","init",str(path)],check=True)
            subprocess.run(["git","-C",str(path),"fetch","--depth","1",f"https://github.com/{repo}.git",revision],check=True)
            subprocess.run(["git","-C",str(path),"-c","core.autocrlf=false","checkout","--detach","FETCH_HEAD"],check=True)
        for f in raw_paths(host):
            data=subprocess.check_output(["git","-c",f"safe.directory={path.as_posix()}","-C",str(path),
                                          "show",revision+":"+f.relative_to(path).as_posix()])
            if data!=f.read_bytes(): raise ValueError(f"Original differs from pinned Git blob: {f}")


def main(fetch=False):
    from admission import lexical, provenance, read, summary, rank
    get_sources(fetch)
    panel={}
    for row in read(ROOT/"runs/typed_fusion_v1/manifest.json")["records"]:
        if row["side"]=="clean":
            files,_=provenance.source_files(row["benchmark"],"clean")
            panel.setdefault(row["benchmark"].split("-")[0],[]).append(lexical(tuple(files))["normalized_tokens"])
    lo=min(map(min,panel.values())); hi=max(map(max,panel.values()))
    records={}
    all_hashes=set()
    for h,(top,repo,rev,_) in HOSTS.items():
        files=raw_paths(h)
        hashes={relative(p):digest(p) for p in files}
        if all_hashes.intersection(hashes.values()): raise ValueError("Cross-family source duplicate")
        all_hashes.update(hashes.values())
        n=lexical(tuple(files))["normalized_tokens"]
        scores=[sum(rank(n,t) for t in counts)/len(counts) for counts in panel.values()]
        records[h]=dict(top=top,upstream=f"https://github.com/{repo}/tree/{rev}",sources=hashes,
                        normalized_tokens=n,in_reference_range=lo<=n<=hi,reference_rank=sum(scores)/len(scores))
    origin=summary({h:r["reference_rank"] for h,r in records.items()})
    passed=all(r["in_reference_range"] for r in records.values()) and origin["ci95"][0]>=0.30 and origin["ci95"][1]<=0.70
    report(DATA/"overlap.json",dict(protocol_sha256=digest(PARENT),reference_clean=panel,reference_range=[lo,hi],
           original_families=records,origin_token_check=origin,passed=bool(passed),
           scope="purposive development intake on original RTL length, not a blind transfer test"))
    print({h:r["normalized_tokens"] for h,r in records.items()},lo,hi,origin,passed,flush=True)
    if not passed: raise SystemExit("Stop before triplet construction")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--fetch",action="store_true")
    main(parser.parse_args().fetch)
