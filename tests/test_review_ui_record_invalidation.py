"""Regression test for invalidating stale final-record drafts during review edits."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import test_review_ui as helpers  # noqa: E402
from validate_candidates import validate_review  # noqa: E402


class ReviewUIRecordInvalidationTests(unittest.TestCase):
    def test_substantive_candidate_edit_clears_reopened_final_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, path = helpers.ReviewUITests.prepare_root(self, root)
            candidate = json.loads(path.read_text())
            verified = store.update(candidate["id"], {
                "action": "verify",
                "reviewer": "test-reviewer",
                "review_notes": "Checked the synthetic source and final record for this isolated test.",
                "candidate": {},
                "record": helpers.ReviewUITests.valid_record_fields(),
            })["candidate"]
            reopened = store.update(verified["id"], {
                "action": "reopen",
                "review_notes": "Reopened to change the source pinpoint.",
            })["candidate"]
            self.assertIsNotNone(reopened["proposed_record"])

            edited = store.update(reopened["id"], {
                "action": "needs_review",
                "review_notes": "Changed the pinpoint; the prior final-record draft must be rebuilt.",
                "candidate": {"source_page": "p. 2"},
            })["candidate"]
            self.assertEqual(edited["source_page"], "p. 2")
            self.assertIsNone(edited["proposed_record"])
            self.assertEqual(validate_review(root), [])


if __name__ == "__main__":
    unittest.main()
