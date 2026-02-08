import requests
import json
import sseclient
import os

# Define the problem
PROBLEM_TEXT = """
Fourier Series & Gibbs Phenomenon: Convergence, Overshoot, and Spectral Decay
Topic: Fourier analysis, approximation theory, convergence in norms, spectral interpretation.

Problem:
Let f(x) be the 2π-periodic extension of the square wave
  f(x) = 1  for x ∈ (0, π),
  f(x) = -1 for x ∈ (-π, 0).
Let S_N(x) be the N-term Fourier partial sum of f.

Tasks (plot required in at least three distinct steps):
(a) For N ∈ {5, 15, 50, 200}, plot f(x) and S_N(x) over [-π, π] on the same axes. Use the plots to measure overshoot near discontinuities and describe the Gibbs phenomenon.
(b) For the same N, plot the pointwise error |S_N(x) - f(x)| over [-π, π]. Then create a zoomed-in plot near x = 0 to show how the overshoot region shrinks while the overshoot height persists.
(c) Plot the magnitudes of Fourier coefficients |f̂(n)| versus n on log-log axes. Fit an approximate slope and relate it to the regularity (discontinuity) of f.
(d) Plot convergence metrics: compute and plot ||S_N - f||_{L^2} vs N and (separately) ||S_N - f||_{L∞} away from discontinuities vs N. Explain why the observed rates differ.

Optional extension:
(e) Replace S_N with Fejér sums σ_N(x). Plot σ_N versus S_N for the same N and compare overshoot and uniform convergence behavior.
"""

def verify_stream():
    url = "http://localhost:8000/api/v1/solve_v3_stream"
    
    payload = {
        "problem": PROBLEM_TEXT,
        "mode": "detailed",
        "subject": "math",
        "grade_level": "University",
        "image_url": None,
        "request_id": "verify_fourier_001"
    }

    print(f"Sending request to {url}...")
    try:
        response = requests.post(url, json=payload, stream=True)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error Content: {response.text[:1000]}")
            return

        client = sseclient.SSEClient(response)
        
        full_text = ""
        final_data = None
        
        for event in client.events():
            if event.event == "delta":
                data = json.loads(event.data)
                print(data["text"], end="", flush=True)
                full_text += data["text"]
            elif event.event == "structured_final":
                print("\n\n[STRUCTURED FINAL RECEIVED]")
                final_data = json.loads(event.data)
                print(json.dumps(final_data, indent=2)[:500] + "...")
            elif event.event == "done":
                print("\n\n[DONE]")
                break
                
        if final_data:
            print("\nSUCCESS: Received structured final data.")
            if "final_answer" in final_data:
                print("Final Answer present.")
            else:
                print("WARNING: Final Answer missing.")
        else:
            print("\nFAILURE: Did not receive structured final data.")

    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    verify_stream()
