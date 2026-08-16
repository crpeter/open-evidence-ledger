#!/usr/bin/env python3
"""Validate all source records and cross-record invariants."""
from common import load_records, validate


def main() -> int:
    records = load_records()
    errors = validate(records)
    if not records:
        errors.append("no records found")
    if errors:
        print("Validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Validated {len(records)} records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
