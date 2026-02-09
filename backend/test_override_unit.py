"""
Unit test for apply_graph_mode_override - NO API CALLS
This tests the override logic directly.
"""

from app.services.plot_integration import apply_graph_mode_override

# Simulate LLM response where should_visualize is False
llm_response = {
    "schema_version": "v1",
    "problem": {"original_text": "line (-1, 3), (2, -3)"},
    "steps": [{"index": 1, "title": "Step 1"}],
    "final_answer": {"answer_text": "y = -2x + 1"},
    "visuals": {
        "should_visualize": False,
        "decision_reason": "User did not request a graph and algebraic solution is sufficient",
        "plots": [],
        "alternative_visual": None
    }
}

print("=" * 60)
print("UNIT TEST: apply_graph_mode_override")
print("=" * 60)

# Test 1: graph_mode='on' should force should_visualize=True
print("\n--- TEST 1: graph_mode='on' ---")
print(f"BEFORE: should_visualize = {llm_response['visuals']['should_visualize']}")
print(f"BEFORE: decision_reason = {llm_response['visuals']['decision_reason']}")

result = apply_graph_mode_override(
    solve_result=llm_response.copy(),  # Use copy to avoid mutation
    graph_mode='on',
    plot_generated=False
)

print(f"AFTER: should_visualize = {result['visuals']['should_visualize']}")
print(f"AFTER: decision_reason = {result['visuals']['decision_reason']}")

if result['visuals']['should_visualize'] == True:
    print("✅ TEST 1 PASSED: should_visualize is True")
else:
    print("❌ TEST 1 FAILED: should_visualize should be True but is False")

# Test 2: graph_mode='off' should force should_visualize=False
print("\n--- TEST 2: graph_mode='off' ---")
llm_response_on = {
    "visuals": {
        "should_visualize": True,
        "decision_reason": "LLM wanted a graph",
        "plots": [{"plot_id": "test"}],
    }
}
result2 = apply_graph_mode_override(
    solve_result=llm_response_on.copy(),
    graph_mode='off',
    plot_generated=True
)
print(f"AFTER: should_visualize = {result2['visuals']['should_visualize']}")
if result2['visuals']['should_visualize'] == False:
    print("✅ TEST 2 PASSED: should_visualize is False")
else:
    print("❌ TEST 2 FAILED: should_visualize should be False")

# Test 3: graph_mode='auto' with plot_generated=True
print("\n--- TEST 3: graph_mode='auto' with plot_generated=True ---")
llm_response_auto = {
    "visuals": {
        "should_visualize": False,
        "decision_reason": "Initial",
        "plots": [],
    }
}
result3 = apply_graph_mode_override(
    solve_result=llm_response_auto.copy(),
    graph_mode='auto',
    plot_generated=True
)
print(f"AFTER: should_visualize = {result3['visuals']['should_visualize']}")
if result3['visuals']['should_visualize'] == True:
    print("✅ TEST 3 PASSED: should_visualize is True when plot was generated")
else:
    print("❌ TEST 3 FAILED: should_visualize should be True when plot was generated")

print("\n" + "=" * 60)
print("UNIT TESTS COMPLETE")
print("=" * 60)
