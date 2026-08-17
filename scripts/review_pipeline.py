"""Shared deterministic helpers for the private review pipeline."""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from jsonschema import Draft202012Validator

from common import ROOT, STRICT_FORMATS, load_records

REVIEW = ROOT / "review"
CANDIDATES = REVIEW / "candidates"
DOCUMENTS = REVIEW / "documents"
REGISTRY = ROOT / "sources" / "registry.json"
CANDIDATE_SCHEMA = ROOT / "schema" / "candidate.schema.json"
DOCUMENT_SCHEMA = ROOT / "schema" / "discovered-document.schema.json"
REGISTRY_SCHEMA = ROOT / "schema" / "source-registry.schema.json"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def normalize_claim(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", value.casefold()).split())


def stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(normalize_claim(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(material.encode()).hexdigest()[:16]}"


def document_id(source_registry_id: str, source_document_id: str, source_url: str) -> str:
    return stable_id("document", source_registry_id, source_document_id, source_url)


def candidate_id(source_document_id: str, claim: str) -> str:
    return stable_id("candidate", source_document_id, claim)


def json_paths(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.json"))


def load_json_files(directory: Path) -> list[tuple[Path, dict]]:
    return [(path, json.loads(path.read_text(encoding="utf-8"))) for path in json_paths(directory)]


def validator(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=STRICT_FORMATS)


def source_metadata(record: dict) -> tuple[str, str, str, str]:
    return tuple(record.get(key, "") for key in ("source_organization", "source_title", "source_url", "publication_date"))


def published_indexes(records=None) -> tuple[dict[str, dict], dict[str, tuple[str, str, str, str]]]:
    records = load_records() if records is None else records
    by_id = {record["id"]: record for _, record in records}
    documents = {record["source_document_id"]: source_metadata(record) for _, record in records}
    return by_id, documents


def procedural_flags(candidate: dict) -> list[str]:
    text = " ".join(str(candidate.get(k) or "") for k in
                    ("source_organization", "source_title", "proposed_claim", "proposed_legal_status", "extraction_notes")).casefold()
    flags = set()
    if "icc" in text or "international criminal court" in text:
        if any(x in text for x in ("warrant", "charge", "reasonable grounds", "court_allegation")):
            flags.add("COURT_ALLEGATION_REVIEW")
    if "provisional measure" in text or "court_interim_finding" in text or "advisory opinion" in text:
        flags.add("INTERIM_VS_FINAL_REVIEW")
    if "commission of inquiry" in text or "special rapporteur" in text or "un_finding" in text:
        flags.add("UN_FINDING_SCOPE_REVIEW")
    if any(x in text for x in ("terminated", "vacated", "withdrawn", "later proceeding")):
        flags.add("LATER_PROCEDURAL_POSTURE_REVIEW")
    if any(x in text for x in ("alleged", "according to", "reported by", "quoted allegation")):
        flags.add("ATTRIBUTION_REVIEW")
    return sorted(flags)


def overlap_flags(candidate: dict, published: dict[str, dict]) -> list[str]:
    flags = set()
    claim = normalize_claim(candidate.get("proposed_claim", ""))
    represented = set(candidate.get("related_published_records", []))
    for rid, record in published.items():
        other = normalize_claim(record.get("claim", ""))
        if claim == other or rid in represented:
            flags.add("PUBLISHED_OVERLAP_REVIEW")
        elif candidate.get("source_document_id") == record.get("source_document_id") and SequenceMatcher(None, claim, other).ratio() >= .9:
            flags.add("PUBLISHED_OVERLAP_REVIEW")
    return sorted(flags)


def known_document_ids(root: Path = ROOT) -> set[str]:
    values = set()
    for path in sorted((root / "data").glob("*/*.json")) + sorted((root / "review/documents").glob("*.json")) + sorted((root / "review/candidates").glob("*.json")):
        values.add(json.loads(path.read_text(encoding="utf-8")).get("source_document_id"))
    return values - {None}


def write_sorted(directory: Path, item: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{item['id']}.json"
    path.write_text(canonical_json(item), encoding="utf-8")
    return path
