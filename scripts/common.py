"""Shared, dependency-free record loading and validation helpers."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCHEMA = ROOT / "schema" / "record.schema.json"

LEGAL_STATUSES = {
    "ALLEGATION", "DOCUMENTED_EVIDENCE", "UN_FINDING", "COURT_ALLEGATION",
    "COURT_INTERIM_FINDING", "COURT_FINAL_FINDING", "DISPUTED", "UNKNOWN",
}
REQUIRED = {
    "id", "title", "event_date", "publication_date", "location", "actors",
    "affected_population", "category", "summary", "claim", "legal_characterization",
    "legal_status", "evidence_type", "source_organization", "source_title",
    "source_url", "source_document_id", "source_page", "source_quote",
    "verification_notes", "related_records", "tags", "created_at", "updated_at",
}


def record_paths() -> list[Path]:
    return sorted(DATA.glob("*/*.json"))


def load_records() -> list[tuple[Path, dict]]:
    return [(path, json.loads(path.read_text(encoding="utf-8"))) for path in record_paths()]


def _date(value: object, timestamp: bool = False) -> bool:
    try:
        (datetime.fromisoformat(str(value).replace("Z", "+00:00")) if timestamp else date.fromisoformat(str(value)))
        return True
    except (TypeError, ValueError):
        return False


def validate(records: list[tuple[Path, dict]]) -> list[str]:
    errors: list[str] = []
    ids: dict[str, Path] = {}
    documents: dict[str, tuple[str, str, str]] = {}
    fingerprints: dict[tuple[str, str], str] = {}
    for path, record in records:
        label = str(path.relative_to(ROOT))
        missing = REQUIRED - record.keys()
        extra = record.keys() - REQUIRED
        if missing:
            errors.append(f"{label}: missing fields: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{label}: unknown fields: {', '.join(sorted(extra))}")
        for field in ("id", "title", "claim", "source_organization", "source_title", "source_url", "source_document_id", "verification_notes"):
            if not isinstance(record.get(field), str) or not record.get(field, "").strip():
                errors.append(f"{label}: {field} must be a non-empty string")
        rid = record.get("id")
        if rid in ids:
            errors.append(f"{label}: duplicate id {rid!r} (also {ids[rid].relative_to(ROOT)})")
        elif isinstance(rid, str):
            ids[rid] = path
        if path.stem != rid:
            errors.append(f"{label}: filename must match id")
        if record.get("legal_status") not in LEGAL_STATUSES:
            errors.append(f"{label}: invalid legal_status {record.get('legal_status')!r}")
        if not _date(record.get("publication_date")):
            errors.append(f"{label}: publication_date must be YYYY-MM-DD")
        if record.get("event_date") is not None and not _date(record.get("event_date")):
            errors.append(f"{label}: event_date must be YYYY-MM-DD or null")
        for field in ("created_at", "updated_at"):
            if not _date(record.get(field), timestamp=True):
                errors.append(f"{label}: {field} must be an ISO 8601 timestamp")
        parsed = urlparse(record.get("source_url", ""))
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{label}: source_url must be an absolute HTTPS URL")
        for field in ("location", "actors", "affected_population", "evidence_type", "related_records", "tags"):
            value = record.get(field)
            if not isinstance(value, list):
                errors.append(f"{label}: {field} must be an array")
            elif len(value) != len(set(value)):
                errors.append(f"{label}: {field} contains duplicates")
        doc_id = record.get("source_document_id")
        metadata = (record.get("source_organization", ""), record.get("source_title", ""), record.get("source_url", ""))
        if doc_id in documents and documents[doc_id] != metadata:
            errors.append(f"{label}: source document {doc_id!r} has conflicting metadata")
        elif isinstance(doc_id, str):
            documents[doc_id] = metadata
        fingerprint = (str(doc_id), record.get("claim", "").casefold().strip())
        if fingerprint in fingerprints:
            errors.append(f"{label}: duplicate source-document claim (also {fingerprints[fingerprint]})")
        else:
            fingerprints[fingerprint] = label
    known = set(ids)
    for path, record in records:
        for related in record.get("related_records", []):
            if related not in known:
                errors.append(f"{path.relative_to(ROOT)}: unknown related record {related!r}")
    return errors
