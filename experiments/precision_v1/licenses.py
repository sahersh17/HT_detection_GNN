"""Fetch the license accompanying each selected source revision for the portable bundle."""
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen
from urllib.error import HTTPError
from planning import DATA,RUN,read,report
from preflight import folder,sha

def collect(r):
    base=r["repo"].replace("https://github.com/","https://raw.githubusercontent.com/").rstrip("/")+"/"+r["commit"]+"/"
    for name in ("LICENSE","LICENSE.md","LICENSE.txt","COPYING"):
        try:
            with urlopen(base+name,timeout=12) as response:value=response.read(200001)
            if len(value)>200000 or len(value)<50:continue
            path=folder(r)/"source_license.txt";path.write_bytes(value)
            return dict(host=r["host"],source_url=base+name,sha256=sha(path))
        except (HTTPError,OSError):continue
    return dict(host=r["host"],source_url=None)
if __name__=="__main__":
    families=read(DATA/"intake.json")["families"]+read(DATA/"reserve_intake.json")["families"]
    with ThreadPoolExecutor(max_workers=8) as pool: found=list(pool.map(collect,families))
    report(RUN/"licenses.json",{x["host"]:x for x in found})
    print(sum(bool(x["source_url"]) for x in found),"pinned license texts of",len(found))
