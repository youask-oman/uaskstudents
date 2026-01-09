
export const DEMO_SOLUTION = {
    "schema_version": "1.0",
    "meta": {
        "language": "en",
        "mode": "full",
        "problem_type": "algebra",
        "difficulty_estimate": "medium",
        "needs_clarification": false,
        "clarifying_questions": null,
        "assumptions": [
            "Solving over real numbers",
            "Principal root assumed for radical"
        ],
        "constraints": [
            "x >= -5 (domain of sqrt)",
            "x - 1 >= 0 (range of sqrt)"
        ],
        "detected_topics": [
            "Radical Equations",
            "Quadratic Equations",
            "Extraneous Solutions"
        ],
        "safety_notes": null
    },
    "problem": {
        "original_text": "sqrt(x+5) = x - 1",
        "normalized_text": "\\sqrt{x+5} = x - 1",
        "latex": "\\sqrt{x+5} = x - 1",
        "goal": "solve",
        "variables": ["x"],
        "parameters": []
    },
    "plan": [
        {
            "step": 1,
            "summary": "Isolate the radical",
            "method": "algebraic_manipulation",
            "why": "Standard approach for radical equations"
        },
        {
            "step": 2,
            "summary": "Square both sides",
            "method": "power_rule",
            "why": "To eliminate the square root, noting possible extraneous solutions"
        },
        {
            "step": 3,
            "summary": "Solve the resulting quadratic",
            "method": "factoring",
            "why": "To find candidate values for x"
        },
        {
            "step": 4,
            "summary": "Verify candidates",
            "method": "substitution",
            "why": "Mandatory check for extraneous roots introduced by squaring"
        }
    ],
    "solution": {
        "steps": [
            {
                "index": 1,
                "title": "State Domain Constraints",
                "explanation": "For the square root $\\sqrt{x+5}$ to be defined over real numbers, the radicand must be non-negative. Also, since the square root output is non-negative, the right hand side $x-1$ must also be non-negative.",
                "math": {
                    "latex_lines": [
                        "x + 5 \\ge 0 \\implies x \\ge -5",
                        "x - 1 \\ge 0 \\implies x \\ge 1",
                        "\\text{Combined Domain: } x \\ge 1"
                    ],
                    "plain_lines": [
                        "x >= -5",
                        "x >= 1"
                    ]
                },
                "step_type": "domain",
                "common_pitfalls": [
                    "Ignoring the RHS constraint often leads to accepting extraneous solutions."
                ]
            },
            {
                "index": 2,
                "title": "Square Both Sides",
                "explanation": "Square both sides of the equation to eliminate the radical. Note that this step is irreversible and may introduce extraneous solutions.",
                "math": {
                    "latex_lines": [
                        "(\\sqrt{x+5})^2 = (x - 1)^2",
                        "x + 5 = x^2 - 2x + 1"
                    ],
                    "plain_lines": [
                        "x + 5 = x^2 - 2x + 1"
                    ]
                },
                "step_type": "transform",
                "common_pitfalls": []
            },
            {
                "index": 3,
                "title": "Rearrange into Standard Quadratic Form",
                "explanation": "Move all terms to one side to set the equation to zero.",
                "math": {
                    "latex_lines": [
                        "0 = x^2 - 2x - x + 1 - 5",
                        "x^2 - 3x - 4 = 0"
                    ],
                    "plain_lines": [
                        "x^2 - 3x - 4 = 0"
                    ]
                },
                "step_type": "simplify",
                "common_pitfalls": ["Sign errors when transposing terms."]
            },
            {
                "index": 4,
                "title": "Solve for x",
                "explanation": "Factor the quadratic equation $x^2 - 3x - 4 = 0$. We look for two numbers that multiply to -4 and add to -3.",
                "math": {
                    "latex_lines": [
                        "(x - 4)(x + 1) = 0",
                        "x - 4 = 0 \\implies x = 4",
                        "x + 1 = 0 \\implies x = -1"
                    ],
                    "plain_lines": [
                        "x = 4",
                        "x = -1"
                    ]
                },
                "step_type": "compute",
                "common_pitfalls": []
            }
        ],
        "result": {
            "final_answer_exact": "x = 4",
            "final_answer_latex": "x = 4",
            "final_answer_approx": null,
            "solution_set": {
                "type": "single",
                "elements": ["4"],
                "intervals": null,
                "conditions": []
            },
            "domain_restrictions": ["x >= 1"],
            "extraneous_solutions_removed": ["-1"],
            "units": {
                "enabled": false,
                "notes": null
            }
        }
    },
    "verification": {
        "status": "pass",
        "methods_used": [
            {
                "method": "substitution",
                "description": "Substitute candidates back into the original equation.",
                "work": {
                    "latex_lines": [
                        "\\textbf{Check } x = 4:",
                        "\\text{LHS} = \\sqrt{4+5} = \\sqrt{9} = 3",
                        "\\text{RHS} = 4 - 1 = 3",
                        "\\text{LHS} = \\text{RHS} \\implies \\text{Valid}",
                        "",
                        "\\textbf{Check } x = -1:",
                        "\\text{LHS} = \\sqrt{-1+5} = \\sqrt{4} = 2",
                        "\\text{RHS} = -1 - 1 = -2",
                        "2 \\neq -2 \\implies \\text{Invalid (Extraneous)}"
                    ],
                    "plain_lines": [
                        "Check x=4: 3=3 (Valid)",
                        "Check x=-1: 2!=-2 (Invalid)"
                    ]
                },
                "conclusion": "Only x=4 is a valid solution."
            }
        ],
        "warnings": []
    },
    "visualization": {
        "included": true,
        "reason": "Intersection of functions helps visualize the solution and extraneous root.",
        "plots": [
            {
                "plot_id": "P1",
                "plot_type": "function",
                "title": "Intersection of y = sqrt(x+5) and y = x - 1",
                "expressions": ["y = \\sqrt{x+5}", "y = x - 1"],
                "variables": ["x", "y"],
                "domain_window": {
                    "x_min": -6,
                    "x_max": 10,
                    "y_min": -5,
                    "y_max": 10,
                    "notes": "Focus on intersection at x=4"
                },
                "key_features": {
                    "intercepts": [
                        { "x": "4", "y": "3", "type": "intersection" }
                    ],
                    "critical_points": [],
                    "inflection_points": [],
                    "asymptotes": [],
                    "discontinuities": [],
                    "symmetry": [],
                    "notes": []
                },
                "point_table": [],
                "interpretation": "The graphs intersect at exactly one point (4, 3). The line y=x-1 is below the x-axis at x=-1, while the square root function is continually positive, confirming why x=-1 is extraneous."
            }
        ]
    },
    "practice": {
        "next_steps": [
            "Practice more radical equations with variables on both sides.",
            "Review quadratic factoring."
        ],
        "similar_problems": [
            {
                "difficulty": "easy",
                "prompt": "\\sqrt{2x+3} = 5",
                "why": "Simpler radical equation."
            },
            {
                "difficulty": "medium",
                "prompt": "\\sqrt{3x+1} = x - 3",
                "why": "Similar structure, likely to have extraneous solutions."
            }
        ]
    },
    "quality_checks": {
        "domain_checked": true,
        "extraneous_checked": true,
        "result_simplified": true,
        "verification_performed": true,
        "graph_considered": true,
        "schema_valid": true,
        "notes": []
    }
};
