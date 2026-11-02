"""Freeze hash-verified s38584 candidate evidence; never mark it expert-reviewed."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/localization_gate_audit"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for variant in ("T100", "T200", "T300"):
        benchmark = f"s38584-{variant}"
        source = ROOT / f"runs/new_trusthub/{benchmark}/trojan/s38584_scan.v"
        description = ROOT / f"runs/new_trusthub/{benchmark}/readme.txt"
        candidate = OUT / f"{benchmark}_candidate_labels.json"
        log = ROOT / f"runs/new_gate_v1/{benchmark}/trojan/yosys.log"
        text = source.read_text(encoding="utf-8", errors="replace")
        readme = description.read_text(encoding="utf-8", errors="replace")
        record = json.loads(candidate.read_text(encoding="utf-8"))
        if variant == "T100":
            evidence = ["INVX0 NOT_test_se ( .IN(test_se), .QN(test_se_NOT) )",
                        ".IN3(test_se_NOT), .Q(Tj_Trigger)",
                        "Trojan_Payload (.IN1(Tj_Trigger)",
                        ".D(g34028_Tj_Payload)"]
            if not all(fragment in text for fragment in evidence) or "functional mode" not in readme:
                raise ValueError("T100 trigger-to-payload evidence changed")
            status = "frozen_mechanical_candidate_pending_independent_review"
            finding = "NOT_test_se inverts test enable; its output enters Trojan_Trigger, which drives Trojan_Payload and a changed flip-flop D input."
        elif variant == "T200":
            evidence = ["RareVectorTrigger TrojanTrigger", ".S(Trigger_out)",
                        ".IN2(g25715)", ".Q(g10122)"]
            if not all(fragment in text for fragment in evidence) or "counter" not in readme.lower():
                raise ValueError("T200 trigger-to-payload evidence changed")
            status = "frozen_mechanical_candidate_pending_independent_review"
            finding = "RareVectorTrigger drives Trigger_out, which selects the payload mux from g25715 to g10122."
        else:
            evidence = ["HighActiveRegionDetection TrojanTrigger", "Tj_Trigger);",
                        ".S(Trigger_out)"]
            if not all(fragment in text for fragment in evidence) or "implicitly declared" not in log.read_text(encoding="utf-8"):
                raise ValueError("T300 disconnection evidence changed")
            status = "quarantined_functional_disconnect"
            finding = "Trigger module drives Tj_Trigger, payload mux selects Trigger_out; Yosys warns Trigger_out is implicitly declared."
        rows.append({"benchmark": benchmark, "status": status, "graph_id": record["graph_id"],
                     "positive_candidates": record["labels"].count(1),
                     "negative_candidates": record["labels"].count(0),
                     "unknown": record["labels"].count(-1),
                     "candidate_sha256": sha(candidate), "source_sha256": sha(source),
                     "description_sha256": sha(description), "yosys_log_sha256": sha(log),
                     "finding": finding, "evidence_fragments": evidence,
                     "reviewed": False})
    target = OUT / "s38584_candidate_freeze.json"
    target.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for row in rows:
        print(row["benchmark"], row["status"], row["positive_candidates"], row["unknown"])


if __name__ == "__main__":
    main()
