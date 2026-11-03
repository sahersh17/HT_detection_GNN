"""Lock the current circuit inventory and host-grouped development folds.

This stage reads existing, locally verified artifacts. It does not fit a model
or inspect the reserved project candidates.
"""

import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/dataset_stage1"
SEED = 20261103
FOLDS = 5
sys.path.insert(0, str(ROOT / "experiments/training_audit_v3"))
from sanitize import sanitize, text_for

BASELINE_MECHANISMS = {
    "divider": "bitwise_operator_change",
    "logic_scope": "mask_change",
    "sha2": "constant_change",
    "i2c_controller": "bit_slice_change",
    "jpeg_huffman": "constant_change",
    "picorv32": "bitwise_operator_change",
}
FOUR_PROJECTS = {
    "verilog-axis": "alexforencich/verilog-axis",
    "sha1": "secworks/sha1",
    "uart16550": "freecores/uart16550",
    "core_usb_uart": "ultraembedded/core_usb_uart",
}
FLOW = {
    "baseline": "overlap_v1_yowasp_no_abc",
    "native": "precision_v1_yowasp_no_abc",
    "four_projects": "transfer_v1_yowasp_no_abc",
    "external_authored": "provenance_v1_yowasp_no_abc",
    "test": "provenance_expansion_yowasp_no_abc",
}


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_hash(value):
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def save(path, value):
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise ValueError(f"Locked artifact would change: {path}")
    path.write_text(payload, encoding="utf-8")


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def project_metadata(host, cohort, baseline, precision, screen):
    if cohort == "baseline":
        upstream = baseline["original_families"][host]["upstream"]
        match = re.fullmatch(r"https://github.com/([^/]+/[^/]+)/tree/([0-9a-f]+)", upstream)
        if match is None:
            raise ValueError(f"Unrecognized pinned baseline project: {upstream}")
        return match.group(1), match.group(2), BASELINE_MECHANISMS[host]
    if cohort == "native":
        clean = precision[host]["clean"]
        revisions = {part for source in clean["sources"] for part in source.split("/")
                     if re.fullmatch(r"[0-9a-f]{40}", part)}
        if len(revisions) != 1:
            raise ValueError(f"Ambiguous native revision for {host}")
        revision = revisions.pop()
        matches = {(row["repo"], row["revision"]) for row in screen[host]
                   if row["revision"] == revision}
        if len(matches) != 1:
            raise ValueError(f"Ambiguous native repository for {host}")
        repo = matches.pop()[0]
        if not repo.startswith("https://github.com/"):
            raise ValueError(f"Unexpected native repository for {host}")
        edit_kind = clean["edit_kind"]
        if edit_kind not in ("literal", "pin_select"):
            raise ValueError(f"Unrecognized native edit kind: {edit_kind}")
        return repo.removeprefix("https://github.com/"), revision, edit_kind
    if cohort == "four_projects":
        return FOUR_PROJECTS[host], read("data/transfer_v1/intake.json")["pins"][host], "conditional_output_fault"
    if cohort == "external_authored":
        return "TrustHub/RS232", "benchmark_archive", "receive_readiness_suppression"
    if cohort == "test":
        return f"TrustHub/{host}", "benchmark_archive", "unknown_original_attack_mechanism"
    raise ValueError(f"Unexpected cohort: {cohort}")


def variant_mechanism(cohort, variant, family, benchmark):
    if variant == "clean":
        return "unmodified_clean"
    if variant == "benign":
        return ("arithmetic_identity" if cohort == "four_projects" else
                "equivalent_numeric_reexpression" if cohort == "native" else
                "equivalent_expression")
    if cohort == "four_projects":
        return "conditional_output_toggle" if variant == "toggle" else "conditional_output_suppression"
    if cohort == "external_authored":
        return ("readiness_suppression_after_false_start" if benchmark == "RS232-T2100"
                else "readiness_suppression_during_reception")
    if cohort == "test":
        return "unknown_original_attack_mechanism"
    return family


def assign_folds(records):
    by_owner = defaultdict(list)
    for row in records:
        if row["role"] == "development":
            by_owner[row["source_owner"]].append(row)
    strata = defaultdict(list)
    for owner, rows in by_owner.items():
        cohort_mechanisms = {(row["cohort"], row["mechanism_family"]) for row in rows}
        stratum = next(iter(cohort_mechanisms)) if len(cohort_mechanisms) == 1 else ("shared_owner", "mixed")
        strata[stratum].append(owner)
    counts = [Counter() for _ in range(FOLDS)]
    host_totals = [0] * FOLDS
    assignment = {}
    for stratum in sorted(strata, key=lambda value: (-len(strata[value]), value)):
        for owner in sorted(strata[stratum], key=stable_hash):
            target = min(range(FOLDS), key=lambda i: (counts[i][stratum], host_totals[i], i))
            assignment[owner] = target
            counts[target][stratum] += 1
            host_totals[target] += len({row["host"] for row in by_owner[owner]})
    development = [row for row in records if row["role"] == "development"]
    output = []
    for fold in range(FOLDS):
        test = [row for row in development if assignment[row["source_owner"]] == fold]
        train = [row for row in development if assignment[row["source_owner"]] != fold]
        test_hosts = {row["host"] for row in test}
        if test_hosts & {row["host"] for row in train}:
            raise ValueError("Host crosses a development fold")
        if {row["source_project"] for row in test} & {row["source_project"] for row in train}:
            raise ValueError("Source project crosses a development fold")
        if {row["source_owner"] for row in test} & {row["source_owner"] for row in train}:
            raise ValueError("Source owner crosses a development fold")
        if {row["label"] for row in test} != {0, 1}:
            raise ValueError("A development fold lacks a class")
        output.append(dict(fold=fold, train_hosts=sorted({row["host"] for row in train}),
                           test_hosts=sorted(test_hosts), test_keys=sorted(row["key"] for row in test),
                           test_labels=dict(Counter(str(row["label"]) for row in test)),
                           test_cohorts=dict(Counter(row["cohort"] for row in test))))
    if sorted(key for fold in output for key in fold["test_keys"]) != sorted(row["key"] for row in development):
        raise ValueError("Development records do not appear exactly once as validation")
    return output


def main():
    torch.set_num_threads(1)
    old_path = "data/training_audit_v3/manifest.json"
    semantic_path = "data/semantic_graph_v1/manifest.json"
    if (OUT / "protocol.json").exists():
        prior = json.loads((OUT / "protocol.json").read_text(encoding="utf-8"))
        for source, expected in prior["input_manifests"].items():
            if digest(ROOT / source) != expected:
                raise ValueError(f"Locked input manifest changed: {source}")
    old = read(old_path)["records"]
    semantic = {row["key"]: row for row in read(semantic_path)["records"]}
    if len(old) != 195 or len(semantic) != 195 or {row["key"] for row in old} != set(semantic):
        raise ValueError("The legacy and semantic manifests do not describe the same cohort")
    verified = read("data/semantic_graph_v1/verification.json")
    if verified.get("status") != "verified" or verified.get("graphs") != 195:
        raise ValueError("Semantic cohort verification is absent")
    baseline = read("data/overlap_six_v1/overlap.json")
    precision_rows = read("data/precision_v1/manifest.json")["records"]
    precision = defaultdict(dict)
    for row in precision_rows:
        precision[row["host"]][row["variant"]] = row
    screen = defaultdict(list)
    for row in read("data/precision_v1/screen_provenance.json")["records"]:
        screen[row["host"]].append(row)
    source_hash_cache = {}
    saved_model_view_mismatches = []
    records = []
    for index, row in enumerate(old, 1):
        partner = semantic[row["key"]]
        for field in ("host", "cohort", "variant", "label", "mapped_sha256", "chunks"):
            if row[field] != partner[field]:
                raise ValueError(f"Legacy/semantic {field} mismatch: {row['key']}")
        path = ROOT / row["file"]
        if digest(path) != row["sha256"]:
            raise ValueError(f"Prepared record hash mismatch: {row['key']}")
        item = torch.load(path, weights_only=False, map_location="cpu")
        graph = item["graph"]
        if (graph.num_nodes != row["nodes"] or len(item["rtl"]) != row["chunks"]
                or graph.x.shape[1] != 20 or item["label"] != row["label"]
                or item["host"] != row["host"]):
            raise ValueError(f"Prepared record metadata mismatch: {row['key']}")
        for source, expected in row["source_sha256"].items():
            if source not in source_hash_cache:
                source_hash_cache[source] = digest(ROOT / source)
            actual = source_hash_cache[source]
            if actual != expected:
                raise ValueError(f"Source hash mismatch: {source}")
        text_path = ROOT / "runs/training_audit_v3/prepared" / (row["key"] + ".v")
        text = sanitize(text_for(row))
        if hashlib.sha256(text.encode()).hexdigest() != row["sanitized_text_sha256"]:
            raise ValueError(f"Model-view text hash mismatch: {row['key']}")
        if text_path.read_text(encoding="utf-8") != text:
            saved_model_view_mismatches.append(row["key"])
        project, revision, family = project_metadata(row["host"], row["cohort"], baseline,
                                                     precision, screen)
        benchmark = item["benchmark"]
        role = "inspected_diagnostic" if row["cohort"] == "test" else "development"
        records.append(dict(key=row["key"], role=role, cohort=row["cohort"],
                            host=row["host"], benchmark=benchmark, variant=row["variant"],
                            label=row["label"], source_collection=("TinyTapeout" if row["cohort"] == "native"
                                                                      else "TrustHub" if row["cohort"] in ("test", "external_authored")
                                                                      else "pinned_open_source_project"),
                            source_project=project, source_owner=project.split("/")[0],
                            source_revision=revision, edit_generator=("precision_v1_native" if row["cohort"] == "native"
                                                                      else "overlap_six_v1" if row["cohort"] == "baseline"
                                                                      else "transfer_v1_conditional" if row["cohort"] == "four_projects"
                                                                      else "original_TrustHub"),
                            mechanism_family=family,
                            variant_mechanism=variant_mechanism(row["cohort"], row["variant"], family, benchmark),
                            synthesis_flow=FLOW[row["cohort"]],
                            legacy_nodes=graph.num_nodes, legacy_edges=graph.num_edges,
                            semantic_nodes=partner["nodes"], semantic_edges=partner["edges"],
                            rtl_chunks=row["chunks"], rtl_characters=len(text),
                            rtl_lines=len(text.splitlines()), source_file_count=len(row["source_sha256"]),
                            source_bundle_sha256=hashlib.sha256(json.dumps(row["source_sha256"], sort_keys=True).encode()).hexdigest(),
                            prepared_sha256=row["sha256"], semantic_sha256=partner["sha256"],
                            mapped_sha256=row["mapped_sha256"]))
        if index % 50 == 0:
            print(f"Verified {index}/{len(old)} records", flush=True)
    records.sort(key=lambda row: row["key"])
    folds = assign_folds(records)
    train = [row for row in records if row["role"] == "development"]
    diagnostic = [row for row in records if row["role"] == "inspected_diagnostic"]
    if len(train) != 185 or len(diagnostic) != 10 or {row["host"] for row in train} & {row["host"] for row in diagnostic}:
        raise ValueError("Unexpected development/diagnostic membership")
    owner_hosts = defaultdict(set)
    for row in train:
        owner_hosts[row["source_owner"]].add(row["host"])
    summary = dict(status="stage1_locked", training_records=len(train),
                   training_hosts=len({row["host"] for row in train}),
                   training_labels=dict(Counter(str(row["label"]) for row in train)),
                   training_cohorts=dict(Counter(row["cohort"] for row in train)),
                   native_mechanism_hosts=dict(Counter(row["mechanism_family"] for row in train
                                                       if row["cohort"] == "native" and row["variant"] == "clean")),
                   diagnostic_records=len(diagnostic),
                   diagnostic_hosts=sorted({row["host"] for row in diagnostic}),
                   undocumented_diagnostic_attack_records=sum(row["label"] == 1 and row["mechanism_family"].startswith("unknown")
                                                       for row in diagnostic),
                   training_legacy_node_range=[min(row["legacy_nodes"] for row in train),
                                               percentile([row["legacy_nodes"] for row in train], .5),
                                               max(row["legacy_nodes"] for row in train)],
                   training_rtl_chunk_range=[min(row["rtl_chunks"] for row in train),
                                             percentile([row["rtl_chunks"] for row in train], .5),
                                             max(row["rtl_chunks"] for row in train)],
                   diagnostic_chunk_max=max(row["rtl_chunks"] for row in diagnostic),
                   shared_source_owners={owner: sorted(hosts) for owner, hosts in owner_hosts.items()
                                         if len(hosts) > 1},
                   saved_model_view_mismatches=saved_model_view_mismatches,
                   final_test_records=0, source_files_hashed=len(source_hash_cache),
                   folds=[dict(fold=fold["fold"], test_hosts=len(fold["test_hosts"]),
                               test_records=len(fold["test_keys"]), test_labels=fold["test_labels"],
                               test_cohorts=fold["test_cohorts"]) for fold in folds])
    OUT.mkdir(parents=True, exist_ok=True)
    save(OUT / "records.json", records)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(records)
    csv_path = OUT / "records.csv"
    csv_payload = stream.getvalue().encode("utf-8")
    if csv_path.exists() and csv_path.read_bytes() != csv_payload:
        raise ValueError(f"Locked artifact would change: {csv_path}")
    csv_path.write_bytes(csv_payload)
    save(OUT / "folds.json", dict(seed=SEED, algorithm="source-owner grouped, cohort/mechanism stratified greedy balancing",
                                   development_keys_sha256=hashlib.sha256(json.dumps(sorted(row["key"] for row in train)).encode()).hexdigest(),
                                   folds=folds))
    save(OUT / "protocol.json", dict(status="locked_before_stage2", stage=1, seed=SEED,
                                      input_manifests={old_path: digest(ROOT / old_path),
                                                       semantic_path: digest(ROOT / semantic_path)},
                                      roles=dict(development="185 records / 60 hosts for model selection with source-owner-grouped folds",
                                                 inspected_diagnostic="10 PIC16F84/memctrl records; report only, never select model or threshold",
                                                 final_test="none admitted; source and lock new independent hosts before scoring"),
                                      reserved_project_candidates=read("experiments/transfer_v1/protocol.json")["reserved_project_candidates"],
                                      fold_file="data/dataset_stage1/folds.json",
                                      primary_development_metrics=["equal_host_auroc", "within_host_pair_ranking",
                                                                   "balanced_accuracy_at_training_selected_threshold",
                                                                   "balanced_log_loss"],
                                      controls=["graph_size", "rtl_length", "chunk_count", "graph_statistics", "gate_histogram"],
                                      inference_assumption="single suspect circuit; no clean reference at inference",
                                      final_test_policy="Freeze independent hosts, mechanisms, thresholds and scoring code before first final prediction."))
    save(OUT / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
