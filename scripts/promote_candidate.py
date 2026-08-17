#!/usr/bin/env python3
"""Human-gated promotion of one VERIFIED candidate into the public ledger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import ROOT, validate
from review_pipeline import (candidate_id, canonical_json, document_id, normalize_claim,
                             source_metadata, validator)


class PromotionError(ValueError):
    pass


def promote(candidate_path: Path, *, root: Path = ROOT, approve: bool = False) -> Path:
    if not approve:
        raise PromotionError("promotion requires explicit --approve")
    root = root.resolve()
    queue = (root / "review/candidates").resolve()
    try:
        resolved_candidate = candidate_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PromotionError("candidate file does not exist") from exc
    if resolved_candidate.parent != queue:
        raise PromotionError("candidate must be a queued file directly inside review/candidates")
    candidate_path = resolved_candidate
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PromotionError("candidate is not valid readable JSON") from exc
    candidate_schema = root / "schema/candidate.schema.json"
    schema_errors = sorted(validator(candidate_schema).iter_errors(candidate), key=lambda error: (list(error.absolute_path), error.message))
    if schema_errors:
        raise PromotionError("candidate schema validation failed: " + "; ".join(error.message for error in schema_errors))
    expected_id = candidate_id(candidate["source_document_id"], candidate["proposed_claim"])
    if candidate["id"] != expected_id or candidate_path.stem != expected_id:
        raise PromotionError("candidate id and filename must match the deterministic source/claim fingerprint")
    expected_source = source_metadata(candidate)
    provenance_valid = False
    document_schema = validator(root / "schema/discovered-document.schema.json")
    for path in sorted((root / "review/documents").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("source_document_id") != candidate["source_document_id"]:
            continue
        valid_id = document.get("id") == document_id(document.get("source_registry_id", ""), document.get("source_document_id", ""), document.get("source_url", ""))
        metadata = (document.get("source_organization"), document.get("title"), document.get("source_url"), document.get("publication_date"))
        provenance_valid = not list(document_schema.iter_errors(document)) and path.stem == document.get("id") and valid_id and metadata == expected_source
        break
    existing_records = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((root / "data").glob("*/*.json"))]
    if not provenance_valid:
        provenance_valid = any(item.get("source_document_id") == candidate["source_document_id"] and source_metadata(item) == expected_source for _, item in existing_records)
    if not provenance_valid:
        raise PromotionError("candidate source_document_id has no valid, metadata-consistent pipeline provenance")
    if candidate.get("review_status") != "VERIFIED":
        raise PromotionError("candidate must have review_status VERIFIED")
    if not all(candidate.get(key) for key in ("reviewed_by", "reviewed_at", "review_notes")):
        raise PromotionError("VERIFIED candidate requires reviewer, review time, and review notes")
    record = candidate.get("proposed_record")
    if not isinstance(record, dict):
        raise PromotionError("a complete proposed_record is required; promotion does not invent fields")
    expected = (candidate["source_organization"], candidate["source_title"], candidate["source_url"], candidate["publication_date"])
    if source_metadata(record) != expected or record.get("source_document_id") != candidate.get("source_document_id"):
        raise PromotionError("candidate and final record source metadata are inconsistent")
    if record.get("claim") != candidate.get("proposed_claim") or record.get("category") != candidate.get("proposed_category") or record.get("legal_status") != candidate.get("proposed_legal_status"):
        raise PromotionError("final claim, category, and legal status must equal the human-reviewed proposals")
    loaded = existing_records
    ids = {item["id"] for _, item in loaded}
    if record.get("id") in ids:
        raise PromotionError("published record id already exists")
    if any(normalize_claim(item["claim"]) == normalize_claim(record["claim"]) for _, item in loaded):
        raise PromotionError("proposed claim duplicates a published claim")
    if any(rid not in ids for rid in candidate.get("related_published_records", [])):
        raise PromotionError("candidate references an unknown published record")
    if sorted(record.get("related_records", [])) != sorted(candidate.get("related_published_records", [])):
        raise PromotionError("final related_records must equal reviewed related_published_records")
    destination = root / "data" / record["category"] / f"{record['id']}.json"
    prospective = loaded + [(destination, record)]
    # common.validate uses repository-relative labels; schema and invariants are still authoritative.
    errors = validate(prospective, root=root)
    if errors:
        raise PromotionError("published-record validation failed: " + "; ".join(errors))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    candidate["review_status"] = "PUBLISHED"
    candidate["published_record_id"] = record["id"]
    candidate_path.write_text(canonical_json(candidate), encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--approve", action="store_true", help="confirm intentional human-reviewed publication")
    args = parser.parse_args()
    try:
        destination = promote(args.candidate, approve=args.approve)
    except PromotionError as exc:
        parser.error(str(exc))
    print(f"Published {destination.relative_to(ROOT)} and retained candidate provenance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
