from app.services.intent import should_require_visual

test_queries = [
    "graph y=x^2",
    "plot the sine function",
    "draw a circle",
    "sketch the graph",
    "Find the equation of the line passing through the points (0,0) and (2,2)",
    "equation of the line through (1,2) and (3,4)",
    "solve 2x+3=7"
]

print("--- Testing Intent Triggers ---")
for q in test_queries:
    req, reason = should_require_visual(q)
    print(f"Query: {q}")
    print(f"  Required: {req}")
    if req:
        print(f"  Reason: {reason}")
    print("-" * 20)
