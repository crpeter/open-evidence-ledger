#!/usr/bin/env python3
"""Build deterministic data exports and an accessible static HTML site."""
from __future__ import annotations

import csv
import html
import json
from collections import Counter
from urllib.parse import quote

from common import ROOT, load_records, validate

DIST = ROOT / "dist"
DOCS = ROOT / "docs"
BASE_URL = "https://crpeter.github.io/open-evidence-ledger"
REPO_URL = "https://github.com/crpeter/open-evidence-ledger"


def dump_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def page_shell(title: str, description: str, canonical: str, body: str, structured: dict) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(description, quote=True)}">
<link rel="canonical" href="{html.escape(canonical, quote=True)}">
<script type="application/ld+json">{json.dumps(structured, ensure_ascii=False).replace('</', '<\\/')}</script>
<style>
:root{{--bg:#f6f7f5;--surface:#fff;--text:#17201d;--muted:#64706b;--line:#dfe4e1;--accent:#155d47;--accent-soft:#e6f0ec;--dark:#10231d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}a{{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}}.shell{{max-width:1120px;margin:auto;padding:0 24px}}.topbar{{border-bottom:1px solid var(--line);background:rgba(246,247,245,.94)}}.topbar .shell{{min-height:66px;display:flex;align-items:center;justify-content:space-between;gap:24px}}.brand{{font-weight:760;letter-spacing:-.02em;color:var(--dark);text-decoration:none}}.nav{{display:flex;gap:18px;font-size:14px}}.nav a{{color:var(--muted);text-decoration:none}}main.shell{{padding-top:48px;padding-bottom:64px}}.hero{{padding:26px 0 42px;max-width:880px}}.eyebrow{{font-size:13px;font-weight:750;letter-spacing:.11em;text-transform:uppercase;color:var(--accent)}}h1{{font-size:clamp(38px,6vw,68px);line-height:1.02;letter-spacing:-.045em;margin:12px 0 18px;color:var(--dark)}}h2{{font-size:27px;letter-spacing:-.025em;margin:0 0 18px}}.lede{{font-size:20px;line-height:1.55;color:#3d4a45;max-width:760px}}.hero-note{{border-left:3px solid var(--accent);padding-left:16px;color:var(--muted);max-width:760px;margin-top:24px}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:8px 0 48px}}.stat{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:20px}}.stat strong{{display:block;font-size:29px;line-height:1.1;color:var(--dark)}}.stat span{{color:var(--muted);font-size:14px}}.section-head{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:18px}}.section-head p{{margin:0;color:var(--muted);max-width:560px}}.records{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.record{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px;display:flex;flex-direction:column;gap:11px}}.record:hover{{border-color:#b8c8c1}}.record h3{{font-size:19px;line-height:1.3;letter-spacing:-.015em;margin:0}}.record h3 a{{color:var(--dark);text-decoration:none}}.record p{{margin:0;color:#52605a}}.status{{display:inline-flex;align-self:flex-start;padding:4px 9px;border-radius:999px;background:var(--accent-soft);color:var(--accent);font-size:11px;font-weight:760;letter-spacing:.045em}}.source{{font-size:13px;color:var(--muted);margin-top:auto}}article{{max-width:820px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:32px}}article h1{{font-size:42px}}dt{{font-weight:750;margin-top:14px}}dd{{margin-left:0;color:#46534e}}blockquote{{border-left:3px solid var(--accent);padding-left:18px;margin-left:0;color:#3d4a45}}footer{{border-top:1px solid var(--line);padding:26px 0 42px;color:var(--muted);font-size:14px}}footer .shell{{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap}}footer a{{color:var(--muted)}}@media(max-width:760px){{.nav{{display:none}}.stats,.records{{grid-template-columns:1fr}}main.shell{{padding-top:28px}}article{{padding:22px}}article h1{{font-size:34px}}}}
</style></head>
<body><header class="topbar"><div class="shell"><a class="brand" href="{BASE_URL}/">Open Evidence Ledger</a><nav class="nav"><a href="{REPO_URL}/blob/main/METHODOLOGY.md">Methodology</a><a href="{REPO_URL}/blob/main/SOURCES.md">Sources</a><a href="{REPO_URL}">GitHub</a></nav></div></header><main class="shell">{body}</main><footer><div class="shell"><span>Open, provenance-first evidence records.</span><span><a href="{REPO_URL}">Project repository</a> · <a href="{REPO_URL}/blob/main/CONTRIBUTING.md">Contribute or correct a record</a></span></div></footer></body></html>"""


def record_page(record: dict) -> str:
    rid = record["id"]
    canonical = f"{BASE_URL}/records/{quote(rid)}.html"
    related = "".join(f'<li><a href="{quote(x)}.html">{html.escape(x)}</a></li>' for x in record["related_records"]) or "<li>None</li>"
    quote_html = f'<h2>Short source quotation</h2><blockquote>{html.escape(record["source_quote"])}</blockquote>' if record["source_quote"] else ""
    body = f"""<p><a href="../index.html">← All records</a></p><article><span class="status">{html.escape(record['legal_status'])}</span><h1>{html.escape(record['title'])}</h1><p class="lede">{html.escape(record['summary'])}</p>
<h2>Claim recorded</h2><p>{html.escape(record['claim'])}</p>
<dl><dt>Legal characterization</dt><dd>{html.escape(record['legal_characterization'])}</dd><dt>Event date</dt><dd>{html.escape(record['event_date'] or 'Not a single-date event')}</dd><dt>Location</dt><dd>{html.escape(', '.join(record['location']))}</dd><dt>Actors</dt><dd>{html.escape(', '.join(record['actors']))}</dd><dt>Affected population</dt><dd>{html.escape(', '.join(record['affected_population']))}</dd></dl>
<h2>Primary source</h2><p><a rel="cite" href="{html.escape(record['source_url'], quote=True)}">{html.escape(record['source_title'])}</a>, {html.escape(record['source_organization'])} ({html.escape(record['publication_date'])}); document {html.escape(record['source_document_id'])}, {html.escape(record['source_page'] or 'page not specified')}.</p>
{quote_html}<h2>Verification notes</h2><p>{html.escape(record['verification_notes'])}</p><h2>Related records</h2><ul>{related}</ul></article>"""
    structured = {"@context": "https://schema.org", "@type": "Report", "@id": canonical, "headline": record["title"], "description": record["summary"], "datePublished": record["publication_date"], "citation": record["source_url"], "identifier": rid, "keywords": record["tags"]}
    return page_shell(record["title"], record["summary"], canonical, body, structured)


def homepage(records: list[dict]) -> str:
    statuses = Counter(record["legal_status"] for record in records)
    organizations = {record["source_organization"] for record in records}
    cards = "".join(
        f'''<article class="record"><span class="status">{html.escape(record["legal_status"])}</span><h3><a href="records/{quote(record["id"])}.html">{html.escape(record["title"])}</a></h3><p>{html.escape(record["summary"])}</p><div class="source">{html.escape(record["source_organization"])} · {html.escape(record["publication_date"])}</div></article>'''
        for record in records
    )
    return f'''<section class="hero"><div class="eyebrow">Primary-source evidence index</div><h1>Open Evidence Ledger</h1><p class="lede">A machine-readable public record of carefully scoped claims concerning alleged and established violations of international humanitarian and human rights law in Israel/Palestine.</p><p class="hero-note">Each record preserves its source, legal posture, citation location, and verification notes. Status labels describe what the cited institution established or alleged; they are not independent verdicts by this project.</p></section><section class="stats"><div class="stat"><strong>{len(records)}</strong><span>reviewed pilot records</span></div><div class="stat"><strong>{len(statuses)}</strong><span>legal-status classifications</span></div><div class="stat"><strong>{len(organizations)}</strong><span>primary-source institutions</span></div></section><section><div class="section-head"><div><div class="eyebrow">Evidence records</div><h2>Current ledger</h2></div><p>The pilot focuses on demonstrating provenance, legal-status discipline, and reproducible sourcing before larger-scale ingestion.</p></div><div class="records">{cards}</div></section>'''


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
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value for key, value in record.items()})
    records_dir = DOCS / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    for stale_page in records_dir.glob("*.html"):
        stale_page.unlink()
    for record in records:
        (records_dir / f"{record['id']}.html").write_text(record_page(record), encoding="utf-8")
    structured = {"@context": "https://schema.org", "@type": "DataCatalog", "name": "Open Evidence Ledger", "description": "Structured primary-source records concerning Israel/Palestine", "dataset": [{"@type": "Dataset", "name": r["title"], "url": f"{BASE_URL}/records/{r['id']}.html"} for r in records]}
    (DOCS / "index.html").write_text(page_shell("Open Evidence Ledger", "A structured, provenance-first evidence corpus concerning Israel/Palestine.", f"{BASE_URL}/", homepage(records), structured), encoding="utf-8")
    urls = [f"{BASE_URL}/"] + [f"{BASE_URL}/records/{r['id']}.html" for r in records]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{html.escape(url)}</loc></url>\n" for url in urls) + "</urlset>\n"
    (DOCS / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"Built {len(records)} records into dist/ and docs/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
