"""Generate length-preserving RTL lexical controls without changing project sources."""
import argparse
import codecs
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from build import source_files  # noqa: E402

OUT = ROOT / "runs/rtl_lexical_v1"
KEYWORDS = set("always and assign automatic begin buf bufif0 bufif1 case casex casez cell cmos config deassign default defparam disable edge else end endcase endconfig endfunction endgenerate endmodule endprimitive endspecify endtable endtask event for force forever fork function generate genvar highz0 highz1 if ifnone incdir include initial inout input instance integer join large liblist library localparam macromodule medium module nand negedge nmos nor noshowcancelled not notif0 notif1 or output parameter pmos posedge primitive pull0 pull1 pulldown pullup pulsestyle_one pulsestyle_ondetect rcmos real realtime reg release repeat rnmos rpmos rtran rtranif0 rtranif1 scalared showcancelled signed small specify specparam strong0 strong1 supply0 supply1 table task time tran tranif0 tranif1 tri tri0 tri1 triand trior trireg unsigned use vectored wait wand weak0 weak1 while wire wor xnor xor logic bit byte shortint int longint typedef struct enum packed endpackage package import export interface endinterface modport unique priority".split())
TOKEN = re.compile(r'^[ \t]*`[^\n]*|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\\[^\s]+|\d+\s*\'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|[A-Za-z_$][\w$]*|[^A-Za-z_$/"\\0-9`\n]+|\n|.', re.M)
IDENT = re.compile(r"[A-Za-z_$][\w$]*\Z")


def rename(name):
    if name.lower() in KEYWORDS or name.startswith("$"):
        return name
    converted = codecs.encode(name, "rot_13")
    converted = "".join(str((int(c)+5)%10) if c.isdigit() else c for c in converted)
    return name if converted.lower() in KEYWORDS else converted


def transform(text, strip_comments=False, rename_identifiers=False):
    output = []
    comment_count = 0
    renamed = 0
    for token in TOKEN.findall(text):
        if token.lstrip().startswith("`"):
            # Preserve macro definitions, includes and conditional directives.
            # Their semantics cannot be checked by renaming individual tokens.
            output.append(token)
        elif token.startswith(("//", "/*")):
            comment_count += 1
            output.append("".join("\n" if c == "\n" else " " for c in token) if strip_comments else token)
        elif rename_identifiers and IDENT.fullmatch(token):
            changed = rename(token)
            renamed += changed != token
            output.append(changed)
        else:
            output.append(token)
    result = "".join(output)
    if len(result) != len(text) or result.count("\n") != text.count("\n"):
        raise ValueError("Lexical control changed character or line count")
    return result, comment_count, renamed


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", action="append")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/integrated/paired_manifest.json").read_text(encoding="utf-8"))
    selected = args.benchmark or sorted({s["benchmark"] for s in manifest["samples"]})
    arms = {"comments": (True, False), "names": (False, True), "both": (True, True)}
    rows = []
    for benchmark in selected:
        for side in ("clean", "trojan"):
            files, top = source_files(benchmark, side)
            includes = sorted(files[0].parent.glob("*.h"))
            for arm, (strip, rename_ids) in arms.items():
                records = []
                include_records = []
                for source in [*files, *includes]:
                    raw = source.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
                    converted, comments, renamed = transform(raw, strip, rename_ids)
                    target = OUT / arm / benchmark / side / source.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(converted, encoding="utf-8", newline="\n")
                    destination = include_records if source.suffix.lower() == ".h" else records
                    destination.append({"original": source.relative_to(ROOT).as_posix(),
                                    "transformed": target.relative_to(ROOT).as_posix(),
                                    "original_sha256": sha(raw), "transformed_sha256": sha(converted),
                                    "comments": comments, "renamed_tokens": renamed})
                rows.append({"benchmark": benchmark, "side": side, "arm": arm,
                             "original_top": top, "transformed_top": rename(top) if rename_ids else top,
                             "files": records, "includes": include_records})
        print(benchmark, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps({"status": "generated_unverified", "arms": list(arms),
        "transform": "comment whitespace preserving; bijective ROT13 letters and +5 digits for non-keyword identifiers",
        "records": rows}, indent=2), encoding="utf-8")
    print(f"{len(rows)} design-side-arm records")


if __name__ == "__main__":
    main()
