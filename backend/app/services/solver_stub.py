from __future__ import annotations
from typing import Dict, Any


def _stub_quadratic_solution() -> Dict[str, Any]:
    return {
        "steps": [
            {
                "index": 1,
                "title": "Factor the quadratic",
                "explanation": "Find two numbers that multiply to 6 and add to -5.",
                "math": {"latex_lines": ["x^2 - 5x + 6 = (x-2)(x-3)"]},
                "visual_refs": []
            },
            {
                "index": 2,
                "title": "Set each factor to zero",
                "explanation": "Solve (x-2)=0 and (x-3)=0.",
                "math": {"latex_lines": ["x-2=0 \\Rightarrow x=2", "x-3=0 \\Rightarrow x=3"]},
                "visual_refs": []
            }
        ],
        "final_answer": "x = 2 or x = 3"
    }


def get_stub_solution_v1(problem_text: str) -> Dict[str, Any]:
    return {
        "problem": {
            "goal": "Solve for x",
            "latex": problem_text
        },
        "solution": _stub_quadratic_solution(),
        "visuals": [],
        "response_intent": ["step_by_step"],
        "_model": "stub-v1"
    }


def get_stub_solution_v3(problem_text: str) -> Dict[str, Any]:
    return {
        "problem": {
            "input": problem_text,
            "topic": "algebra",
            "goal": "Solve for x",
            "assumptions": [],
            "given_data": [],
            "unknowns": ["x"]
        },
        "analysis": {
            "plan": ["Factor the quadratic", "Solve each factor"],
            "detected_entities": {
                "expressions": ["x^2 - 5x + 6"],
                "equations": ["x^2 - 5x + 6 = 0"],
                "functions": [],
                "constraints": []
            }
        },
        "solution": {
            "final_answer": "x = 2 or x = 3",
            "final_forms": {
                "factored": "(x-2)(x-3)=0",
                "general_solution_set": "{2, 3}"
            },
            "steps": [
                {
                    "index": 1,
                    "title": "Factor the quadratic",
                    "concept": "Factoring",
                    "rules_used": ["Product-sum method"],
                    "work": ["x^2 - 5x + 6 = (x-2)(x-3)"],
                    "result": "(x-2)(x-3)=0",
                    "checkpoint": {
                        "question": "What two numbers multiply to 6 and add to -5?",
                        "expected_answer": "2 and 3"
                    }
                },
                {
                    "index": 2,
                    "title": "Solve each factor",
                    "concept": "Zero product property",
                    "rules_used": ["If ab=0 then a=0 or b=0"],
                    "work": ["x-2=0", "x-3=0"],
                    "result": "x = 2 or x = 3",
                    "checkpoint": {
                        "question": "What are the two solutions?",
                        "expected_answer": "x=2 and x=3"
                    }
                }
            ],
            "key_concepts": ["Factoring", "Zero product property"],
            "common_mistakes": ["Sign errors when factoring"]
        },
        "verification": [
            {
                "method": "Substitution",
                "why_it_works": "Plugging solutions verifies the equation is satisfied.",
                "steps": ["2^2 - 5(2) + 6 = 0", "3^2 - 5(3) + 6 = 0"],
                "conclusion": "Both solutions satisfy the equation."
            },
            {
                "method": "Graph check",
                "why_it_works": "Roots are x-intercepts of the parabola.",
                "steps": ["Confirm parabola crosses x-axis at x=2 and x=3."],
                "conclusion": "Graph aligns with solutions."
            }
        ],
        "plot": {
            "should_plot": False,
            "plot_type": "function",
            "plan": {
                "title": "Quadratic roots",
                "axes": {"x_label": "x", "y_label": "y"},
                "recommended_window": {"x_min": -1, "x_max": 6, "y_min": -5, "y_max": 10},
                "objects": [
                    {"kind": "curve", "expression": "y=x^2-5x+6", "label": "y=x^2-5x+6"}
                ],
                "annotations": [
                    {"name": "root_2", "detail": "x=2", "point": {"x": 2.0, "y": 0.0}},
                    {"name": "root_3", "detail": "x=3", "point": {"x": 3.0, "y": 0.0}}
                ],
                "sampling": {"strategy": "uniform", "resolution": 200}
            }
        },
        "similar_examples": [
            {
                "problem": "Solve x^2 - 7x + 12 = 0",
                "key_idea": "Factor into two binomials",
                "short_solution": "x^2 - 7x + 12 = (x-3)(x-4)"
            },
            {
                "problem": "Solve x^2 - 4x + 3 = 0",
                "key_idea": "Find numbers that multiply to 3 and add to -4",
                "short_solution": "x^2 - 4x + 3 = (x-1)(x-3)"
            }
        ],
        "meta": {
            "confidence": 0.95,
            "localization": {"region": "north_america", "notation": "standard"},
            "rounding_policy": "Exact values for integers"
        },
        "_model": "stub-v3",
        "_validated": True,
        "_repaired": False
    }
