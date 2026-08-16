#!/usr/bin/env python3
"""Build deterministic data exports and an accessible static HTML site."""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from urllib.parse import quote

from common import ROOT, load_records, validate

DIST = ROOT / "dist"
SITE = ROOT / "site"
BASE_URL = "https://open-evidence-ledger.github.io/open-evidence-ledger"


def dump_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def page_shell(title: str, description: str, canonical: str, body: str, structured: dict) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(description, quote=True)}">
<link rel="canonical" href="{html.escape(canonical, quote=True)}">
<script type="application/ld+json">{json.dumps(structured, ensure_ascii=False).replace('</', '<\\/')}</script>
<style>body{{font:16px/1.55 system-ui,sans-serif;max-width:900px;margin:auto;padding:2rem;color:#18202a}}a{{color:#0645ad}}dt{{font-weight:700;margin-top:.8rem}}.status{{display:inline-block;padding:.2rem .5rem;background:#e8eef5;border-radius:.25rem}}blockquote{{border-left:4px solid #bbc;padding-left:1rem}}footer{{margin-top:3rem;border-top:1px solid #ddd;padding-top:1rem}}</style></head>
<body>{body}<footer><a href="{BASE_URL}/">Open Evidence Ledger</a> · Generated from reviewable source records.</footer></body></html>"""


def record_page(record: dict) -> str:
    rid = record["id"]
    canonical = f"{BASE_URL}/records/{quote(rid)}.html"
    related = "".join(f'<li><a href="{quote(x)}.html">{html.escape(x)}</a></li>' for x in record["related_records"]) or "<li>None</li>"
    quote_html = f'<h2>Short source quotation</h2><blockquote>{html.escape(record["source_quote"])}</blockquote>' if record["source_quote"] else ""
    body = f"""<nav><a href="../index.html">All records</a></nav><article><h1>{html.escape(record['title'])}</h1>
<p class="status">{html.escape(record['legal_status'])}</p><p>{html.escape(record['summary'])}</p>
<h2>Claim recorded</h2><p>{html.escape(record['claim'])}</p>
<dl><dt>Legal characterization</dt><dd>{html.escape(record['legal_characterization'])}</dd><dt>Event date</dt><dd>{html.escape(record['event_date'] or 'Not a single-date event')}</dd><dt>Location</dt><dd>{html.escape(', '.join(record['location']))}</dd><dt>Actors</dt><dd>{html.escape(', '.join(record['actors']))}</dd><dt>Affected population</dt><dd>{html.escape(', '.join(record['affected_population']))}</dd></dl>
<h2>Primary source</h2><p><a rel="cite" href="{html.escape(record['source_url'], quote=True)}">{html.escape(record['source_title'])}</a>, {html.escape(record['source_organization'])} ({html.escape(record['publication_date'])}); document {html.escape(record['source_document_id'])}, {html.escape(record['source_page'] or 'page not specified')}.</p>
{quote_html}<h2>Verification notes</h2><p>{html.escape(record['verification_notes'])}</p><h2>Related records</h2><ul>{related}</ul></article>"""
    structured = {"@context": "https://schema.org", "@type": "Report", "@id": canonical, "headline": record["title"], "description": record["summary"], "datePublished": record["publication_date"], "citation": record["source_url"], "identifier": rid, "keywords": record["tags"]}
    return page_shell(record["title"], record["summary"], canonical, body, structured)


def main() -> int:
    loaded = load_records()
    errors = validate(loaded)
    if errors:
        print("Build stopped; run scripts/validate.py for details.")
        return 1
    records = [record for _, record in loaded]
    DIST.mkdir(exist_ok=True)
    (DIST / "evidence.json").write_text(dump_json(records), encoding="utf-8")
    (DIST / "evidence.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    columns = list(records[0])
    with (DIST / "evidence.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value for key, value in record.items()})
    records_dir = SITE / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        (records_dir / f"{record['id']}.html").write_text(record_page(record), encoding="utf-8")
    items = "".join(f'<li><a href="records/{quote(r["id"])}.html">{html.escape(r["title"])}</a> <span class="status">{r["legal_status"]}</span><br>{html.escape(r["summary"])}</li>' for r in records)
    body = f"<h1>Open Evidence Ledger</h1><p>A provenance-first corpus. A status describes the cited institution's treatment of the claim, not an independent conclusion by this project.</p><ol>{items}</ol>"
    structured = {"@context": "https://schema.org", "@type": "DataCatalog", "name": "Open Evidence Ledger", "description": "Structured primary-source records concerning Israel/Palestine", "dataset": [{"@type": "Dataset", "name": r["title"], "url": f"{BASE_URL}/records/{r['id']}.html"} for r in records]}
    (SITE / "index.html").write_text(page_shell("Open Evidence Ledger", "A structured, provenance-first evidence corpus concerning Israel/Palestine.", f"{BASE_URL}/", body, structured), encoding="utf-8")
    urls = [f"{BASE_URL}/"] + [f"{BASE_URL}/records/{r['id']}.html" for r in records]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{html.escape(url)}</loc></url>\n" for url in urls) + "</urlset>\n"
    (SITE / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"Built {len(records)} records into dist/ and site/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
