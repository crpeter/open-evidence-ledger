"""Regression tests for the authoritative schema and cross-record checks."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import load_records, schema_validator, validate  # noqa: E402


class SchemaValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = schema_validator()
        cls.base = load_records()[0][1]

    def assert_invalid(self, mutate) -> None:
        record = copy.deepcopy(self.base)
        mutate(record)
        self.assertTrue(list(self.validator.iter_errors(record)))

    def test_repository_records_are_valid(self) -> None:
        self.assertEqual(validate(load_records()), [])

    def test_required_and_additional_properties(self) -> None:
        self.assert_invalid(lambda record: record.pop("claim"))
        self.assert_invalid(lambda record: record.update({"unsupported_field": True}))

    def test_enums(self) -> None:
        self.assert_invalid(lambda record: record.update(legal_status="VERDICT"))
        self.assert_invalid(lambda record: record.update(category="miscellaneous"))
        self.assert_invalid(lambda record: record.update(evidence_type=["rumour"]))

    def test_patterns(self) -> None:
        self.assert_invalid(lambda record: record.update(id="Invalid ID"))
        self.assert_invalid(lambda record: record.update(tags=["Invalid Tag"]))
        self.assert_invalid(lambda record: record.update(source_url="http://example.test/source"))

    def test_minimum_and_maximum_lengths(self) -> None:
        self.assert_invalid(lambda record: record.update(title="short"))
        self.assert_invalid(lambda record: record.update(claim="too short"))
        self.assert_invalid(lambda record: record.update(source_quote="x" * 501))

    def test_array_type_size_and_uniqueness(self) -> None:
        self.assert_invalid(lambda record: record.update(actors="an actor"))
        self.assert_invalid(lambda record: record.update(location=[]))
        self.assert_invalid(lambda record: record.update(tags=["same", "same"]))

    def test_date_and_timestamp_formats(self) -> None:
        self.assert_invalid(lambda record: record.update(publication_date="2024-02-30"))
        self.assert_invalid(lambda record: record.update(created_at="not-a-timestamp"))


if __name__ == "__main__":
    unittest.main()
