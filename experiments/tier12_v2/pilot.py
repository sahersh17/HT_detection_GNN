"""Run the mixed-edit development revision through the original pilot checks."""
import argparse
import sys
from collections import Counter
from dataclasses import dataclass, replace
from os.path import commonprefix
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tier12_v1"))
import build
from hosts import HOSTS

DATA = build.ROOT / "data/tier12_v2"
RUN = build.ROOT / "runs/tier12_v2"


@dataclass(frozen=True)
class Site:
    kind: str
    clean: str
    benign: str
    trojan: str


# Three sites per operator. Both edits start from the same host implementation.
# Removals drop a conjunct or a disjunct from working logic. Replacements
# substitute a literal, reduction, or signal in an existing decision.
SITES = {
    "spi": Site("removal",
                "{((a[7] && a!=8'hd6) || a==8'hd6),a[6:0]}",
                "{((a[7]) || a==8'hd6),a[6:0]}",
                "{((a[7] && a!=8'hd6)),a[6:0]}"),
    "i2c": Site("removal",
                "b[0] && (tx!=8'hb3 || (tx==8'hb3 && b[0]))",
                "b[0] && (tx!=8'hb3 || (tx==8'hb3))",
                "b[0] && (tx!=8'hb3)"),
    "sram_ctrl": Site("removal",
                "((addr!=3 || val!=8'hce) ? val : 0) | ((addr==3 && val==8'hce) ? 8'hce : 0)",
                "((addr!=3 || val!=8'hce) ? val : 0) | ((val==8'hce) ? 8'hce : 0)",
                "((addr!=3 || val!=8'hce) ? val : 0)"),
    "crc32": Site("addition", "crc<=tmp;",
                  "crc<=tmp;\n  if (a==8'hd2 && crc==32'hffffffff) crc<=32'h4520a38a;",
                  "crc<=tmp;\n  if (a==8'hd2 && crc==32'hffffffff) crc<=32'h4520a38b;"),
    "mac": Site("addition", "acc<=acc+a*b;",
                "acc<=acc+a*b;\n  if (acc==255 && a==0) acc<=acc;",
                "acc<=acc+a*b;\n  if (acc==255 && a==0) acc<=0;"),
    "fir": Site("addition", "q<=a+2*d1+d2;",
                "q<=a+2*d1+d2;\n  if (d2==193 && d1==74) q<=a+341;",
                "q<=a+2*d1+d2;\n  if (d2==193 && d1==74) q<=a+340;"),
    "fifo": Site("replacement",
                 "(count==4 && queue[7:0]==8'he7 ? 8'he7 : queue[7:0])",
                 "(count==4 && queue[7:0]==8'he7 ? queue[7:0] : queue[7:0])",
                 "(count==4 && queue[7:0]==8'he7 ? 8'he6 : queue[7:0])"),
    "alu": Site("replacement",
                "(a==8'hb6 && b==8'h4d ? 8'hfb : a^b)",
                "(a==8'hb6 && b==8'h4d ? b^a : a^b)",
                "(a==8'hb6 && b==8'h4d ? 8'hfa : a^b)"),
    "pwm": Site("replacement",
                "(duty!=8'ha5 || count==255)",
                "(duty!=8'ha5 || (&count))",
                "(duty!=8'ha5 || count==254)"),
}


def classify_edit(before, after):
    """Classify a single contiguous edit after ignoring the shared prefix."""
    start = len(commonprefix([before, after]))
    if before == after:
        raise ValueError("Empty edit")
    if len(after) > len(before) and after.endswith(before[start:]):
        return "addition"
    if len(before) > len(after) and before.endswith(after[start:]):
        return "removal"
    return "replacement"


def revised_hosts():
    if set(SITES) != {host.name for host in HOSTS}:
        raise ValueError("Edit plan does not cover the nine original hosts")
    if Counter(s.kind for s in SITES.values()) != dict(addition=3, removal=3, replacement=3):
        raise ValueError("Unbalanced edit plan")
    for host in HOSTS:
        site = SITES[host.name]
        for edited in (site.benign, site.trojan):
            if classify_edit(site.clean, edited) != site.kind:
                raise ValueError(f"Edit disagrees with declared operation on {host.name}")
        body = host.body
        if site.kind == "addition":
            body = body.replace("EDIT", host.edits[0])
            if body.count(site.clean) != 1:
                raise ValueError(f"Missing unique assignment for {host.name}")
            # Group the original and any added assignments under the same enable.
            body = body.replace(site.clean, "begin\n  EDIT\nend")
        yield replace(host, body=body, edits=(site.clean, site.benign, site.trojan))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["verify", "audit"])
    stage = parser.parse_args().stage
    if stage == "verify":
        build.main(list(revised_hosts()), DATA, RUN, "tier12_rtl_v2",
                   build.OUT / "rtl", {name: site.kind for name, site in SITES.items()})
    else:
        import audit
        from representation import compare
        audit.main(DATA, RUN, "ver2_tier12_v2_catalog.json", graph_review=compare)


if __name__ == "__main__":
    main()
