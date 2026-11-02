"""Make a portable, hash-checked edit bundle without redistributing whole upstream projects."""
import argparse,base64,json,hashlib
from os.path import commonprefix
from urllib.request import urlopen
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
from planning import DATA,RUN,ROOT,read
from preflight import raw,sha

BUNDLE=DATA/"triplet_edits.zip"
def add(z,name,obj):
    z.writestr(ZipInfo(name),json.dumps(obj,indent=2).encode(),compress_type=ZIP_DEFLATED)
def main(pack,fetch):
    intake=read(DATA/"intake.json");manifest=read(DATA/"manifest.json")
    if (DATA/"reserve_intake.json").exists():intake["families"]+=read(DATA/"reserve_intake.json")["families"]
    rows={(r["host"],r["variant"]):r for r in manifest["records"]}
    if pack:
        notices=read(RUN/"licenses.json")
        with ZipFile(BUNDLE,"w") as z:
            for r in intake["families"]:
                h=r["host"]
                if (h,"clean") not in rows:continue
                recipes={}
                for side in ("benign","trojan"):
                    edits={}
                    for p,after_path in zip(raw(r),rows[h,side]["sources"],strict=True):
                        before=p.read_bytes();after=(ROOT/after_path).read_bytes()
                        if before==after:continue
                        a=len(commonprefix([before,after]))
                        suffix=len(commonprefix([before[a:][::-1],after[a:][::-1]]))
                        edits[p.name]=dict(start=a,end=len(before)-suffix,insert=base64.b64encode(after[a:len(after)-suffix]).decode())
                    recipes[side]=edits
                notice=notices[h]
                included=False
                if notice["source_url"]:
                    license_bytes=(RUN/"hosts"/h/"source_license.txt").read_bytes()
                    # Keep less familiar license terms as pinned fetch recipes.
                    included=any(t in license_bytes.lower() for t in
                                 (b"apache license",b"permission is hereby granted",b"redistribution and use in source and binary forms",b"gnu general public license"))
                    z.writestr(ZipInfo(h+"/LICENSE"),license_bytes,compress_type=ZIP_DEFLATED)
                if included:
                    for original in raw(r):
                        z.writestr(ZipInfo(h+"/original/"+original.name),original.read_bytes(),compress_type=ZIP_DEFLATED)
                add(z,h+".json",dict(repo=r["repo"],revision=r["commit"],original_files=r["sha256"],edits=recipes,
                    source_included=included,upstream_license=notice))
                add(z,h+"/observations.json",read(RUN/"hosts"/h/"oracle.json"))
                add(z,h+"/mutation.json",read(RUN/"hosts"/h/"edit.json"))
    with ZipFile(BUNDLE) as z:
        for r in intake["families"]:
            h=r["host"]
            if (h,"clean") not in rows:continue
            recipe=json.loads(z.read(h+".json"))
            for p in raw(r):
                if not p.exists() and recipe["source_included"]:
                    data=z.read(h+"/original/"+p.name)
                    if hashlib.sha256(data).hexdigest()!=r["sha256"][p.name]:raise ValueError("Bundled source hash changed")
                    p.parent.mkdir(parents=True,exist_ok=True)
                    p.write_bytes(data)
                if not p.exists() and fetch:
                    url=r["repo"].replace("https://github.com/","https://raw.githubusercontent.com/")+"/"+r["commit"]+"/src/"+p.name
                    p.parent.mkdir(parents=True,exist_ok=True)
                    with urlopen(url,timeout=30) as resp:source=resp.read()
                    if hashlib.sha256(source).hexdigest()!=r["sha256"][p.name]:raise ValueError("Remote source hash changed")
                    p.write_bytes(source)
                if sha(p)!=r["sha256"][p.name]:raise ValueError((h,p.name))
                for side in ("clean","benign","trojan"):
                    data=p.read_bytes();edit=recipe["edits"].get(side,{}).get(p.name)
                    if edit:data=data[:edit["start"]]+base64.b64decode(edit["insert"])+data[edit["end"]:]
                    expected=next(v for k,v in rows[h,side]["sources"].items() if k.rsplit("/",1)[-1]==p.name)
                    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError((h,side,p.name))
                    target=RUN/"materialized"/h/side/p.name
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    print(len(rows),"source sets matched their manifest hashes")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--pack",action="store_true");p.add_argument("--fetch",action="store_true")
    args=p.parse_args();main(args.pack,args.fetch)
