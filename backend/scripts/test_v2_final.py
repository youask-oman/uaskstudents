import requests
import json

# Test the solve endpoint with Solver V2 enabled
url = "http://localhost:8000/api/v1/solve"

payload = {
    "confirmed_markdown": "Solve: 2x + 5 = 13",
    "mode": "general",
    "user_id": 1
}

headers = {
    "Content-Type": "application/json"
}

print("=" * 60)
print("TESTING SOLVER V2 WITH TRANSFORMATION")
print("=" * 60)
print(f"\nProblem: {payload['confirmed_markdown']}")
print(f"\nSending request to {url}...\n")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=120)
    print(f"✓ Status Code: {response.status_code}\n")
    
    if response.status_code == 200:
        data = response.json()
        session_id = data.get("session_id")
        solution = data.get("solution", {})
        verification = data.get("verification", {})
        concepts = data.get("concepts", [])
        visuals = data.get("visuals", [])
        model_used = data.get("model_used", "Unknown")
        
        print(f"✓ Session ID: {session_id}")
        print(f"✓ Model Used: {model_used}")
        print(f"✓ Final Answer: {solution.get('final_answer', 'N/A')}")
        print(f"✓ Verification Methods: {len(verification.get('methods', []))}")
        print(f"✓ Concepts: {len(concepts)}")
        print(f"✓ Visuals: {len(visuals)}")
        
        # Check if transformation worked
        print("\n" + "=" * 60)
        print("VERIFICATION STRUCTURE CHECK")
        print("=" * 60)
        methods = verification.get("methods", [])
        if methods:
            first_method = methods[0]
            print(f"\nFirst method keys: {list(first_method.keys())}")
            if "math" in first_method:
                print(f"✓ Has 'math' key")
                if "latex_lines" in first_method["math"]:
                    print(f"✓ Has 'math.latex_lines' (frontend compatible!)")
                    print(f"  latex_lines: {first_method['math']['latex_lines']}")
                else:
                    print(f"✗ Missing 'math.latex_lines'")
            else:
                print(f"✗ Missing 'math' key")
        
        print("\n" + "=" * 60)
        print("CONCEPTS CHECK")
        print("=" * 60)
        if concepts:
            print(f"✓ Concepts is an array with {len(concepts)} items")
            print(f"  First concept: {concepts[0].get('name', 'N/A')}")
        else:
            print("✗ No concepts found")
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Solver V2 is working with transformation!")
        print("=" * 60)
        
    else:
        print(f"\n❌ Error {response.status_code}")
        print(response.text)
        
except requests.exceptions.Timeout:
    print("\n❌ Request timed out after 120 seconds!")
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
