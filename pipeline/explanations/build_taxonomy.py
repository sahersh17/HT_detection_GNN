"""Draft trigger/payload reference categories from bundled benchmark descriptions.

These labels are a review queue, not a final expert-annotated evaluation set.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "localization_reference" / "manifest.json"
OUTPUT = ROOT / "data" / "localization_reference" / "taxonomy_draft.json"

# Explicit categories allow an auditor to check each description against the
# original benchmark README. No categories are inferred from model outputs.
CATEGORIES = {
    "AES-T100": ("always_on", "key_leakage_power_cdma"),
    "AES-T200": ("always_on", "key_leakage_power_cdma"),
    "AES-T400": ("predefined_plaintext", "key_leakage_rf"),
    "AES-T700": ("predefined_plaintext", "key_leakage_power_cdma"),
    "AES-T800": ("plaintext_sequence", "key_leakage_power_cdma"),
    "AES-T900": ("encryption_count", "key_leakage_power_cdma"),
    "AES-T1000": ("predefined_plaintext", "key_leakage_power_cdma"),
    "AES-T1100": ("plaintext_sequence", "key_leakage_power_cdma"),
    "AES-T1200": ("encryption_count", "key_leakage_power_cdma"),
    "AES-T1600": ("plaintext_sequence", "key_leakage_rf"),
    "AES-T1700": ("encryption_count", "key_leakage_rf"),
    "AES-T2300": ("two_signal_condition", "ciphertext_bit_flip"),
    "AES-T2400": ("two_signal_condition", "ciphertext_bit_flip"),
    "AES-T2500": ("synchronous_counter", "ciphertext_bit_flip"),
    "AES-T2600": ("asynchronous_counter", "ciphertext_bit_flip"),
    "AES-T2700": ("cascaded_counters", "ciphertext_bit_flip"),
    "AES-T2800": ("counters_and_signals", "ciphertext_bit_flip"),
    "RS232-T2100": ("rare_branch", "ready_signal_suppressed"),
    "RS232-T2200": ("state_machine_state", "ready_signal_suppressed"),
    "RS232-T2300": ("state_transition", "ready_signal_suppressed"),
    "RS232-T2400": ("branch_count", "ready_signal_suppressed"),
}


def main():
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    names = {r["benchmark"] for r in rows}
    if names != set(CATEGORIES):
        raise ValueError(f"Reference mismatch: missing={names - set(CATEGORIES)}, extra={set(CATEGORIES) - names}")
    draft = [{"benchmark": r["benchmark"], "trigger_type": CATEGORIES[r["benchmark"]][0],
              "payload_type": CATEGORIES[r["benchmark"]][1],
              "evidence_document": r["description"]["path"],
              "evidence_sha256": r["description"]["sha256"],
              "review_status": "draft_requires_hardware_expert_review",
              "fix_reference": None} for r in rows]
    OUTPUT.write_text(json.dumps({"annotations": draft}, indent=2), encoding="utf-8")
    print(f"Wrote {len(draft)} draft taxonomy records to {OUTPUT}")


if __name__ == "__main__":
    main()
