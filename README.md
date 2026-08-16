# Open Evidence Ledger

Open Evidence Ledger is an open, machine-readable repository of carefully scoped claims concerning alleged and established violations of international humanitarian and human rights law in Israel/Palestine. It is an evidence index—not advocacy, a court, or an independent fact-finding body.

## Status and scope

This initial release proves the data model with six primary-source examples that collectively exercise five legitimate statuses: `COURT_INTERIM_FINDING`, `COURT_FINAL_FINDING`, `COURT_ALLEGATION`, `UN_FINDING`, and `DOCUMENTED_EVIDENCE`. A record reports only what its named source supports. See [METHODOLOGY.md](METHODOLOGY.md) before interpreting or contributing data.

## Repository map

* `data/<topic>/*.json` — reviewable source records
* `schema/record.schema.json` — machine-readable contract and controlled values
* `scripts/validate.py` — required fields, formats, references, and duplicate checks
* `scripts/build_index.py` — deterministic JSON, JSONL, CSV, HTML, and sitemap builder
* `scripts/check_links.py` — optional live primary-source URL check
* `dist/` and `docs/` — generated artifacts committed for easy reuse and GitHub Pages hosting

## Build

Requires Python 3.10+. Install the single direct validation dependency first:

```sh
python -m pip install -r requirements.txt
python scripts/validate.py
python scripts/build_index.py
python -m unittest discover -s tests
python scripts/check_links.py  # requires network access; servers may block automation
```

Generated HTML is usable without JavaScript. Each record page has a canonical URL, concise summary, prominent source citation, related-record links, and Schema.org JSON-LD.

## Reuse and corrections

Consume `dist/evidence.json`, `dist/evidence.jsonl`, or `dist/evidence.csv`. Treat `id` as the stable identifier and check `updated_at` when refreshing an index. Please submit corrections with precise primary-source support using [CONTRIBUTING.md](CONTRIBUTING.md).
