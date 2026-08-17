#!/usr/bin/env python3
"""Run conservative discovery adapters; this command never writes to data/."""
from __future__ import annotations

import argparse
import json

from common import ROOT
from review_pipeline import DOCUMENTS, document_id, known_document_ids, write_sorted


class ManualAdapter:
    """Explicitly records that a source has no reliable automated adapter."""
    def discover(self, source: dict) -> list[dict]:
        print(f"MANUAL REQUIRED {source['id']}: {source['discovery_url']} (not interpreted as no new documents)")
        return []


ADAPTERS = {"manual": ManualAdapter}


def enqueue(documents: list[dict], root=ROOT) -> list:
    """Persist new documents in stable ID order, deduplicating every corpus tier."""
    known = known_document_ids(root)
    unique = {}
    for document in documents:
        source_id = document["source_document_id"]
        if source_id in known:
            continue
        unique[source_id] = document
    paths = []
    for document in sorted(unique.values(), key=lambda x: (x["source_document_id"], x["source_url"])):
        document["id"] = document_id(document["source_registry_id"], document["source_document_id"], document["source_url"])
        paths.append(write_sorted(root / "review/documents", document))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=ROOT / "sources/registry.json", type=str)
    args = parser.parse_args()
    sources = json.loads(open(args.registry, encoding="utf-8").read())
    discovered = []
    for source in sorted((x for x in sources if x["enabled"]), key=lambda x: (x["priority"], x["id"])):
        adapter = ADAPTERS.get(source["adapter"])
        if adapter is None:
            print(f"UNAVAILABLE {source['id']}: unknown adapter; discovery incomplete")
            continue
        try:
            discovered.extend(adapter().discover(source))
        except OSError as exc:
            print(f"UNREACHABLE {source['id']}: {exc}; discovery incomplete")
    created = enqueue(discovered)
    print(f"Queued {len(created)} new official document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
