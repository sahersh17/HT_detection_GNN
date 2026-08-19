from pathlib import Path
import json
import re
import hashlib
import os
import time

# ==========================================================
# CONFIG
# ==========================================================

NETLIST_ROOT = Path(r"C:\HT_detection_GNN\trusthub\netlists")   # where the .ys scripts live
FEATURES_ROOT = Path(r"C:\HT_detection_GNN\trusthub\features")   # has manifest.json from 05
OUTPUT_ROOT = Path(r"C:\HT_detection_GNN\trusthub\semantic_features")

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

MODEL = "gemini-2.5-flash"    # swap to "gemini-2.5-pro" for higher quality, slower/costlier
MAX_RTL_CHARS = 60000         # rough safety cap per LLM call; large files get truncated with a note
LIMIT = 5                  # set to an int (e.g. 5) to test on a few benchmarks before a full run
RETRY_COUNT = 1
RETRY_DELAY_SECONDS = 5
REQUEST_DELAY_SECONDS = 4   # spacing between actual (non-cached) API calls

# ==========================================================
# LLM client setup
# ==========================================================
#
# Requires: pip install google-genai
# Requires: GEMINI_API_KEY environment variable set
#
try:
    from google import genai
    from google.genai import types
except ImportError:
    raise SystemExit(
        "The 'google-genai' package is required for this script.\n"
        "Install it with: pip install google-genai"
    )

if "GEMINI_API_KEY" not in os.environ:
    raise SystemExit(
        "GEMINI_API_KEY environment variable is not set.\n"
        "Set it before running this script."
    )

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ==========================================================
# Extract RTL source file list from a .ys script
# ==========================================================

READ_VERILOG_RE = re.compile(r'read_verilog\s+"([^"]+)"')

def get_source_files_from_ys(ys_path):
    """
    Your synthesis scripts (02_synthesize_*.py) wrote every RTL file they
    fed into Yosys as a `read_verilog "path"` line in the .ys script. This
    reconstructs the exact non-testbench source file list used for a given
    netlist, without needing a separate path-mapping step.
    """
    text = ys_path.read_text(errors="ignore")
    return [Path(p) for p in READ_VERILOG_RE.findall(text)]


def locate_ys_file(graph_id):
    """
    graph_id looks like 'AES/AES-T100/clean_netlist' (from 05's manifest).
    The matching .ys script sits at netlists/AES/AES-T100/clean.ys —
    same relative folder, tag name before '_netlist' + '.ys'.
    """
    parts = graph_id.split("/")
    family, bench, tag = parts[0], parts[1], parts[2]
    tag = tag.replace("_netlist", "")
    return NETLIST_ROOT / family / bench / f"{tag}.ys"


# ==========================================================
# LLM prompt
# ==========================================================

SYSTEM_PROMPT = """You are assisting a hardware security researcher in \
analyzing Verilog RTL for signs of a hardware Trojan trigger. A hardware \
Trojan trigger is logic that activates only under a rare, specific \
condition (e.g. a wide comparator checking many signal bits against a \
fixed pattern, a counter that must reach an unusual value, or a rarely-hit \
state in a state machine), and produces some effect when triggered.

You will be given Verilog source code. Identify signals, wires, or \
instances that plausibly relate to rare-condition trigger logic. Only \
reference names that literally appear in the provided code — never invent \
or guess a signal name. If nothing suspicious is present, return an empty \
list; do not force a finding.

Respond with ONLY a JSON array (no other text, no markdown fences), where \
each entry has:
{
  "signal_or_instance": "<exact name from the code>",
  "reason": "<one sentence, grounded in what the code actually does>",
  "suspicion_score": <float 0.0-1.0>
}
"""

RESPONSE_SCHEMA = types.Schema(
    type=types.Type.ARRAY,
    items=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "signal_or_instance": types.Schema(type=types.Type.STRING),
            "reason": types.Schema(type=types.Type.STRING),
            "suspicion_score": types.Schema(type=types.Type.NUMBER),
        },
        required=["signal_or_instance", "reason", "suspicion_score"],
    ),
)

def _extract_retry_delay(error, default=RETRY_DELAY_SECONDS):
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)", str(error))
    return int(match.group(1)) + 1 if match else default

def analyze_rtl(rtl_text):
    if len(rtl_text) > MAX_RTL_CHARS:
        rtl_text = rtl_text[:MAX_RTL_CHARS] + "\n\n/* ... truncated ... */"

    last_error = None

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            response = client.models.generate_content( #use send_message
                model=MODEL,
                contents=rtl_text,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    temperature=0.0,
                ),
            )

            raw = response.text.strip()
            findings = json.loads(raw)

            if not isinstance(findings, list):
                raise ValueError("Response was not a JSON array")

            return findings

        except Exception as e:
            last_error = e
            print(f"      WARNING: attempt {attempt}/{RETRY_COUNT} failed ({e})")
            if attempt < RETRY_COUNT:
                time.sleep(_extract_retry_delay(e))

    print(f"      GIVING UP after {RETRY_COUNT} attempts: {last_error}")
    return []


# ==========================================================
# MAIN
# ==========================================================

with open(FEATURES_ROOT / "manifest.json", "r") as f:
    manifest = json.load(f)

if LIMIT is not None:
    manifest = manifest[:LIMIT]

print(f"Processing {len(manifest)} graphs\n")

# Cache: identical concatenated RTL source (e.g. the same clean aes_128.v
# reused across many T-variants) is only sent to the LLM once.
source_cache = {}  # content_hash -> findings

semantic_manifest = []
success = 0
skipped_missing_ys = 0
failed = 0

for entry in manifest:
    graph_id = entry["graph_id"]
    label = entry["label"]

    print("-" * 70)
    print(graph_id)

    ys_path = locate_ys_file(graph_id)
    if not ys_path.exists():
        print(f"      SKIP: no .ys file found at {ys_path}")
        skipped_missing_ys += 1
        continue

    try:
        source_files = get_source_files_from_ys(ys_path)
        source_files = [p for p in source_files if p.exists()]

        if not source_files:
            print("      SKIP: no readable source files listed in .ys")
            skipped_missing_ys += 1
            continue

        combined = "\n\n".join(
            f"// ---- {p.name} ----\n{p.read_text(errors='ignore')}"
            for p in source_files
        )

        content_hash = hashlib.sha256(combined.encode("utf-8", errors="ignore")).hexdigest()

        if content_hash in source_cache:
            print("      (cache hit — identical source already analyzed)")
            findings = source_cache[content_hash]
        else:
            findings = analyze_rtl(combined)
            source_cache[content_hash] = findings
            time.sleep(REQUEST_DELAY_SECONDS)

        out_path = (OUTPUT_ROOT / graph_id).with_suffix(".json")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        result = {
            "graph_id": graph_id,
            "label": label,
            "source_files": [str(p) for p in source_files],
            "content_hash": content_hash,
            "findings": findings,
        }

        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)

        semantic_manifest.append({
            "graph_id": graph_id,
            "label": label,
            "semantic_path": str(out_path),
            "num_findings": len(findings),
        })

        print(f"      Findings: {len(findings)}")
        success += 1

    except Exception as e:
        print(f"      FAILED: {e}")
        failed += 1

with open(OUTPUT_ROOT / "manifest.json", "w") as f:
    json.dump(semantic_manifest, f, indent=2)

print("\n" + "=" * 70)
print("Semantic feature extraction complete")
print(f"Successful          : {success}")
print(f"Skipped (no .ys)     : {skipped_missing_ys}")
print(f"Failed               : {failed}")
print(f"Unique source sets   : {len(source_cache)}  (of {len(manifest)} graphs — caching saved "
      f"{len(manifest) - len(source_cache)} API calls)")
print(f"Manifest             : {OUTPUT_ROOT / 'manifest.json'}")
print("=" * 70)