"""
Quick test to verify graph_mode is being passed correctly.
This sends a request and immediately exits - NO waiting for LLM.
Just checks if the graph_mode value is logged.
"""
import requests
import json

print("Sending request with graph_mode='on'...")
url = "http://localhost:8000/api/v1/solve_v3_stream?user_id=1"
payload = {
    "confirmed_text": "2+2",  # Simple problem
    "graph_mode": "on",
    "requested_mode": "minimal",
    "tier": "free"
}

# Just start the request and read a few lines
response = requests.post(url, json=payload, stream=True, timeout=5)
lines_read = 0
for line in response.iter_lines():
    if line:
        print(f"  Response line: {line.decode('utf-8')[:100]}")
        lines_read += 1
        if lines_read >= 3:  # Just read first 3 lines
            break

print("\nRequest sent. Check server console for:")
print("  [SOLVE_V3_STREAM] Extracted graph_mode: on")
print("  [SOLVER_V3_STREAM] effective_graph_mode from body: on")

response.close()
