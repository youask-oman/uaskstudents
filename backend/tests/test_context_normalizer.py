"""
Unit tests for context normalization (Part D1).
Tests: Canada->CA, ON->CA-ON, Grade 11->11
"""
import pytest
from app.services.context_normalizer import (
    normalize_country,
    normalize_province_state,
    normalize_grade_level,
    normalize_trusted_context,
    build_compact_user_message
)


class TestNormalizeCountry:
    def test_canada_to_ca(self):
        assert normalize_country("Canada") == "CA"
        assert normalize_country("canada") == "CA"
        assert normalize_country("CA") == "CA"
    
    def test_us_variants(self):
        assert normalize_country("United States") == "US"
        assert normalize_country("USA") == "US"
        assert normalize_country("US") == "US"
    
    def test_none_returns_none(self):
        assert normalize_country(None) is None
        assert normalize_country("") is None


class TestNormalizeProvinceState:
    def test_on_to_ca_on(self):
        # Without country hint, ON is ambiguous but should map to CA-ON
        assert normalize_province_state("ON") == "CA-ON"
        assert normalize_province_state("Ontario") == "CA-ON"
    
    def test_us_states(self):
        assert normalize_province_state("California") == "US-CA"
        assert normalize_province_state("NY") == "US-NY"
        assert normalize_province_state("Texas") == "US-TX"
    
    def test_already_formatted(self):
        assert normalize_province_state("CA-ON") == "CA-ON"
        assert normalize_province_state("US-CA") == "US-CA"
    
    def test_with_country_hint(self):
        # With CA country context
        assert normalize_province_state("BC", "CA") == "CA-BC"
    
    def test_none_returns_none(self):
        assert normalize_province_state(None) is None


class TestNormalizeGradeLevel:
    def test_grade_11_to_11(self):
        assert normalize_grade_level("Grade 11") == "11"
        assert normalize_grade_level("grade 11") == "11"
        assert normalize_grade_level("Grade11") == "11"
    
    def test_numeric_stays_numeric(self):
        assert normalize_grade_level("11") == "11"
        assert normalize_grade_level("9") == "9"
    
    def test_college_to_c(self):
        assert normalize_grade_level("College-1") == "C1"
        assert normalize_grade_level("College 2") == "C2"
    
    def test_kindergarten(self):
        assert normalize_grade_level("K") == "K"
        assert normalize_grade_level("Kindergarten") == "K"
    
    def test_none_returns_none(self):
        assert normalize_grade_level(None) is None


class TestNormalizeTrustedContext:
    def test_full_normalization(self):
        ctx = {
            "learning_mode": "study",
            "grade_level": "Grade 11",
            "region_country": "Canada",
            "region_state_province": "ON"
        }
        result = normalize_trusted_context(ctx)
        
        assert result["learning_mode"] == "study"
        assert result["grade_level"] == "11"
        assert result["region_country"] == "CA"
        assert result["region_state_province"] == "CA-ON"
    
    def test_empty_context(self):
        assert normalize_trusted_context({}) == {}
        assert normalize_trusted_context(None) == {}
    
    def test_partial_context(self):
        ctx = {"learning_mode": "solve"}
        result = normalize_trusted_context(ctx)
        assert result == {"learning_mode": "solve"}


class TestBuildCompactUserMessage:
    def test_minimal_message(self):
        msg = build_compact_user_message("expand(x-1)")
        assert msg == '{"problem":"expand(x-1)"}'
    
    def test_with_context(self):
        msg = build_compact_user_message(
            "expand(x-1)",
            trusted_context={"learning_mode": "study", "grade_level": "11"}
        )
        # Should be compact JSON
        import json
        data = json.loads(msg)
        assert data["problem"] == "expand(x-1)"
        assert data["trusted_context"]["learning_mode"] == "study"
        assert data["trusted_context"]["grade_level"] == "11"
    
    def test_with_task(self):
        msg = build_compact_user_message(
            "expand(x-1)",
            task="expand"
        )
        import json
        data = json.loads(msg)
        assert data["task"] == "expand"
