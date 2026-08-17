#!/usr/bin/env python3
"""Local-only browser UI for human review of provisional candidates."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from common import ROOT
from review_pipeline import candidate_id, canonical_json, load_json_files, validator
from validate_candidates import validate_review

HOST = "127.0.0.1"
STATIC_ROOT = ROOT / "review_ui"
STATUS_ORDER = {"NEEDS_REVIEW": 0, "CANDIDATE": 1, "VERIFIED": 2, "REJECTED": 3, "PUBLISHED": 4}
EDITABLE_CANDIDATE_FIELDS = {
    "proposed_event_date", "proposed_category", "proposed_claim", "proposed_legal_status",
    "supporting_passage", "source_page", "extraction_notes", "related_published_records",
    "review_flags", "review_notes",
}
RECORD_SENSITIVE_CANDIDATE_FIELDS = {
    "proposed_event_date", "proposed_category", "proposed_claim", "proposed_legal_status",
    "source_page", "related_published_records",
}
RECORD_EDIT_FIELDS = {
    "id", "title", "location", "actors", "affected_population", "summary",
    "legal_characterization", "evidence_type", "source_quote", "verification_notes", "tags",
}


class ReviewUIError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def schema_error(error) -> str:
    path = ".".join(map(str, error.absolute_path)) or "<item>"
    return f"{path}: {error.message}"


def split_csv(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").replace("\n", ",").split(",") if item.strip()]


class ReviewStore:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.candidates_dir = root / "review/candidates"
        self.candidate_validator = validator(root / "schema/candidate.schema.json")
        self.record_validator = validator(root / "schema/record.schema.json")

    def _published(self) -> dict[str, dict]:
        return {
            item["id"]: item
            for path in sorted((self.root / "data").glob("*/*.json"))
            for item in [json.loads(path.read_text(encoding="utf-8"))]
        }

    def _candidate_path(self, candidate_id_value: str) -> Path:
        if not candidate_id_value.startswith("candidate-") or "/" in candidate_id_value or "\\" in candidate_id_value:
            raise ReviewUIError("invalid candidate id")
        path = self.candidates_dir / f"{candidate_id_value}.json"
        if not path.is_file():
            raise ReviewUIError("candidate not found")
        return path

    def get(self, candidate_id_value: str) -> dict:
        return json.loads(self._candidate_path(candidate_id_value).read_text(encoding="utf-8"))

    def list(self) -> list[dict]:
        rows = []
        for _, candidate in load_json_files(self.candidates_dir):
            rows.append({
                "id": candidate["id"],
                "status": candidate["review_status"],
                "claim": candidate["proposed_claim"],
                "source_organization": candidate["source_organization"],
                "source_document_id": candidate["source_document_id"],
                "flags": candidate["review_flags"],
            })
        return sorted(rows, key=lambda item: (STATUS_ORDER.get(item["status"], 99), item["id"]))

    def detail(self, candidate_id_value: str) -> dict:
        candidate = self.get(candidate_id_value)
        published = self._published()
        related = [
            {"id": rid, "title": published[rid]["title"], "claim": published[rid]["claim"]}
            for rid in candidate.get("related_published_records", []) if rid in published
        ]
        record = candidate.get("proposed_record")
        return {
            "candidate": candidate,
            "related_records": related,
            "record_fields": self._record_fields(record),
        }

    @staticmethod
    def _record_fields(record: dict | None) -> dict:
        if not record:
            return {
                "id": "", "title": "", "location": [], "actors": [], "affected_population": [],
                "summary": "", "legal_characterization": "", "evidence_type": [], "source_quote": None,
                "verification_notes": "", "tags": [],
            }
        return {key: record.get(key) for key in RECORD_EDIT_FIELDS}

    def config(self) -> dict:
        record_schema = json.loads((self.root / "schema/record.schema.json").read_text(encoding="utf-8"))
        candidate_schema = json.loads((self.root / "schema/candidate.schema.json").read_text(encoding="utf-8"))
        return {
            "categories": candidate_schema["properties"]["proposed_category"]["enum"],
            "legal_statuses": candidate_schema["properties"]["proposed_legal_status"]["enum"],
            "review_flags": candidate_schema["properties"]["review_flags"]["items"]["enum"],
            "evidence_types": record_schema["properties"]["evidence_type"]["items"]["enum"],
        }

    def update(self, candidate_id_value: str, payload: dict) -> dict:
        action = payload.get("action", "save")
        if action not in {"save", "needs_review", "reopen", "reject", "verify"}:
            raise ReviewUIError("unsupported review action")

        old_path = self._candidate_path(candidate_id_value)
        old_bytes = old_path.read_bytes()
        candidate = json.loads(old_bytes.decode("utf-8"))
        status = candidate.get("review_status")
        if status == "PUBLISHED":
            raise ReviewUIError("published candidates are read-only in the review UI")
        if status in {"VERIFIED", "REJECTED"} and action not in {"reopen"}:
            raise ReviewUIError(f"{status.lower()} candidate must be reopened before editing")

        if action == "reopen":
            candidate["review_status"] = "NEEDS_REVIEW"
            candidate["reviewed_at"] = None
            candidate["reviewed_by"] = None
            candidate["review_notes"] = payload.get("review_notes") or candidate.get("review_notes")
            return self._commit(old_path, old_bytes, candidate)

        record_sensitive_before = {key: candidate.get(key) for key in RECORD_SENSITIVE_CANDIDATE_FIELDS}
        fields = payload.get("candidate", {})
        if not isinstance(fields, dict):
            raise ReviewUIError("candidate fields must be an object")
        for key in EDITABLE_CANDIDATE_FIELDS:
            if key in fields:
                candidate[key] = fields[key]
        candidate["related_published_records"] = split_csv(candidate.get("related_published_records", []))
        candidate["review_flags"] = split_csv(candidate.get("review_flags", []))
        if candidate.get("proposed_record") is not None and any(
            candidate.get(key) != record_sensitive_before[key] for key in RECORD_SENSITIVE_CANDIDATE_FIELDS
        ):
            candidate["proposed_record"] = None

        new_id = candidate_id(candidate["source_document_id"], candidate["proposed_claim"])
        candidate["id"] = new_id

        reviewer = str(payload.get("reviewer") or "").strip()
        notes = str(payload.get("review_notes") or candidate.get("review_notes") or "").strip()

        if action in {"save", "needs_review"}:
            candidate["review_status"] = "NEEDS_REVIEW" if action == "needs_review" else candidate["review_status"]
            candidate["reviewed_at"] = None
            candidate["reviewed_by"] = None
            candidate["review_notes"] = notes or None
        elif action == "reject":
            if not reviewer:
                raise ReviewUIError("reviewer is required to reject a candidate")
            if not notes:
                raise ReviewUIError("review notes are required to reject a candidate")
            candidate["review_status"] = "REJECTED"
            candidate["reviewed_at"] = utc_now()
            candidate["reviewed_by"] = reviewer
            candidate["review_notes"] = notes
        elif action == "verify":
            if not reviewer:
                raise ReviewUIError("reviewer is required to verify a candidate")
            if not notes:
                raise ReviewUIError("substantive review notes are required to verify a candidate")
            record_fields = payload.get("record")
            if not isinstance(record_fields, dict):
                raise ReviewUIError("final record fields are required to verify a candidate")
            now = utc_now()
            candidate["proposed_record"] = self._build_record(candidate, record_fields, now)
            candidate["review_status"] = "VERIFIED"
            candidate["reviewed_at"] = now
            candidate["reviewed_by"] = reviewer
            candidate["review_notes"] = notes

        new_path = self.candidates_dir / f"{new_id}.json"
        if new_path != old_path and new_path.exists():
            raise ReviewUIError(f"rewritten claim collides with existing candidate {new_id}")
        return self._commit(old_path, old_bytes, candidate, new_path=new_path)

    def _build_record(self, candidate: dict, fields: dict, now: str) -> dict:
        clean = {key: fields.get(key) for key in RECORD_EDIT_FIELDS}
        for key in ("location", "actors", "affected_population", "evidence_type", "tags"):
            clean[key] = split_csv(clean.get(key))
        source_quote = clean.get("source_quote")
        clean["source_quote"] = str(source_quote).strip() if source_quote not in (None, "") else None
        record = {
            "id": str(clean.get("id") or "").strip(),
            "title": str(clean.get("title") or "").strip(),
            "event_date": candidate.get("proposed_event_date"),
            "publication_date": candidate["publication_date"],
            "location": clean["location"],
            "actors": clean["actors"],
            "affected_population": clean["affected_population"],
            "category": candidate["proposed_category"],
            "summary": str(clean.get("summary") or "").strip(),
            "claim": candidate["proposed_claim"],
            "legal_characterization": str(clean.get("legal_characterization") or "").strip(),
            "legal_status": candidate["proposed_legal_status"],
            "evidence_type": clean["evidence_type"],
            "source_organization": candidate["source_organization"],
            "source_title": candidate["source_title"],
            "source_url": candidate["source_url"],
            "source_document_id": candidate["source_document_id"],
            "source_page": candidate.get("source_page"),
            "source_quote": clean["source_quote"],
            "verification_notes": str(clean.get("verification_notes") or "").strip(),
            "related_records": list(candidate.get("related_published_records", [])),
            "tags": clean["tags"],
            "created_at": now,
            "updated_at": now,
        }
        errors = sorted(self.record_validator.iter_errors(record), key=lambda error: (list(error.absolute_path), error.message))
        if errors:
            raise ReviewUIError("final record is incomplete or invalid: " + "; ".join(schema_error(error) for error in errors))
        return record

    def _validate_candidate(self, candidate: dict) -> None:
        errors = sorted(self.candidate_validator.iter_errors(candidate), key=lambda error: (list(error.absolute_path), error.message))
        if errors:
            raise ReviewUIError("candidate is invalid: " + "; ".join(schema_error(error) for error in errors))
        expected_id = candidate_id(candidate["source_document_id"], candidate["proposed_claim"])
        if candidate["id"] != expected_id:
            raise ReviewUIError("candidate id does not match the source/claim fingerprint")

    def _commit(self, old_path: Path, old_bytes: bytes, candidate: dict, *, new_path: Path | None = None) -> dict:
        self._validate_candidate(candidate)
        new_path = new_path or old_path
        new_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = new_path.with_name(new_path.name + ".tmp")
        temp_path.write_text(canonical_json(candidate), encoding="utf-8")
        os.replace(temp_path, new_path)
        if new_path != old_path:
            old_path.unlink()
        errors = validate_review(self.root)
        if errors:
            if new_path.exists():
                new_path.unlink()
            old_path.write_bytes(old_bytes)
            raise ReviewUIError("review validation failed; no changes saved: " + "; ".join(errors))
        return self.detail(candidate["id"])


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "OpenEvidenceReview/1.0"

    @property
    def app(self):
        return self.server.app

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0]
        return host == HOST

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self._json({"error": message}, status)

    def _static(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._host_allowed():
            self._error("invalid host", HTTPStatus.FORBIDDEN)
            return
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/session":
            self._json({"csrf_token": self.app["token"]})
            return
        if path == "/api/config":
            self._json(self.app["store"].config())
            return
        if path == "/api/candidates":
            self._json({"candidates": self.app["store"].list()})
            return
        if path.startswith("/api/candidates/"):
            candidate_id_value = unquote(path.removeprefix("/api/candidates/"))
            try:
                self._json(self.app["store"].detail(candidate_id_value))
            except ReviewUIError as exc:
                self._error(str(exc), HTTPStatus.NOT_FOUND)
            return
        if path in {"/", "/index.html"}:
            self._static(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self._static(STATIC_ROOT / "app.js", "text/javascript; charset=utf-8")
            return
        if path == "/style.css":
            self._static(STATIC_ROOT / "style.css", "text/css; charset=utf-8")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._host_allowed():
            self._error("invalid host", HTTPStatus.FORBIDDEN)
            return
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/candidates/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ReviewUIError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not secrets.compare_digest(str(payload.pop("csrf_token", "")), self.app["token"]):
                self._error("invalid session token", HTTPStatus.FORBIDDEN)
                return
            candidate_id_value = unquote(parsed.path.removeprefix("/api/candidates/"))
            result = self.app["store"].update(candidate_id_value, payload)
            self._json(result)
        except (ReviewUIError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._error(str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    if not STATIC_ROOT.is_dir():
        parser.error(f"missing local UI assets at {STATIC_ROOT}")

    store = ReviewStore(ROOT)
    existing_errors = validate_review(ROOT)
    if existing_errors:
        parser.error("review queue is invalid; run scripts/validate_candidates.py first")

    server = ThreadingHTTPServer((HOST, args.port), ReviewHandler)
    server.app = {"store": store, "token": secrets.token_urlsafe(32)}
    url = f"http://{HOST}:{args.port}/"
    print(f"Open Evidence Ledger reviewer: {url}")
    print("Local only. This UI cannot promote or publish candidates.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping reviewer.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
