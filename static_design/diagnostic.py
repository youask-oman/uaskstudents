#!/usr/bin/env python3
"""
Diagnose why app gets 307 chars vs CLI's 13,341 chars
"""
import requests, json, time

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mightykatun/qwen2.5-math:7b"

PROMPT = 'Solve √(x+3) = x-3. Output exactly 18 detailed steps. Include full Plotly spec and 4 verification checks. Minimum 4000 characters. Start with {"schema_version":"v1"'

# TEST 1: Non-streaming (should match CLI)
print("TEST 1: Non-streaming (/api/generate)")
start = time.time()
resp1 = requests.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "prompt": PROMPT,
        "stream": False,          # ← CRITICAL: non-streaming
        "raw": True,              # ← CRITICAL: disable chat formatting
        "options": {
            "num_predict": 4096,
            "temperature": 0.1,
            "stop": []            # ← CRITICAL: no stop sequences
        }
    },
    timeout=120
)
elapsed1 = time.time() - start
output1 = resp1.json()["response"]
print(f"✓ Length: {len(output1):,} chars | Time: {elapsed1:.1f}s")
print(f"✓ Starts with '{{': {output1.strip().startswith('{')}")
print(f"✓ Ends with '}}': {output1.strip().endswith('}')}")
print(f"✓ First '}}' at char: {output1.find('}')}\n")

# TEST 2: Streaming (likely what your app uses)
print("TEST 2: Streaming (/api/generate + stream:true)")
start = time.time()
resp2 = requests.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "prompt": PROMPT,
        "stream": True,           # ← BUG: streaming stops early
        "raw": True,
        "options": {"num_predict": 4096, "stop": []}
    },
    stream=True,
    timeout=120
)
chunks = []
for line in resp2.iter_lines():
    if line:
        chunk = json.loads(line)["response"]
        chunks.append(chunk)
        # Simulate app bug: stop at first '}'
        if '}' in chunk and len(''.join(chunks)) < 500:
            print(f"⚠️  APP BUG SIMULATED: Stopped at char {len(''.join(chunks))} after seeing '}}'")
            break
output2 = ''.join(chunks)
elapsed2 = time.time() - start
print(f"✗ Truncated length: {len(output2):,} chars | Time: {elapsed2:.1f}s\n")

# TEST 3: With stop sequence (worst case)
print("TEST 3: Non-streaming WITH stop:['}']")
resp3 = requests.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "prompt": PROMPT,
        "stream": False,
        "raw": True,
        "options": {
            "num_predict": 4096,
            "stop": ["}"]  # ← KILLS GENERATION AT FIRST BRACE
        }
    },
    timeout=120
)
output3 = resp3.json()["response"]
print(f"✗ Stop-sequence length: {len(output3):,} chars")
print(f"   Output preview: {output3[:100]}...\n")

print("="*60)
print("DIAGNOSIS:")
print(f"• Non-streaming + raw:true + stop:[] → {len(output1):,} chars ✅")
print(f"• Streaming (app likely) → ~{len(output2):,} chars ❌")
print(f"• Stop:['}}'] (common bug) → {len(output3):,} chars ❌")
print("="*60)