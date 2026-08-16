"""Checks for the committed static topic and legal-status indexes."""
from __future__ import annotations

import json
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_index import BASE_URL, status_slug  # noqa: E402
from common import load_records  # noqa: E402


class PageMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.structured = ""
        self._element = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self._element = tag
        if tag == "meta" and values.get("name") == "description":
            self.description = values.get("content", "")
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        self._element = ""

    def handle_data(self, data: str) -> None:
        if self._element == "title":
            self.title += data
        elif self._element == "script":
            self.structured += data


class GeneratedSiteTests(unittest.TestCase):
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
