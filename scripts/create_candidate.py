#!/usr/bin/env python3
"""Create a provisional candidate from an already reviewed queued document."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from common import ROOT
from review_pipeline import candidate_id, canonical_json, load_json_files, procedural_flags


def build_candidate(document: dict, *, claim: str, legal_status: str, category: str,
                    passage: str | None, page: str | None, notes: str, created_at: str) -> dict:
    candidate = {
        "id": candidate_id(document["source_document_id"], claim),
        "source_document_id": document["source_document_id"], "source_organization": document["source_organization"],
        "source_title": document["title"], "source_url": document["source_url"], "publication_date": document["publication_date"],
        "proposed_event_date": None, "proposed_category": category, "proposed_claim": claim,
        "proposed_legal_status": legal_status, "supporting_passage": passage, "source_page": page,
        "extraction_notes": notes, "related_published_records": [], "review_status": "CANDIDATE",
        "review_flags": [], "created_at": created_at, "reviewed_at": None, "reviewed_by": None,
        "review_notes": None, "proposed_record": None, "published_record_id": None,
    }
    candidate["review_flags"] = procedural_flags(candidate)
    return candidate


def create_candidate(document_path, *, root=ROOT, claim: str, legal_status: str, category: str,
                     passage: str | None, page: str | None, notes: str, created_at: str):
    """Create once, then advance the source document without losing provenance."""
    document = json.loads(document_path.read_text(encoding="utf-8"))
    if document.get("status") not in ("REVIEWED", "CANDIDATES_CREATED"):
        raise ValueError("source document must have status REVIEWED or CANDIDATES_CREATED")
    candidate = build_candidate(document, claim=claim, legal_status=legal_status, category=category,
                                passage=passage, page=page, notes=notes, created_at=created_at)
    path = root / "review/candidates" / f"{candidate['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(canonical_json(candidate))
    except FileExistsError as exc:
        raise ValueError(f"candidate already exists and will not be overwritten: {path.name}") from exc
    if document["status"] == "REVIEWED":
        document["status"] = "CANDIDATES_CREATED"
        document_path.write_text(canonical_json(document), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_document_id")
    parser.add_argument("--claim", required=True); parser.add_argument("--legal-status", required=True)
    parser.add_argument("--category", required=True); parser.add_argument("--passage")
    parser.add_argument("--source-page"); parser.add_argument("--extraction-notes", required=True)
    args = parser.parse_args()
    matches = [(p, d) for p, d in load_json_files(ROOT / "review/documents") if d["source_document_id"] == args.source_document_id]
    if len(matches) != 1 or matches[0][1]["status"] not in ("REVIEWED", "CANDIDATES_CREATED"):
        parser.error("source document must exist exactly once and have status REVIEWED or CANDIDATES_CREATED")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        path = create_candidate(matches[0][0], claim=args.claim, legal_status=args.legal_status, category=args.category,
                                passage=args.passage, page=args.source_page, notes=args.extraction_notes, created_at=now)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Created provisional candidate {path.relative_to(ROOT)}; human verification is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
