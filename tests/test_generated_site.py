"""Checks for the committed static topic and legal-status indexes."""
from __future__ import annotations

import json
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_index import BASE_URL, dump_json, source_manifest, status_slug, topic_label  # noqa: E402
from common import load_records  # noqa: E402


class PageMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.structured = ""
        self.alternates: list[dict[str, str | None]] = []
        self._element = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self._element = tag
        if tag == "meta" and values.get("name") == "description":
            self.description = values.get("content", "")
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href", "")
        if tag == "link" and values.get("rel") == "alternate":
            self.alternates.append(values)

    def handle_endtag(self, tag: str) -> None:
        self._element = ""

    def handle_data(self, data: str) -> None:
        if self._element == "title":
            self.title += data
        elif self._element == "script":
            self.structured += data


class GeneratedSiteTests(unittest.TestCase):
    def test_pages_exports_exactly_match_dist_exports(self) -> None:
        for name in ("evidence.json", "evidence.jsonl", "evidence.csv"):
            with self.subTest(name=name):
                self.assertEqual((ROOT / "docs/data" / name).read_bytes(), (ROOT / "dist" / name).read_bytes())

    def test_source_manifest_covers_every_record_and_is_deterministic(self) -> None:
        records = [record for _, record in load_records()]
        manifest_path = ROOT / "docs/data/sources.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), dump_json(source_manifest(records)))
        manifested_ids = [record_id for source in manifest for record_id in source["record_ids"]]
        self.assertCountEqual(manifested_ids, [record["id"] for record in records])
        self.assertEqual(len(manifested_ids), len(set(manifested_ids)))

    def test_source_metadata_is_consistent_with_records(self) -> None:
        records = [record for _, record in load_records()]
        manifest = json.loads((ROOT / "docs/data/sources.json").read_text(encoding="utf-8"))
        by_document = {source["source_document_id"]: source for source in manifest}
        keys = ("source_organization", "source_title", "source_url", "publication_date")
        for record in records:
            with self.subTest(record=record["id"]):
                source = by_document[record["source_document_id"]]
                self.assertEqual({key: source[key] for key in keys}, {key: record[key] for key in keys})

    def test_homepage_and_record_pages_link_json_dataset(self) -> None:
        pages = [ROOT / "docs/index.html", *(ROOT / "docs/records").glob("*.html")]
        expected = f"{BASE_URL}/data/evidence.json"
        for page in pages:
            parser = PageMetadataParser()
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertTrue(any(link.get("type") == "application/json" and link.get("href") == expected for link in parser.alternates), page)

    def test_known_topic_names_have_public_display_labels(self) -> None:
        expected = {
            "icc": "ICC",
            "icj": "ICJ",
            "ohchr": "OHCHR",
            "un-commission-of-inquiry": "UN Commission of Inquiry",
            "south-africa-v-israel": "South Africa v. Israel",
        }
        self.assertEqual({slug: topic_label(slug) for slug in expected}, expected)

    def test_every_topic_and_status_has_an_index_page(self) -> None:
        records = [record for _, record in load_records()]
        topics = {tag for record in records for tag in record["tags"]}
        statuses = {status_slug(record["legal_status"]) for record in records}
        self.assertEqual({path.stem for path in (ROOT / "docs/topics").glob("*.html")} - {"index"}, topics)
        self.assertEqual({path.stem for path in (ROOT / "docs/legal-status").glob("*.html")} - {"index"}, statuses)

    def test_collection_pages_have_metadata_and_are_in_sitemap(self) -> None:
        sitemap = (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8")
        pages = list((ROOT / "docs/topics").glob("*.html")) + list((ROOT / "docs/legal-status").glob("*.html"))
        for page in pages:
            with self.subTest(page=page.relative_to(ROOT)):
                parser = PageMetadataParser()
                parser.feed(page.read_text(encoding="utf-8"))
                self.assertTrue(parser.title)
                self.assertTrue(parser.description)
                self.assertTrue(parser.canonical.startswith(BASE_URL))
                self.assertIn(f"<loc>{parser.canonical}</loc>", sitemap)
                self.assertEqual(json.loads(parser.structured)["@type"], "CollectionPage")


if __name__ == "__main__":
    unittest.main()
