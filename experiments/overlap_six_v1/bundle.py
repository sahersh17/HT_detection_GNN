"""Pack pinned source bytes and byte-exact triplet edits, or materialize them offline."""
import argparse
import base64
import hashlib
import json
from os.path import commonprefix
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from intake import DATA, HOSTS, ROOT, RUN, SIDES, UP, digest, raw_paths

BUNDLE=DATA/"sources.zip"
LICENSES={"divider":"COPYING.txt","logic_scope":"doc/gpl-3.0.pdf","sha2":"LICENSE",
          "i2c_controller":"COPYING","jpeg_huffman":"LICENSE","picorv32":"COPYING"}


def add(archive,name,content):
    archive.writestr(ZipInfo(name),content,compress_type=ZIP_DEFLATED)


def pack(records):
    index={}
    with ZipFile(BUNDLE,"w") as archive:
        for host,(_,repo,commit,_) in HOSTS.items():
            originals=raw_paths(host)
            folder=UP/repo.split("/")[1]
            license_file=LICENSES[host]
            add(archive,host+"/"+license_file,(folder/license_file).read_bytes())
            index[host]=dict(upstream=repo,revision=commit,files=[p.name for p in originals],edits={})
            for path,expected in zip(originals,records[host,"clean"]["sources"].values()):
                if digest(path)!=expected: raise ValueError(f"Changed upstream file: {path}")
                add(archive,host+"/"+path.name,path.read_bytes())
            before=originals[0].read_bytes()
            for side in ("benign","trojan"):
                candidate=ROOT/next(iter(records[host,side]["sources"]))
                after=candidate.read_bytes()
                start=len(commonprefix([before,after]))
                tail=len(commonprefix([before[start:][::-1],after[start:][::-1]]))
                index[host]["edits"][side]=dict(start=start,end=len(before)-tail,
                    insert=base64.b64encode(after[start:len(after)-tail]).decode())
        add(archive,"triplets.json",json.dumps(index,indent=2)+"\n")


def materialize(records):
    with ZipFile(BUNDLE) as archive:
        index=json.loads(archive.read("triplets.json"))
        for host in HOSTS:
            for side in SIDES:
                for i,(name,expected) in enumerate(zip(index[host]["files"],records[host,side]["sources"].values(),strict=True)):
                    data=archive.read(host+"/"+name)
                    if side!="clean" and i==0:
                        edit=index[host]["edits"][side]
                        data=data[:edit["start"]]+base64.b64decode(edit["insert"])+data[edit["end"]:]
                    if hashlib.sha256(data).hexdigest()!=expected: raise ValueError((host,side,name))
                    target=RUN/"materialized"/host/side/name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(data)
                license_file=LICENSES[host]
                target=RUN/"materialized"/host/side/license_file
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.read(host+"/"+license_file))
    print("All 18 standalone source sets match their manifest hashes.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--pack",action="store_true")
    args=parser.parse_args()
    records={(r["host"],r["variant"]):r for r in json.loads((DATA/"manifest.json").read_text())["records"]}
    if args.pack: pack(records)
    materialize(records)
