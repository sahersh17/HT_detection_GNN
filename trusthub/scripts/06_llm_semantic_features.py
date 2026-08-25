from pathlib import Path
import json
import re
import hashlib
import time

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


# ==========================================================
# CONFIG
# ==========================================================

NETLIST_ROOT = Path(
    r"C:\HT_detection_GNN\trusthub\netlists"
)

FEATURES_ROOT = Path(
    r"C:\HT_detection_GNN\trusthub\features"
)

OUTPUT_ROOT = Path(
    r"C:\HT_detection_GNN\trusthub\semantic_features"
)

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


# ==========================================================
# QWEN3 CONFIG
# ==========================================================

MODEL = "Qwen/Qwen3-8B"

MAX_RTL_CHARS = 60000

# Set to an integer such as 5 for testing.
# Set to None for the full dataset.
LIMIT = 5

MAX_NEW_TOKENS = 1024

# Qwen3 non-thinking mode settings
TEMPERATURE = 0.7
TOP_P = 0.8
TOP_K = 20

# Small delay between uncached model calls
REQUEST_DELAY_SECONDS = 1


# ==========================================================
# LOAD QWEN3-8B
# ==========================================================

print("=" * 70)
print("Loading Qwen3-8B")
print("=" * 70)

print(f"Model: {MODEL}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(
        f"GPU memory: "
        f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB"
    )
else:
    print(
        "WARNING: CUDA is not available. "
        "Qwen3-8B will run on CPU and may be very slow."
    )

print("\nLoading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL,
    trust_remote_code=True,
)

print("Loading model...")

model = AutoModelForCausalLM.from_pretrained(
    MODEL,
    torch_dtype="auto",
    device_map="auto",
    trust_remote_code=True,
)

model.eval()

print("Qwen3-8B loaded successfully.")

if torch.cuda.is_available():
    print(
        f"Allocated GPU memory: "
        f"{torch.cuda.memory_allocated() / 1024**3:.2f} GB"
    )

print("=" * 70)
print()


# ==========================================================
# EXTRACT RTL SOURCE FILE LIST FROM .YS SCRIPT
# ==========================================================

READ_VERILOG_RE = re.compile(
    r'read_verilog\s+"([^"]+)"'
)


def get_source_files_from_ys(ys_path):
    """
    The synthesis scripts contain lines such as:

        read_verilog "path/to/file.v"

    Reconstruct the exact RTL source files used by Yosys.
    """

    text = ys_path.read_text(errors="ignore")

    return [
        Path(p)
        for p in READ_VERILOG_RE.findall(text)
    ]


def locate_ys_file(graph_id):
    """
    graph_id example:

        AES/AES-T100/clean_netlist

    Matching synthesis script:

        netlists/AES/AES-T100/clean.ys
    """

    parts = graph_id.split("/")

    family = parts[0]
    bench = parts[1]
    tag = parts[2]

    tag = tag.replace("_netlist", "")

    return (
        NETLIST_ROOT
        / family
        / bench
        / f"{tag}.ys"
    )


# ==========================================================
# SYSTEM PROMPT
# ==========================================================

SYSTEM_PROMPT = """
You are assisting a hardware security researcher analyzing
Verilog RTL for signs of a Hardware Trojan trigger.

A Hardware Trojan trigger is logic that activates only under
a rare or specific condition, for example:

- a wide comparator checking many signal bits against a
  fixed or unusual pattern
- a counter reaching an unusual value
- a rarely activated state-machine state
- a combination of internal signals that is unlikely during
  normal operation
- logic that detects a particular sequence of events
- unusual enable conditions
- dormant control logic that appears unrelated to the
  normal function of the circuit

Analyze ONLY the Verilog source code provided.

IMPORTANT RULES:

1. Only reference signal, wire, register, module, or instance
   names that literally appear in the provided code.

2. NEVER invent signal names.

3. Ground every finding in the actual RTL.

4. Do not assume that unusual logic is automatically a Trojan.

5. If nothing suspicious is present, return an empty JSON array.

6. Do not report normal datapath logic merely because it is
   complicated.

7. Focus specifically on logic that plausibly represents a
   rare-condition trigger.

8. Return ONLY valid JSON.

9. Do NOT use markdown.

10. Do NOT include explanations outside the JSON.

Required JSON format:

[
  {
    "signal_or_instance": "exact_signal_name",
    "reason": "one sentence explaining why this logic may represent a rare trigger",
    "suspicion_score": 0.85
  }
]

The suspicion_score must be a floating point value between
0.0 and 1.0.
"""


# ==========================================================
# JSON EXTRACTION
# ==========================================================

def extract_json_array(text):
    """
    Qwen can occasionally produce a small amount of text
    around the JSON despite the instruction.

    This function extracts the first valid JSON array.
    """

    text = text.strip()

    # Remove possible markdown fences
    text = re.sub(
        r"```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = text.replace("```", "").strip()

    # First try the entire response
    try:
        parsed = json.loads(text)

        if isinstance(parsed, list):
            return parsed

    except json.JSONDecodeError:
        pass

    # Otherwise locate the first JSON array
    start = text.find("[")

    if start == -1:
        raise ValueError(
            "No JSON array found in model response."
        )

    # Find matching closing bracket
    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):

        char = text[i]

        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "[":
            depth += 1

        elif char == "]":
            depth -= 1

            if depth == 0:

                candidate = text[start:i + 1]

                parsed = json.loads(candidate)

                if not isinstance(parsed, list):
                    raise ValueError(
                        "Extracted JSON is not a list."
                    )

                return parsed

    raise ValueError(
        "Could not locate a complete JSON array."
    )


# ==========================================================
# VALIDATE FINDINGS
# ==========================================================

def validate_findings(findings):

    if not isinstance(findings, list):
        raise ValueError(
            "Model response is not a JSON array."
        )

    validated = []

    for item in findings:

        if not isinstance(item, dict):
            continue

        signal = item.get(
            "signal_or_instance"
        )

        reason = item.get(
            "reason"
        )

        score = item.get(
            "suspicion_score"
        )

        if not isinstance(signal, str):
            continue

        if not isinstance(reason, str):
            continue

        try:
            score = float(score)
        except (TypeError, ValueError):
            continue

        score = max(
            0.0,
            min(1.0, score)
        )

        validated.append(
            {
                "signal_or_instance": signal,
                "reason": reason,
                "suspicion_score": score,
            }
        )

    return validated


# ==========================================================
# QWEN RTL ANALYSIS
# ==========================================================

def analyze_rtl(rtl_text):

    if len(rtl_text) > MAX_RTL_CHARS:

        rtl_text = (
            rtl_text[:MAX_RTL_CHARS]
            + "\n\n"
            "/* ... RTL truncated because it exceeded "
            "MAX_RTL_CHARS ... */"
        )

    user_prompt = f"""
Analyze the following Verilog RTL for possible
Hardware Trojan trigger logic.

Return ONLY the required JSON array.

{rtl_text}
"""

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    # ------------------------------------------------------
    # IMPORTANT:
    # Qwen3 normally enables thinking.
    #
    # For this structured extraction task we explicitly
    # disable thinking to reduce unnecessary output and
    # generation time.
    # ------------------------------------------------------

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    inputs = tokenizer(
        [text],
        return_tensors="pt",
        padding=True,
    )

    inputs = {
        key: value.to(model.device)
        for key, value in inputs.items()
    }

    input_length = inputs["input_ids"].shape[-1]

    with torch.inference_mode():

        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            top_k=TOP_K,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][
        input_length:
    ]

    response_text = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    ).strip()

    findings = extract_json_array(
        response_text
    )

    findings = validate_findings(
        findings
    )

    return findings


# ==========================================================
# LOAD MANIFEST
# ==========================================================

manifest_path = (
    FEATURES_ROOT / "manifest.json"
)

with open(
    manifest_path,
    "r",
    encoding="utf-8",
) as f:

    manifest = json.load(f)


if LIMIT is not None:

    manifest = manifest[:LIMIT]


print(
    f"Processing {len(manifest)} graphs\n"
)


# ==========================================================
# CACHE
# ==========================================================

# Identical RTL source is only analyzed once.

source_cache = {}


# ==========================================================
# STATISTICS
# ==========================================================

semantic_manifest = []

success = 0
skipped_missing_ys = 0
failed = 0


# ==========================================================
# MAIN LOOP
# ==========================================================

for entry in manifest:

    graph_id = entry["graph_id"]
    label = entry["label"]

    print("-" * 70)
    print(graph_id)

    # ------------------------------------------------------
    # Locate synthesis script
    # ------------------------------------------------------

    ys_path = locate_ys_file(
        graph_id
    )

    if not ys_path.exists():

        print(
            f"      SKIP: no .ys file found at {ys_path}"
        )

        skipped_missing_ys += 1

        continue

    try:

        # --------------------------------------------------
        # Get RTL source files
        # --------------------------------------------------

        source_files = (
            get_source_files_from_ys(
                ys_path
            )
        )

        source_files = [
            p
            for p in source_files
            if p.exists()
        ]

        if not source_files:

            print(
                "      SKIP: no readable source files "
                "listed in .ys"
            )

            skipped_missing_ys += 1

            continue

        print(
            f"      RTL files: {len(source_files)}"
        )

        # --------------------------------------------------
        # Combine RTL
        # --------------------------------------------------

        combined_parts = []

        for p in source_files:

            combined_parts.append(
                f"// ---- {p.name} ----\n"
                f"{p.read_text(errors='ignore')}"
            )

        combined = "\n\n".join(
            combined_parts
        )

        # --------------------------------------------------
        # Hash source
        # --------------------------------------------------

        content_hash = hashlib.sha256(
            combined.encode(
                "utf-8",
                errors="ignore",
            )
        ).hexdigest()

        # --------------------------------------------------
        # Cache check
        # --------------------------------------------------

        if content_hash in source_cache:

            print(
                "      Cache hit — "
                "identical RTL already analyzed"
            )

            findings = source_cache[
                content_hash
            ]

        else:

            print(
                "      Running Qwen3-8B..."
            )

            start_time = time.time()

            findings = analyze_rtl(
                combined
            )

            elapsed = (
                time.time() - start_time
            )

            print(
                f"      Inference time: "
                f"{elapsed:.2f}s"
            )

            source_cache[
                content_hash
            ] = findings

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

        # --------------------------------------------------
        # Output path
        # --------------------------------------------------

        out_path = (
            OUTPUT_ROOT / graph_id
        ).with_suffix(".json")

        out_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # --------------------------------------------------
        # Save result
        # --------------------------------------------------

        result = {
            "graph_id": graph_id,
            "label": label,
            "model": MODEL,
            "source_files": [
                str(p)
                for p in source_files
            ],
            "content_hash": content_hash,
            "findings": findings,
        }

        with open(
            out_path,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                result,
                f,
                indent=2,
            )

        # --------------------------------------------------
        # Manifest entry
        # --------------------------------------------------

        semantic_manifest.append(
            {
                "graph_id": graph_id,
                "label": label,
                "semantic_path": str(
                    out_path
                ),
                "num_findings": len(
                    findings
                ),
            }
        )

        print(
            f"      Findings: {len(findings)}"
        )

        # Print findings for quick inspection
        for finding in findings:

            print(
                f"        - "
                f"{finding['signal_or_instance']} "
                f""
                f"(score="
                f"{finding['suspicion_score']:.2f})"
            )

        success += 1

    except Exception as e:

        print(
            f"      FAILED: {e}"
        )

        failed += 1


# ==========================================================
# WRITE SEMANTIC MANIFEST
# ==========================================================

semantic_manifest_path = (
    OUTPUT_ROOT / "manifest.json"
)

with open(
    semantic_manifest_path,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        semantic_manifest,
        f,
        indent=2,
    )


# ==========================================================
# FINAL SUMMARY
# ==========================================================

print("\n" + "=" * 70)

print(
    "Semantic feature extraction complete"
)

print(
    f"Successful          : {success}"
)

print(
    f"Skipped (no .ys)    : "
    f"{skipped_missing_ys}"
)

print(
    f"Failed              : {failed}"
)

print(
    f"Unique source sets  : "
    f"{len(source_cache)} "
    f"(of {len(manifest)} graphs)"
)

print(
    f"Cached analyses     : "
    f"{len(manifest) - len(source_cache)}"
)

print(
    f"Model               : {MODEL}"
)

print(
    f"Manifest             : "
    f"{semantic_manifest_path}"
)

print("=" * 70)
