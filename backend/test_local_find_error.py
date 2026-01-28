"""
Test script for local find error feature
"""
import asyncio
from app.services.math.error_localizer import analyze_error, normalize_ocr_text, parse_statement, validate_equation

def test_normalize():
    print("Testing normalization...")
    text = "93 × 43 + 3 = 18"
    normalized = normalize_ocr_text(text)
    print(f"  Input: {text}")
    print(f"  Output: {normalized}")
    assert "*" in normalized
    print("  ✓ Normalization works\n")

def test_parse():
    print("Testing parsing...")
    line = "93*43+3=18"
    parsed = parse_statement(line)
    print(f"  Input: {line}")
    print(f"  Kind: {parsed['kind']}")
    print(f"  LHS: {parsed.get('lhs_str')}")
    print(f"  RHS: {parsed.get('rhs_str')}")
    assert parsed["kind"] == "equation"
    print("  ✓ Parsing works\n")

def test_validate():
    print("Testing validation...")
    line = "93*43+3=18"
    parsed = parse_statement(line)
    validation = validate_equation(parsed)
    print(f"  Input: {line}")
    print(f"  Is correct: {validation['is_correct']}")
    print(f"  Confidence: {validation['confidence']}")
    print(f"  Method: {validation['method']}")
    assert validation["is_correct"] == False
    print("  ✓ Validation works (correctly detected error)\n")

def test_analyze():
    print("Testing full analysis...")
    text = "93*43+3=18"
    result = analyze_error(text)
    print(f"  Input: {text}")
    print(f"  Format: {result['detected_format']}")
    print(f"  First wrong line: {result['first_wrong_line_index']}")
    print(f"  What's wrong: {result['what_is_wrong']}")
    print(f"  Fix: {result['minimal_fix']}")
    print(f"  Confidence: {result['confidence']}")
    assert result["first_wrong_line_index"] == 0
    print("  ✓ Analysis works\n")

def test_correct_equation():
    print("Testing correct equation...")
    text = "2+2=4"
    result = analyze_error(text)
    print(f"  Input: {text}")
    print(f"  First wrong line: {result['first_wrong_line_index']}")
    print(f"  What's wrong: {result['what_is_wrong']}")
    assert result["first_wrong_line_index"] is None
    print("  ✓ Correctly identified as correct\n")

if __name__ == "__main__":
    print("=" * 60)
    print("LOCAL FIND ERROR - UNIT TESTS")
    print("=" * 60 + "\n")
    
    test_normalize()
    test_parse()
    test_validate()
    test_analyze()
    test_correct_equation()
    
    print("=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
