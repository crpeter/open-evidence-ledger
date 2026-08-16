# Open Evidence Ledger

Open Evidence Ledger is an open, machine-readable repository of carefully scoped claims concerning alleged and established violations of international humanitarian and human rights law in Israel/Palestine. It is an evidence index—not advocacy, a court, or an independent fact-finding body.

## Status and scope

This initial release proves the data model with five primary-source examples. A record reports what its named source supports. In particular, `COURT_INTERIM_FINDING` is not a final merits judgment, `COURT_ALLEGATION` is not a conviction, and `UN_FINDING` is not a judicial determination. See [METHODOLOGY.md](METHODOLOGY.md) before interpreting or contributing data.

## Repository map

* `data/<topic>/*.json` — reviewable source records
* `schema/record.schema.json` — machine-readable contract and controlled values
* `scripts/validate.py` — required fields, formats, references, and duplicate checks
* `scripts/build_index.py` — deterministic JSON, JSONL, CSV, HTML, and sitemap builder
* `scripts/check_links.py` — optional live primary-source URL check
* `dist/` and `site/` — generated artifacts committed for easy reuse and static hosting

## Build

Requires Python 3.10+ and no third-party packages.

```sh
python scripts/validate.py
python scripts/build_index.py
python scripts/check_links.py  # requires network access; servers may block automation
```

Generated HTML is usable without JavaScript. Each record page has a canonical URL, concise summary, prominent source citation, related-record links, and Schema.org JSON-LD.

## Reuse and corrections

Consume `dist/evidence.json`, `dist/evidence.jsonl`, or `dist/evidence.csv`. Treat `id` as the stable identifier and check `updated_at` when refreshing an index. Please submit corrections with precise primary-source support using [CONTRIBUTING.md](CONTRIBUTING.md).

