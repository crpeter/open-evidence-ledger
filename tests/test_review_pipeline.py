"""Safety and determinism regression tests for the human review pipeline."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import load_records  # noqa: E402
from create_candidate import build_candidate  # noqa: E402
from discover_sources import enqueue  # noqa: E402
from promote_candidate import PromotionError, promote  # noqa: E402
from review_pipeline import (candidate_id, canonical_json, document_id, normalize_claim,
                             overlap_flags, procedural_flags, validator)  # noqa: E402


def queued_document() -> dict:
    return {"id": "", "source_registry_id": "test-source", "source_organization": "Official Test Institution",
            "title": "Synthetic official document for tests", "publication_date": "2024-01-02",
            "source_url": "https://example.test/official.pdf", "source_document_id": "TEST-DOC-1",
            "discovered_at": "2026-01-01T00:00:00Z", "discovery_method": "MANUAL", "status": "REVIEWED", "notes": "Synthetic fixture."}


class ReviewPipelineTests(unittest.TestCase):
    def test_source_registry_schema_and_unique_ids(self) -> None:
        registry = json.loads((ROOT / "sources/registry.json").read_text())
        self.assertEqual(list(validator(ROOT / "schema/source-registry.schema.json").iter_errors(registry)), [])
        self.assertEqual(len({x["id"] for x in registry}), len(registry))

    def test_document_deduplication_and_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "data/x").mkdir(parents=True); (root / "review/candidates").mkdir(parents=True)
            first, second = queued_document(), queued_document()
            second.update(source_document_id="A-DOC", source_url="https://example.test/a")
            paths = enqueue([first, first.copy(), second], root)
            self.assertEqual([json.loads(p.read_text())["source_document_id"] for p in paths], ["A-DOC", "TEST-DOC-1"])
            self.assertEqual(enqueue([first], root), [])
            queued = json.loads((root / "review/documents" / "document-2e1b6ceed71959b9.json").read_text())
            self.assertEqual(queued["id"], document_id("test-source", "TEST-DOC-1", "https://example.test/official.pdf"))

    def test_candidate_schema_and_deterministic_output(self) -> None:
        doc = queued_document()
        one = build_candidate(doc, claim="The institution documented a bounded synthetic event.", legal_status="DOCUMENTED_EVIDENCE",
                              category="statement", passage=None, page=None, notes="No inference.", created_at="2026-01-01T00:00:00Z")
        two = build_candidate(doc, claim=one["proposed_claim"], legal_status="DOCUMENTED_EVIDENCE",
                              category="statement", passage=None, page=None, notes="No inference.", created_at="2026-01-01T00:00:00Z")
        self.assertEqual(one, two)
        self.assertEqual(one["id"], candidate_id("TEST-DOC-1", one["proposed_claim"]))
        self.assertEqual(list(validator(ROOT / "schema/candidate.schema.json").iter_errors(one)), [])
        self.assertEqual(canonical_json(one), canonical_json(two))

    def test_duplicate_and_published_overlap_detection(self) -> None:
        published = load_records()[0][1]
        candidate = {"proposed_claim": published["claim"].upper() + "!!!", "source_document_id": published["source_document_id"], "related_published_records": []}
        self.assertEqual(normalize_claim(candidate["proposed_claim"]), normalize_claim(published["claim"]))
        self.assertIn("PUBLISHED_OVERLAP_REVIEW", overlap_flags(candidate, {published["id"]: published}))

    def test_procedural_flags_are_conservative_and_deterministic(self) -> None:
        cases = [
            ({"source_title": "ICC arrest warrant on reasonable grounds"}, "COURT_ALLEGATION_REVIEW"),
            ({"proposed_claim": "ICJ ordered provisional measures"}, "INTERIM_VS_FINAL_REVIEW"),
            ({"source_organization": "UN Commission of Inquiry"}, "UN_FINDING_SCOPE_REVIEW"),
            ({"extraction_notes": "Later proceeding terminated"}, "LATER_PROCEDURAL_POSTURE_REVIEW"),
            ({"proposed_claim": "According to witnesses, the event was alleged"}, "ATTRIBUTION_REVIEW"),
        ]
        for candidate, expected in cases:
            self.assertIn(expected, procedural_flags(candidate))

    def candidate_and_record(self, root: Path) -> tuple[Path, dict]:
        base = copy.deepcopy(load_records()[0][1])
        base.update(id="synthetic-promoted-record", title="Synthetic promoted record for isolated workflow testing",
                    claim="An official synthetic source documented one bounded test-only claim.", summary="An official synthetic source documented a bounded event solely for an isolated promotion test.",
                    source_organization="Official Test Institution", source_title="Synthetic official document for tests",
                    source_url="https://example.test/official.pdf", source_document_id="TEST-DOC-1", publication_date="2024-01-02",
                    category="statement", legal_status="DOCUMENTED_EVIDENCE", related_records=[], tags=["synthetic-test"])
        candidate = build_candidate(queued_document(), claim=base["claim"], legal_status=base["legal_status"], category=base["category"],
                                    passage=None, page=base["source_page"], notes="Human must inspect.", created_at="2026-01-01T00:00:00Z")
        candidate.update(review_status="VERIFIED", reviewed_at="2026-01-02T00:00:00Z", reviewed_by="Test Reviewer",
                         review_notes="Checked only within an isolated synthetic fixture.", proposed_record=base)
        path = root / "review/candidates" / f"{candidate['id']}.json"; path.parent.mkdir(parents=True)
        path.write_text(canonical_json(candidate))
        return path, candidate

    def test_promotion_requires_explicit_approval_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "data").mkdir()
            path, candidate = self.candidate_and_record(root)
            with self.assertRaisesRegex(PromotionError, "--approve"):
                promote(path, root=root)
            candidate["review_status"] = "CANDIDATE"; path.write_text(canonical_json(candidate))
            with self.assertRaisesRegex(PromotionError, "VERIFIED"):
                promote(path, root=root, approve=True)

    def test_successful_promotion_in_temporary_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "data").mkdir()
            path, candidate = self.candidate_and_record(root)
            destination = promote(path, root=root, approve=True)
            self.assertTrue(destination.is_file())
            updated = json.loads(path.read_text())
            self.assertEqual(updated["review_status"], "PUBLISHED")
            self.assertEqual(updated["published_record_id"], candidate["proposed_record"]["id"])

    def test_candidates_cannot_enter_public_exports_or_html(self) -> None:
        public = b"".join(path.read_bytes() for directory in (ROOT / "dist", ROOT / "docs/data", ROOT / "docs/records") for path in directory.glob("*" ) if path.is_file())
        for path in (ROOT / "review/candidates").glob("*.json"):
            candidate = json.loads(path.read_text())
            self.assertNotIn(candidate["id"].encode(), public)
        self.assertNotIn(b"Candidate claims are provisional", public)


if __name__ == "__main__":
    unittest.main()
