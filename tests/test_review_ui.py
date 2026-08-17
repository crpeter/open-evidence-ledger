"""Tests for the local-only human review UI state layer."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review_pipeline import candidate_id, canonical_json, document_id  # noqa: E402
from review_ui import ReviewStore, ReviewUIError  # noqa: E402
from validate_candidates import validate_review  # noqa: E402


class ReviewUITests(unittest.TestCase):
    def prepare_root(self, root: Path) -> tuple[ReviewStore, Path]:
        (root / "data").mkdir()
        (root / "review/candidates").mkdir(parents=True)
        (root / "review/documents").mkdir()
        shutil.copytree(ROOT / "schema", root / "schema")
        shutil.copytree(ROOT / "sources", root / "sources")

        document = {
            "id": "",
            "source_registry_id": "un-documents",
            "source_organization": "United Nations",
            "title": "Synthetic official document for local review UI tests",
            "publication_date": "2026-01-02",
            "source_url": "https://example.test/review-ui.pdf",
            "source_document_id": "TEST-REVIEW-UI-1",
            "discovered_at": "2026-01-03T00:00:00Z",
            "discovery_method": "MANUAL",
            "status": "CANDIDATES_CREATED",
            "notes": "Synthetic metadata-only test fixture.",
        }
        document["id"] = document_id(document["source_registry_id"], document["source_document_id"], document["source_url"])
        (root / "review/documents" / f"{document['id']}.json").write_text(canonical_json(document), encoding="utf-8")

        claim = "The United Nations documented one bounded synthetic fact for review UI testing."
        candidate = {
            "id": candidate_id(document["source_document_id"], claim),
            "source_document_id": document["source_document_id"],
            "source_organization": document["source_organization"],
            "source_title": document["title"],
            "source_url": document["source_url"],
            "publication_date": document["publication_date"],
            "proposed_event_date": None,
            "proposed_category": "statement",
            "proposed_claim": claim,
            "proposed_legal_status": "DOCUMENTED_EVIDENCE",
            "supporting_passage": "Synthetic exact supporting text.",
            "source_page": "p. 1",
            "extraction_notes": "Synthetic candidate used only to test local review state changes.",
            "related_published_records": [],
            "review_status": "NEEDS_REVIEW",
            "review_flags": [],
            "created_at": "2026-01-03T00:00:00Z",
            "reviewed_at": None,
            "reviewed_by": None,
            "review_notes": None,
            "proposed_record": None,
            "published_record_id": None,
        }
        path = root / "review/candidates" / f"{candidate['id']}.json"
        path.write_text(canonical_json(candidate), encoding="utf-8")
        self.assertEqual(validate_review(root), [])
        return ReviewStore(root), path

    @staticmethod
    def valid_record_fields() -> dict:
        return {
            "id": "synthetic-local-review-record",
            "title": "Synthetic local review record for isolated testing",
            "location": ["Synthetic location"],
            "actors": ["Synthetic actor"],
            "affected_population": ["Synthetic affected population"],
            "summary": "A synthetic official source documents one bounded fact for an isolated local reviewer test.",
            "legal_characterization": "Documented evidence",
            "evidence_type": ["official-report"],
            "source_quote": None,
            "verification_notes": "Human-review metadata is synthesized solely for this isolated unit test.",
            "tags": ["synthetic-test"],
        }

    def test_list_and_detail_expose_review_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store, path = self.prepare_root(Path(tmp))
            candidate = json.loads(path.read_text())
            rows = store.list()
            self.assertEqual([row["id"] for row in rows], [candidate["id"]])
            detail = store.detail(candidate["id"])
            self.assertEqual(detail["candidate"]["source_document_id"], "TEST-REVIEW-UI-1")
            self.assertEqual(detail["record_fields"]["id"], "")

    def test_verify_requires_complete_final_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store, path = self.prepare_root(Path(tmp))
            candidate = json.loads(path.read_text())
            with self.assertRaisesRegex(ReviewUIError, "final record is incomplete or invalid"):
                store.update(candidate["id"], {
                    "action": "verify",
                    "reviewer": "test-reviewer",
                    "review_notes": "I checked the synthetic source and candidate posture.",
                    "candidate": {},
                    "record": {"id": "incomplete"},
                })
            self.assertEqual(json.loads(path.read_text())["review_status"], "NEEDS_REVIEW")

    def test_verify_writes_review_provenance_but_does_not_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, path = self.prepare_root(root)
            candidate = json.loads(path.read_text())
            detail = store.update(candidate["id"], {
                "action": "verify",
                "reviewer": "test-reviewer",
                "review_notes": "Checked the cited passage, bounded claim, attribution and legal status.",
                "candidate": {},
                "record": self.valid_record_fields(),
            })
            updated = detail["candidate"]
            self.assertEqual(updated["review_status"], "VERIFIED")
            self.assertEqual(updated["reviewed_by"], "test-reviewer")
            self.assertIsNotNone(updated["reviewed_at"])
            self.assertEqual(updated["proposed_record"]["claim"], updated["proposed_claim"])
            self.assertEqual(updated["proposed_record"]["source_document_id"], updated["source_document_id"])
            self.assertEqual(list((root / "data").glob("*/*.json")), [])
            self.assertEqual(validate_review(root), [])

    def test_claim_rewrite_renames_candidate_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, path = self.prepare_root(root)
            candidate = json.loads(path.read_text())
            new_claim = "The United Nations documented a revised bounded synthetic fact for review UI testing."
            detail = store.update(candidate["id"], {
                "action": "needs_review",
                "reviewer": "",
                "review_notes": "Reworded during human review; verification still pending.",
                "candidate": {"proposed_claim": new_claim},
            })
            new_id = candidate_id(candidate["source_document_id"], new_claim)
            self.assertEqual(detail["candidate"]["id"], new_id)
            self.assertFalse(path.exists())
            self.assertTrue((root / "review/candidates" / f"{new_id}.json").is_file())
            self.assertEqual(validate_review(root), [])

    def test_reject_records_reviewer_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store, path = self.prepare_root(Path(tmp))
            candidate = json.loads(path.read_text())
            with self.assertRaisesRegex(ReviewUIError, "review notes are required"):
                store.update(candidate["id"], {"action": "reject", "reviewer": "test-reviewer", "review_notes": "", "candidate": {}})
            detail = store.update(candidate["id"], {
                "action": "reject",
                "reviewer": "test-reviewer",
                "review_notes": "The synthetic candidate does not meet the evidentiary threshold.",
                "candidate": {},
            })
            self.assertEqual(detail["candidate"]["review_status"], "REJECTED")
            self.assertEqual(detail["candidate"]["reviewed_by"], "test-reviewer")

    def test_verified_and_rejected_candidates_require_reopen_before_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store, path = self.prepare_root(Path(tmp))
            candidate = json.loads(path.read_text())
            verified = store.update(candidate["id"], {
                "action": "verify",
                "reviewer": "test-reviewer",
                "review_notes": "Checked the synthetic fixture for this isolated test.",
                "candidate": {},
                "record": self.valid_record_fields(),
            })["candidate"]
            with self.assertRaisesRegex(ReviewUIError, "must be reopened"):
                store.update(verified["id"], {"action": "save", "candidate": {"source_page": "p. 2"}})
            reopened = store.update(verified["id"], {"action": "reopen", "review_notes": "Reopened to reconsider the pinpoint."})["candidate"]
            self.assertEqual(reopened["review_status"], "NEEDS_REVIEW")
            self.assertIsNone(reopened["reviewed_by"])
            self.assertIsNone(reopened["reviewed_at"])


if __name__ == "__main__":
    unittest.main()
