"""Index original digital Verilog sources named by the staged Tiny Tapeout shuttle metadata."""
import json,yaml
from planning import RUN,report
def main():
    rows=[]
    for path in sorted(RUN.glob("tt*/projects/*/info.yaml")):
        try:
            metadata=yaml.safe_load(path.read_text(encoding="utf-8"))
            project=dict(metadata.get("documentation",{}),**metadata["project"])
            pin=json.loads(path.with_name("commit_id.json").read_text())
            files=project["source_files"]
            if str(project["language"]).lower() not in ("verilog","systemverilog"):continue
            if not all(f.endswith(".v") and "/" not in f for f in files):continue
            if not pin.get("repo","").startswith("https://github.com/") or not pin.get("commit"):continue
            rows.append(dict(repo=pin["repo"],commit=pin["commit"],host=project["top_module"],title=project["title"],
                author=project["author"],files=files,path=path.relative_to(RUN.parents[1]).as_posix()))
        except (KeyError,OSError,UnicodeError,ValueError,TypeError,yaml.YAMLError):
            continue
    report(RUN/"inventory.json",rows)
    print(len(rows),"metadata-qualified entries")
if __name__=="__main__":main()
