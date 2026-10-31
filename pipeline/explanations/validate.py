"""Reject explanation claims without verifiable Trojan RTL citations.

This checks citation existence and exact quoted text. Semantic truth still
requires comparison with a held-out reference and human review.
"""
import json
import sys
from pathlib import Path

KINDS = {"where", "trigger", "payload", "fix"}


def validate(explanation, source_root):
    root = Path(source_root).resolve()
    errors = []
    if not explanation.get("claims"):
        errors.append("No claims supplied")
    for i, claim in enumerate(explanation.get("claims", [])):
        if claim.get("kind") not in KINDS:
            errors.append(f"claim {i}: invalid kind")
        if not claim.get("text"):
            errors.append(f"claim {i}: empty text")
        if not claim.get("evidence"):
            errors.append(f"claim {i}: no RTL evidence")
        for j, cite in enumerate(claim.get("evidence", [])):
            try:
                target = (root / cite["file"]).resolve()
                if not target.is_relative_to(root) or not target.is_file():
                    raise ValueError("file missing or outside source root")
                line = int(cite["line"])
                lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
                if line < 1 or line > len(lines):
                    raise ValueError("line out of range")
                quote = str(cite["quote"]).strip()
                if not quote or quote not in lines[line - 1]:
                    raise ValueError("quote not present on cited line")
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"claim {i} evidence {j}: {exc}")
    return {"valid_citations": not errors, "errors": errors}


def main(explanation_path, source_root):
    explanation = json.loads(Path(explanation_path).read_text(encoding="utf-8"))
    result = validate(explanation, source_root)
    print(json.dumps(result, indent=2))
    return 0 if result["valid_citations"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
