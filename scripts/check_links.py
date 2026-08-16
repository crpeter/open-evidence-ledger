#!/usr/bin/env python3
"""Check unique primary-source URLs without changing corpus contents."""
from __future__ import annotations

import argparse
import urllib.error
import urllib.request

from common import load_records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    urls = sorted({record["source_url"] for _, record in load_records()})
    failures = 0
    for url in urls:
        request = urllib.request.Request(url, headers={"User-Agent": "OpenEvidenceLedger-LinkChecker/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                print(f"OK {response.status} {url}")
        except (urllib.error.URLError, TimeoutError) as error:
            failures += 1
            print(f"FAIL {url}: {error}")
    print(f"Checked {len(urls)} unique URLs; {failures} failed.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
