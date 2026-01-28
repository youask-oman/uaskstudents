from app.services.math.error_localizer import OCRPayload, find_first_error_from_ocr, Budget
import sys
import os

# Ensure app is in path
sys.path.append(os.getcwd())

def test_arithmetic():
    ocr = OCRPayload(
        raw="93 + 43 + 3 = 18",
        text="93 + 43 + 3 = 18",
        confidence=0.95
    )
    budget = Budget()
    print("Testing localizer with: 93 + 43 + 3 = 18")
    result = find_first_error_from_ocr(ocr, transcript_hint="find_error", budget=budget)
    
    print(f"First wrong line index: {result.first_wrong_line_index}")
    print(f"What is wrong: {result.what_is_wrong}")
    print(f"Minimal fix: {result.minimal_fix}")
    print(f"Confidence: {result.confidence}")
    for i, line in enumerate(result.per_line):
        print(f"Line {i}: ok={line.ok}, reason='{line.reason}', debug={line.debug}")

if __name__ == "__main__":
    test_arithmetic()
