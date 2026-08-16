"""Shared, dependency-free record loading and validation helpers."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCHEMA = ROOT / "schema" / "record.schema.json"


STRICT_FORMATS = FormatChecker()


@STRICT_FORMATS.checks("date")
def _is_date(value: object) -> bool:
    if not isinstance(value, str):
        return True  # JSON Schema's type keyword reports non-string values.
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


@STRICT_FORMATS.checks("date-time")
def _is_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return "T" in value and parsed.tzinfo is not None
    except ValueError:
        return False


@STRICT_FORMATS.checks("uri")
def _is_uri(value: object) -> bool:
    if not isinstance(value, str):
        return True
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc and not any(character.isspace() for character in value))

def record_paths() -> list[Path]:
    return sorted(DATA.glob("*/*.json"))


def load_records() -> list[tuple[Path, dict]]:
    return [(path, json.loads(path.read_text(encoding="utf-8"))) for path in record_paths()]


def schema_validator() -> Draft202012Validator:
    """Return a validator built from the repository's authoritative contract."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=STRICT_FORMATS)


def _error_path(error: object) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "<record>"


def validate(records: list[tuple[Path, dict]]) -> list[str]:
    errors: list[str] = []
    validator = schema_validator()
    ids: dict[str, Path] = {}
    documents: dict[str, tuple[str, str, str]] = {}
    fingerprints: dict[tuple[str, str], str] = {}
    for path, record in records:
        label = str(path.relative_to(ROOT))
        schema_errors = sorted(
            validator.iter_errors(record),
            key=lambda error: (list(error.absolute_path), error.message),
        )
        errors.extend(f"{label}: {_error_path(error)}: {error.message}" for error in schema_errors)
        rid = record.get("id")
        if rid in ids:
            errors.append(f"{label}: duplicate id {rid!r} (also {ids[rid].relative_to(ROOT)})")
        elif isinstance(rid, str):
            ids[rid] = path
        if path.stem != rid:
            errors.append(f"{label}: filename must match id")
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
