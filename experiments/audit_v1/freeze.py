"""Record and verify a reproducible snapshot of prospective audit rules.

This is a local versioned snapshot, not a timestamped preregistration or an
untouched external test. Existing pilot results are explicitly retrospective.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/audit_v1/freeze.json"
FILES = (
    "experiments/audit_v1/protocol.json",
    "experiments/matched_insertion_v3/generate.py",
    "experiments/matched_insertion_v3/verify.py",
    "experiments/matched_insertion_v3/controls.py",
    "experiments/matched_insertion_v3/prove_isomorphism.py",
    "experiments/port_aware_v1/build.py",
    "experiments/port_aware_v1/probe.py",
    "experiments/rtl_lexical_v1/metadata_controls.py",
    "data/rtl_lexical_v1/metadata_controls.json",
    "data/lofo_expanded_b19/protocol.json",
    "data/audit_v1/host_inventory.json",
    "data/audit_v1/b19_embedding_audit.json",
    "runs/matched_insertion_v3/manifest.json",
    "runs/matched_insertion_v3/verification.json",
    "runs/matched_insertion_v3/controls.json",
    "runs/matched_insertion_v3/isomorphism.json",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        freeze = json.loads(OUT.read_text(encoding="utf-8"))
        for name, expected in freeze["sha256"].items():
            if sha256(ROOT / name) != expected:
                raise ValueError(f"Frozen input changed: {name}")
        if set(freeze["sha256"]) != set(FILES):
            raise ValueError("Frozen file list changed")
        print(f"Verified {len(FILES)} frozen inputs")
        return
    if OUT.exists():
        raise FileExistsError("Audit snapshot already exists; version a new protocol instead")
    freeze = {"status": "local_snapshot_for_future_work_not_external_preregistration",
              "protocol_version": "audit_v1_2026-11-02",
              "sha256": {name: sha256(ROOT / name) for name in FILES}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(freeze, indent=2), encoding="utf-8")
    print(f"Froze {len(FILES)} inputs in {OUT}")


if __name__ == "__main__":
    main()
