
from app.services.solve.canonicalization_service import canonicalization_service
import json

def test_word_problem_canonicalization():
    text = "You have 32 grams of a radioactive kind of tellurium. How much will be left after 4 months if its half-life is 2 months?"
    
    print("\n--- TEST: Word Problem Canonicalization ---")
    print(f"Input: {text}")
    
    # 1. Intent
    intent = canonicalization_service.get_intent(text)
    print(f"Detected Intent: {intent}")
    
    # 2. Canonical Math Object
    math, meta = canonicalization_service.normalize_math_object(text, intent)
    print(f"Canonical Math Object: {math}")
    print(f"Metadata: {json.dumps(meta, indent=2)}")
    
    # 3. Key Generation
    key = canonicalization_service.compute_canonical_key(intent, math, {})
    print(f"Generated Key: {key}")
    
    # 4. Stability Check
    intent2 = canonicalization_service.get_intent(text)
    math2, meta2 = canonicalization_service.normalize_math_object(text, intent2)
    key2 = canonicalization_service.compute_canonical_key(intent2, math2, {})
    
    assert key == key2, "Key generation is unstable!"
    print("✅ Key is stable for identical input.")
    
    if "parse_error" in meta:
        print("ℹ️ Note: SymPy parsing failed (expected for word problems). Using normalized text fallback.")
    else:
        print("🎉 SymPy managed to parse it (impressive)!")

if __name__ == "__main__":
    test_word_problem_canonicalization()
