#!/usr/bin/env python3
"""Check unique primary-source URLs without changing corpus contents."""
from __future__ import annotations

import argparse
import urllib.error
import urllib.request

from common import load_records


BLOCKED_STATUSES = {403, 429}
ANTI_BOT_MARKERS = (b"captcha", b"cloudflare", b"verify you are human", b"access denied", b"bot detection")


def is_automated_request_block(error: urllib.error.HTTPError) -> bool:
    """Distinguish access controls from evidence that a source is missing."""
    if error.code in BLOCKED_STATUSES:
        return True
    body = error.read(65536).lower()
    return any(marker in body for marker in ANTI_BOT_MARKERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    urls = sorted({record["source_url"] for _, record in load_records()})
    failures = 0
    blocked = 0
    for url in urls:
        request = urllib.request.Request(url, headers={"User-Agent": "OpenEvidenceLedger-LinkChecker/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                print(f"OK {response.status} {url}")
        except urllib.error.HTTPError as error:
            if is_automated_request_block(error):
                blocked += 1
                print(f"BLOCKED {error.code} {url}: automated request refused; citation validity undetermined")
            else:
                failures += 1
                print(f"FAIL {url}: {error}")
        except (urllib.error.URLError, TimeoutError) as error:
            failures += 1
            print(f"FAIL {url}: {error}")
    print(f"Checked {len(urls)} unique URLs; {failures} failed, {blocked} blocked automated requests.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
