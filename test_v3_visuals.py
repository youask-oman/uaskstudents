import requests, json
payload = {
    "text_query": "$$ \\text{line }(-3,0),(0,6) $$",
    "subject": "Algebra",
    "mode": "general"
}
try:
    print("Sending request...")
    r = requests.post('http://localhost:8000/api/v1/solve_v3?user_id=1', json=payload)
    print(f"Status: {r.status_code}")
    data = r.json()
    
    solution = data.get("solution", {})
    steps = solution.get("steps", [])
    visuals = data.get("visuals", [])
    
    print(f"Steps: {len(steps)}")
    print(f"Visuals: {len(visuals)}")
    
    if visuals:
        print("Visual 1:", json.dumps(visuals[0], indent=2))
        
    for i, s in enumerate(steps):
        if s.get("visual_refs"):
            print(f"Step {i+1} has visual_refs: {s.get('visual_refs')}")

except Exception as e:
    print(e)
