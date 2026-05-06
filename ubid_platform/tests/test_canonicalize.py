"""Tests for canonicalization pipeline."""
import pytest
from ubid.canonicalize import name_normalizer, address_parser, identifier_extractor, locality_normalizer


class TestNameNormalizer:
    def test_strips_pvt_ltd(self):
        norm, tokens, stripped = name_normalizer.normalize("Sharma Traders Pvt Ltd")
        assert "pvt" not in stripped
        assert "ltd" not in stripped
        assert "sharma" in stripped

    def test_strips_ms_prefix(self):
        norm, tokens, stripped = name_normalizer.normalize("M/s Krishna Industries")
        assert "m/s" not in norm or "m" not in stripped

    def test_expands_abbreviation(self):
        norm, tokens, stripped = name_normalizer.normalize("ABC Trdrs")
        assert "traders" in norm

    def test_prefix4(self):
        assert name_normalizer.name_prefix4("sharmaindustries") == "shar"
        assert len(name_normalizer.name_prefix4("ab")) == 4  # padded


class TestAddressParser:
    def test_extracts_pin_bengaluru(self):
        parsed = address_parser.parse("No. 12, Peenya 2nd Stage, Bengaluru 560058")
        assert parsed.pin_code == "560058"

    def test_extracts_door_number(self):
        parsed = address_parser.parse("No. 12/A, 3rd Cross, Peenya")
        assert parsed.door_number is not None

    def test_detects_bengaluru_urban(self):
        parsed = address_parser.parse("Plot 45, KIADB, Bangalore Urban 560100")
        assert parsed.district == "bengaluru urban"

    def test_no_crash_empty(self):
        parsed = address_parser.parse("")
        assert parsed.pin_code is None


class TestIdentifierExtractor:
    def test_valid_pan(self):
        assert identifier_extractor.clean_pan("ABCDE1234F") == "ABCDE1234F"

    def test_invalid_pan_returns_none(self):
        assert identifier_extractor.clean_pan("INVALID") is None
        assert identifier_extractor.clean_pan("") is None

    def test_pan_entity_type_company(self):
        assert identifier_extractor.pan_entity_type("ABCDE1234F") == "company"

    def test_pan_entity_type_individual(self):
        assert identifier_extractor.pan_entity_type("ABCPD1234F") == "individual"

    def test_pan_is_proprietorship(self):
        assert identifier_extractor.pan_is_proprietorship("ABCPD1234F") is True
        assert identifier_extractor.pan_is_proprietorship("ABCDE1234F") is False

    def test_extract_pan_from_gstin(self):
        pan = identifier_extractor.extract_pan_from_gstin("29ABCDE1234F1Z5")
        assert pan == "ABCDE1234F"

    def test_clean_phone(self):
        assert identifier_extractor.clean_phone("9876543210") == "9876543210"
        assert identifier_extractor.clean_phone("+91-9876543210") == "9876543210"
        assert identifier_extractor.clean_phone("1234567890") is None  # invalid start

    def test_clean_email(self):
        assert identifier_extractor.clean_email("test@example.com") == "test@example.com"
        assert identifier_extractor.clean_email("INVALID") is None


class TestLocalityNormalizer:
    def test_exact_synonym(self):
        result = locality_normalizer.normalize("Peenya 2nd Stage")
        assert result == "peenya industrial area phase 2"

    def test_fuzzy_match(self):
        result = locality_normalizer.normalize("Peenya 2nd Stg")
        assert result is not None

    def test_none_input(self):
        assert locality_normalizer.normalize(None) is None
