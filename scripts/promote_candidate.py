#!/usr/bin/env python3
"""Human-gated promotion of one VERIFIED candidate into the public ledger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import ROOT, validate
from review_pipeline import canonical_json, normalize_claim, source_metadata


class PromotionError(ValueError):
    pass


def promote(candidate_path: Path, *, root: Path = ROOT, approve: bool = False) -> Path:
    if not approve:
        raise PromotionError("promotion requires explicit --approve")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
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
    loaded = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((root / "data").glob("*/*.json"))]
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
