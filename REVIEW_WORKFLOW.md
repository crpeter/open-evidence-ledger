# Human-reviewed source and candidate workflow

The only supported lifecycle is:

**official source → `review/documents/` → `review/candidates/` → human verification → explicit promotion → `data/` → generated public outputs**

Automation assists discovery and extraction. Humans approve the bounded evidentiary claim and its exact legal/procedural posture. A candidate is provisional material, not evidence, even when tooling extracted it. **Only validated records in `data/` are public ledger truth.** Review material is never copied to `dist/` or `docs/`.

## Commands and review gate

1. Run `python scripts/discover_sources.py`. Adapters are deliberately modular. Every initial official endpoint currently uses the `manual` adapter because no reliable machine-readable mechanism is assumed; the command reports this as “manual required,” never as evidence that no document exists. A reviewer may add schema-valid document JSON to `review/documents/` with a deterministic ID produced by `review_pipeline.document_id`.
2. Set a queued document's `status` to `REVIEWED` after checking its identity and metadata. Then run `python scripts/create_candidate.py SOURCE_DOCUMENT_ID --claim 'A bounded proposed claim…' --legal-status DOCUMENTED_EVIDENCE --category statement --extraction-notes 'How the passage was selected' --passage 'Exact supporting text' --source-page 'p. 1'`. The tool cannot set `VERIFIED` and does not infer absent values.
3. Run `python scripts/validate_candidates.py`. Review any deterministic posture or overlap flags. A human edits the candidate, supplies a complete `proposed_record`, and sets `review_status`, `reviewed_at`, `reviewed_by`, and substantive `review_notes`. Use `NEEDS_REVIEW` when uncertain. `REJECTED` requires notes.
4. Promote only with `python scripts/promote_candidate.py review/candidates/CANDIDATE_ID.json --approve`. The command rejects anything other than a fully reviewed `VERIFIED` candidate, applies the published schema and corpus invariants, writes `data/<category>/<record-id>.json`, then changes the candidate to `PUBLISHED` and records `published_record_id`. There is no discovery, extraction, build, or CI path that promotes automatically.
5. Run `python scripts/validate.py`, `python scripts/validate_candidates.py`, `python scripts/build_index.py`, and `python -m unittest discover -s tests`.

Reviewers must preserve attribution and procedural distinctions: allegation is not finding; an ICC warrant is not conviction; an ICJ provisional measure is not a final merits judgment; a UN finding is not a court judgment; and an advisory opinion is not a criminal judgment. Never infer or fabricate quotations, citations, dates, identifiers, figures, or legal conclusions. Flag uncertainty for review.
