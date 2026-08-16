# Contributing

Contributions from all perspectives are welcome when they improve accuracy, coverage, or reproducibility.

## Propose a record

1. Search IDs, claims, and source document IDs for an existing record.
2. Copy a current JSON record into the appropriate `data/` topic directory.
3. Keep the claim atomic and attribute every finding to the institution that made it.
4. Cite the direct official document, stable document identifier, and page/paragraph where possible.
5. Explain procedural posture, ambiguity, translations, and corroboration in `verification_notes`.
6. Use a brief quotation (maximum 500 characters by schema); do not reproduce long passages.
7. Set `created_at` and `updated_at` to UTC ISO 8601 timestamps.
8. Run validation before committing, then rebuild and inspect the diff.

```sh
python -m pip install -r requirements.txt
python scripts/validate.py
python scripts/build_index.py
python -m unittest discover -s tests
git diff --check
```

For a correction, update only what the new source supports, advance `updated_at`, and explain the reason in the pull request. Do not silently upgrade a legal status.

## Review checklist

Reviewers ask:

* Does the cited source support this exact claim at the cited location?
* Is an allegation, evidentiary threshold, interim order, UN finding, or final judgment labeled correctly?
* Are institution, document ID, event date, and publication date accurate?
* Does omitted context materially change the claim?
* Can a reader reproduce the record without relying on the contributor?
* Is language neutral and actor coverage driven by evidence rather than artificial symmetry?

Submissions that fabricate sources, quotes, dates, figures, authors, organizations, or legal conclusions will be rejected.
