
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils.safe_json import safe_parse_json, extract_and_parse_json
import json

def test_case(name, input_str, expected_substr=None, expect_error=False):
    print(f"--- Test Case: {name} ---")
    print(f"Input: {repr(input_str)}")
    try:
        result = safe_parse_json(input_str)
        print(f"Result: {json.dumps(result)[:50]}...")
        if expect_error:
            print("FAILED: Expected error but got success.")
            return False
        if expected_substr:
            if expected_substr not in json.dumps(result):
                print(f"FAILED: Expected substring '{expected_substr}' not found.")
                return False
        print("PASSED")
        return True
    except Exception as e:
        if expect_error:
            print(f"PASSED (Caught expected error: {e})")
            return True
        else:
            print(f"FAILED: Unexpected error: {e}")
            return False

def run_tests():
    # Case A: Clean single JSON
    a = '{"foo": "bar"}'
    test_case("A: Clean", a, expected_substr="bar")

    # Case B: SSE Contamination
    b = 'data: {"foo": "bar"}\n\n'
    test_case("B: SSE Contamination", b, expected_substr="bar")

    # Case C: Meta + Final (Multiple Objects)
    c = '{"meta": "info"}{"solution": "42"}'
    # Our extractor takes the FIRST object.
    # Wait, if the first object is meta, we might want the LAST or merge?
    # The user said: "Extract exactly ONE JSON object and parse that." 
    # Usually the final answer is the last one or the big one.
    # If the stream is {meta}{final}, taking {meta} might be wrong if `full_content` has both.
    # Let's see what happens.
    test_case("C: Multiple Objects (First)", c, expected_substr="info")
    
    # Case D: Partial/Truncated
    d = '{"foo": "bar"'
    test_case("D: Partial", d, expect_error=True)
    
    # Case E: Middle Extractor
    e = '  garbage  {"valid": 1}  more garbage '
    test_case("E: Surrounded by garbage", e, expected_substr="valid")
    
    # Case F: Nested Braces
    f = '{"a": {"b": "c"}}'
    test_case("F: Nested", f, expected_substr="c")
    
    # Case G: Braces in String
    g = '{"a": "b}"}'
    test_case("G: Braces in String", g, expected_substr="b}")

if __name__ == "__main__":
    run_tests()
