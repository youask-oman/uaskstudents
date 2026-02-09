import requests
import json
import time

def test_graph_mode_on():
    print("Testing streaming solve_v3 with graph_mode='on'...")
    url = "http://localhost:8000/api/v1/solve_v3_stream?user_id=1"
    payload = {
        "confirmed_text": "line (1, 2), (4, 2)",
        "graph_mode": "on",
        "requested_mode": "detailed",
        "tier": "standard",
        "features_used": {"ocr_used": False, "voice_used": False}
    }
    
    response = requests.post(url, json=payload, stream=True)
    
    session_id = None
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                try:
                    data = json.loads(line_str[6:])
                    if data.get("type") == "meta":
                        session_id = data.get("session_id")
                        if session_id:
                            print(f"Captured Session ID: {session_id}")
                    if data.get("type") == "done":
                        print("Stream finished.")
                except:
                    pass
    
    if not session_id:
        print("Failed to capture session_id")
        return

    # Wait a bit for persistence
    time.sleep(2)
    
    print(f"Fetching session details for {session_id}...")
    details_url = f"http://localhost:8000/api/v1/sessions/{session_id}"
    details_resp = requests.get(details_url)
    details = details_resp.json()
    
    # Find the assistant message
    messages = details.get("messages", [])
    for msg in messages:
        if msg.get("role") == "assistant":
            structured_data = msg.get("structured_data", {})
            visuals = structured_data.get("visuals", {})
            should_visualize = visuals.get("should_visualize")
            print(f"should_visualize: {should_visualize}")
            print(f"decision_reason: {visuals.get('decision_reason')}")
            
            if should_visualize is True:
                print("SUCCESS: should_visualize is True")
            else:
                print("FAILURE: should_visualize is False")
            
            plots = visuals.get("plots", [])
            print(f"Number of plots: {len(plots)}")
            if plots:
                print(f"Plot 0 ID: {plots[0].get('plot_id')}")

if __name__ == "__main__":
    test_graph_mode_on()
