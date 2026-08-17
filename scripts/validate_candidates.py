#!/usr/bin/env python3
"""Validate review queues without treating candidates as evidence."""
from __future__ import annotations

import json
from collections import Counter

from common import ROOT, schema_validator
from review_pipeline import (CANDIDATES, DOCUMENTS, candidate_id, document_id,
                             load_json_files, normalize_claim, overlap_flags,
                             published_indexes, source_metadata, validator)


def error_path(error) -> str:
    return ".".join(map(str, error.absolute_path)) or "<item>"


def validate_review(root=ROOT) -> list[str]:
    errors: list[str] = []
    candidates_dir, documents_dir = root / "review/candidates", root / "review/documents"
    registry_path = root / "sources/registry.json"
    schema_dir = root / "schema"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_validator = validator(schema_dir / "source-registry.schema.json")
    for error in sorted(registry_validator.iter_errors(registry), key=lambda e: list(e.absolute_path)):
        errors.append(f"sources/registry.json: {error_path(error)}: {error.message}")
    registry_ids = [entry.get("id") for entry in registry]
    if len(registry_ids) != len(set(registry_ids)):
        errors.append("sources/registry.json: duplicate registry id")
    organizations = {entry.get("id"): entry.get("organization") for entry in registry}

    documents = load_json_files(documents_dir)
    doc_validator = validator(schema_dir / "discovered-document.schema.json")
    queued_doc_ids: dict[str, str] = {}
    document_metadata: dict[str, tuple[str, str, str, str]] = {}
    for path, document in documents:
        label = str(path.relative_to(root))
        for error in doc_validator.iter_errors(document):
            errors.append(f"{label}: {error_path(error)}: {error.message}")
        if path.stem != document.get("id"):
            errors.append(f"{label}: filename must match id")
        expected_id = document_id(document.get("source_registry_id", ""), document.get("source_document_id", ""), document.get("source_url", ""))
        if document.get("id") != expected_id:
            errors.append(f"{label}: document id is not the deterministic source fingerprint")
        source_id = document.get("source_document_id")
        if source_id in queued_doc_ids:
            errors.append(f"{label}: duplicate queued source_document_id {source_id!r}")
        queued_doc_ids[source_id] = label
        registry_id = document.get("source_registry_id")
        if registry_id not in organizations:
            errors.append(f"{label}: unknown source_registry_id {registry_id!r}")
        elif document.get("source_organization") != organizations[registry_id]:
            errors.append(f"{label}: source organization disagrees with registry")
        document_metadata[source_id] = (document.get("source_organization", ""), document.get("title", ""), document.get("source_url", ""), document.get("publication_date", ""))

    published, published_documents = published_indexes([
        (path, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((root / "data").glob("*/*.json"))
    ])
    for source_id, label in queued_doc_ids.items():
        if source_id in published_documents and document_metadata[source_id] != published_documents[source_id]:
            errors.append(f"{label}: queued and published source metadata are inconsistent")
    candidate_validator = validator(schema_dir / "candidate.schema.json")
    record_validator = schema_validator() if root == ROOT else validator(schema_dir / "record.schema.json")
    seen_ids, fingerprints = {}, {}
    for path, candidate in load_json_files(candidates_dir):
        label = str(path.relative_to(root))
        # Validate the embedded final record separately, avoiding ambiguous publication semantics.
        candidate_for_schema = dict(candidate)
        proposed_record = candidate_for_schema.get("proposed_record")
        candidate_for_schema["proposed_record"] = None
        for error in candidate_validator.iter_errors(candidate_for_schema):
            errors.append(f"{label}: {error_path(error)}: {error.message}")
        if proposed_record is not None:
            for error in record_validator.iter_errors(proposed_record):
                errors.append(f"{label}: proposed_record.{error_path(error)}: {error.message}")
        cid = candidate.get("id")
        if path.stem != cid:
            errors.append(f"{label}: filename must match id")
        if cid != candidate_id(candidate.get("source_document_id", ""), candidate.get("proposed_claim", "")):
            errors.append(f"{label}: candidate id is not the deterministic source/claim fingerprint")
        if cid in seen_ids:
            errors.append(f"{label}: duplicate candidate id {cid!r}")
        seen_ids[cid] = label
        fingerprint = normalize_claim(candidate.get("proposed_claim", ""))
        if fingerprint in fingerprints:
            errors.append(f"{label}: duplicate proposed claim (also {fingerprints[fingerprint]})")
        fingerprints[fingerprint] = label
        source_id = candidate.get("source_document_id")
        expected = document_metadata.get(source_id) or published_documents.get(source_id)
        if expected is None:
            errors.append(f"{label}: source_document_id is not queued or published")
        elif source_metadata(candidate) != expected:
            errors.append(f"{label}: source metadata is inconsistent")
        for rid in candidate.get("related_published_records", []):
            if rid not in published:
                errors.append(f"{label}: unknown related published record {rid!r}")
        status = candidate.get("review_status")
        if status == "VERIFIED" and not all(candidate.get(k) for k in ("reviewed_at", "reviewed_by", "review_notes")):
            errors.append(f"{label}: VERIFIED requires reviewed_at, reviewed_by, and review_notes")
        if status == "REJECTED" and not candidate.get("review_notes"):
            errors.append(f"{label}: REJECTED requires review_notes")
        if status == "PUBLISHED":
            rid = candidate.get("published_record_id")
            if rid not in published:
                errors.append(f"{label}: PUBLISHED must identify an actual published record")
        elif candidate.get("published_record_id") is not None:
            errors.append(f"{label}: only PUBLISHED may set published_record_id")
        if status in ("CANDIDATE", "NEEDS_REVIEW") and any(candidate.get(k) for k in ("reviewed_at", "reviewed_by")):
            errors.append(f"{label}: unreviewed candidate cannot carry human verification metadata")
        if status != "PUBLISHED" and overlap_flags(candidate, published) and "PUBLISHED_OVERLAP_REVIEW" not in candidate.get("review_flags", []):
            errors.append(f"{label}: published overlap must be flagged for review")
    return errors


def write_summary() -> None:
    docs = [item for _, item in load_json_files(DOCUMENTS)]
    candidates = [item for _, item in load_json_files(CANDIDATES)]
    counts = Counter(item["review_status"] for item in candidates)
    lines = ["# Internal review summary", "", "> Candidate claims are provisional and are not public ledger evidence.", "",
             f"- Newly discovered documents: {sum(x['status'] == 'NEW' for x in docs)}",
             f"- Candidates: {counts['CANDIDATE']}", f"- Needs review: {counts['NEEDS_REVIEW']}",
             f"- Verified: {counts['VERIFIED']}", f"- Rejected: {counts['REJECTED']}", f"- Published: {counts['PUBLISHED']}", "", "## Flagged candidates", ""]
    flagged = sorted((x for x in candidates if x["review_flags"]), key=lambda x: x["id"])
    lines.extend(f"- `{x['id']}`: {', '.join(x['review_flags'])}" for x in flagged)
    if not flagged:
        lines.append("None.")
    (ROOT / "review/summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    errors = validate_review()
    if errors:
        print("Candidate validation failed:\n" + "\n".join(f"- {x}" for x in errors))
        return 1
    write_summary()
    print(f"Validated {len(load_json_files(DOCUMENTS))} discovered documents and {len(load_json_files(CANDIDATES))} candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
