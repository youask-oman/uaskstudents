import requests, json
payload = {
    "text_query": "$$ \\text{line }(-3,0),(0,6) $$",
    "subject": "Algebra",
    "mode": "general"
}
try:
    r = requests.post('http://localhost:8000/api/v1/solve_v3?user_id=1', json=payload)
    print(f"Status: {r.status_code}")
    data = r.json()
    steps = data.get("solution", {}).get("steps", [])
    print(f"Steps count: {len(steps)}")
    if steps:
        print("Sample Step 1 Work:", steps[0].get("work"))
        print("Sample Step 1 Concept:", steps[0].get("concept"))
except Exception as e:
    print(e)
