/**
 * Mock response matching the full tttt.json schema
 * All fields are included, even when null
 */

export const DEMO_SOLUTION = {
    "schema_version": "v1",
    "refusal": {
        "is_refusal": false,
        "reason": null,
        "safe_alternative": null
    },
    "assumptions": [
        "Solving over real numbers",
        "Principal root assumed for radical",
        "Variable x is the unknown to solve for"
    ],
    "problem": {
        "original_text": "sqrt(x+5) = x - 1",
        "normalized_text": "\\sqrt{x+5} = x - 1",
        "language": "en",
        "detected_tasks": [
            "algebra",
            "equation_solving"
        ]
    },
    "classification": {
        "grade_band": "high_school",
        "domain": "algebra",
        "topic": "Radical equations; extraneous solutions",
        "difficulty": "medium"
    },
    "steps": [
        {
            "index": 1,
            "title": "State Domain Constraints",
            "explanation": "For the square root $\\sqrt{x+5}$ to be defined over real numbers, the radicand must be non-negative. Also, since the square root output is non-negative, the right hand side $x-1$ must also be non-negative.",
            "math_latex": [
                "x \\ge -5",
                "x \\ge 1",
                "\\text{Combined: } x \\ge 1"
            ],
            "rules_used": ["Radical Definition", "Non-negative Output"],
            "checks": ["Radicand ≥ 0", "RHS ≥ 0"],
            "plots_used": [],
            "notes": "Constraints are crucial for identifying extraneous solutions later."
        },
        {
            "index": 2,
            "title": "Square Both Sides",
            "explanation": "Square both sides of the equation to eliminate the radical. Note that this step is irreversible and may introduce extraneous solutions.",
            "math_latex": [
                "(\\sqrt{x+5})^2 = (x - 1)^2",
                "x + 5 = x^2 - 2x + 1"
            ],
            "rules_used": ["Power Rule"],
            "checks": [],
            "plots_used": [],
            "notes": null
        },
        {
            "index": 3,
            "title": "Rearrange into Standard Quadratic Form",
            "explanation": "Move all terms to one side to set the equation to zero.",
            "math_latex": [
                "0 = x^2 - 3x - 4"
            ],
            "rules_used": ["Algebraic Rearrangement"],
            "checks": ["Arithmetic verification"],
            "plots_used": [],
            "notes": null
        },
        {
            "index": 4,
            "title": "Solve for x",
            "explanation": "Factor the quadratic equation and apply the zero product property.",
            "math_latex": [
                "(x - 4)(x + 1) = 0",
                "x = 4 \\text{ or } x = -1"
            ],
            "rules_used": ["Zero Product Property", "Factoring"],
            "checks": [],
            "plots_used": [],
            "notes": null
        },
        {
            "index": 5,
            "title": "Verify Solutions Against Domain",
            "explanation": "Check each candidate solution against the domain constraint x ≥ 1 and by substitution into the original equation.",
            "math_latex": [
                "x = 4: \\sqrt{4+5} = 3, \\quad 4-1 = 3 \\quad \\checkmark",
                "x = -1: -1 \\not\\ge 1 \\quad \\text{(fails domain)}"
            ],
            "rules_used": ["Domain verification", "Substitution check"],
            "checks": ["x=4 passes", "x=-1 rejected"],
            "plots_used": [],
            "notes": "x = -1 is an extraneous solution introduced by squaring."
        }
    ],
    "final_answer": {
        "answer_text": "The only valid solution is x = 4. The candidate x = -1 is extraneous because it fails the domain constraint x ≥ 1 and does not satisfy the original equation when substituted back.",
        "answer_latex": "x_1'=x_2;\\;x_2'=-2\\zeta x_2 - x_1 - \\beta x_1^3 + \\gamma\\cos(\\omega t);\\;\\zeta=0.15;\\;\\beta=1;\\;\\omega=1\\\\\\text{Expected classification: }\\gamma=0.2:\\text{periodic};\\;\\gamma=0.3:\\text{period-doubling};\\;\\gamma=0.37:\\text{chaotic};\\;\\gamma=0.45:\\text{chaotic}",
        "values": [
            {
                "label": "valid_solution",
                "value": { "x": 4 },
                "value_latex": "x = 4"
            },
            {
                "label": "extraneous_solution",
                "value": { "x": -1 },
                "value_latex": "x = -1 \\text{ (rejected)}"
            }
        ],
        "units": null
    },
    "visuals": {
        "should_visualize": false,
        "decision_reason": "This algebraic problem does not require visualization.",
        "plots": [],
        "alternative_visual": {
            "kind": "none",
            "description": null,
            "data": []
        }
    },
    "verification": {
        "checks": [
            {
                "check_id": "Substitution Check",
                "verdict": "pass",
                "message": "x=4: √(4+5) = 3 and 4-1 = 3. Both sides equal, solution verified.",
                "evidence_math": ["\\sqrt{4+5} = 3", "4-1 = 3"]
            },
            {
                "check_id": "Domain Check",
                "verdict": "pass",
                "message": "x=4 satisfies x ≥ 1. The candidate x=-1 fails this constraint.",
                "evidence_math": ["4 \\ge 1 \\quad \\checkmark", "-1 \\not\\ge 1"]
            }
        ]
    },
    "quality": {
        "confidence": 0.98,
        "common_mistakes": [
            "Forgetting to restrict the domain (x ≥ 1) often leads to including x = -1 as a solution.",
            "Squaring individual terms instead of the entire side (e.g., x^2 - 1^2) is a common algebraic error.",
            "Not checking solutions by substitution back into the original equation."
        ],
        "warnings": []
    },
    "debug": {
        "tier": null,
        "mode": null,
        "llm_provider": null,
        "model": null,
        "request_id": null,
        "latency_ms": null
    },
    "_raw_llm_output": null
};

/**
 * Complex example with long LaTeX that tests the layout engine
 * Based on the Duffing oscillator from tttt.json
 */
export const DEMO_SOLUTION_COMPLEX = {
    "schema_version": "v1",
    "refusal": {
        "is_refusal": false,
        "reason": null,
        "safe_alternative": null
    },
    "assumptions": [
        "Numerical integration uses a variable-step, high-order integrator (explicit Runge-Kutta Dormand–Prince RK45 or similar) with tight tolerances (1e-9 abs, 1e-9 rel) unless stated otherwise.",
        "Initial condition for time series is x(0)=0.1, x'(0)=0 for all runs; transients removed by discarding the first 200 forcing periods.",
        "Time horizon per run is 400 forcing periods unless otherwise stated; sampling timestep for dense time series is at least 200 points per forcing period.",
        "Poincaré sampling uses strobing at t_k = 2\\pi k/\\omega with interpolation to align integrator outputs to section times.",
        "Bifurcation sweep uses 501 evenly spaced gamma values in [0.10,0.60], collecting 200 post-transient Poincaré points per gamma."
    ],
    "problem": {
        "original_text": "Nonlinear Dynamics: Duffing Oscillator (Chaos + Bifurcation + Poincaré)\nTopic: ODEs, nonlinear dynamics, numerical integration, chaos diagnostics.\n\nProblem:\nConsider the forced, damped Duffing oscillator\n  x'' + 2ζ x' + x + β x^3 = γ cos(ω t),\nwith parameters ζ = 0.15, β = 1, ω = 1. Treat γ as a control parameter.",
        "normalized_text": "Study the forced damped Duffing oscillator x'' + 2ζ x' + x + β x^3 = γ cos(ω t) with ζ=0.15, β=1, ω=1. Treat γ in [0.10,0.60]. Numerically integrate for selected γ values {0.2,0.3,0.37,0.45}, plot time series, phase portraits, and Poincaré sections sampled at period 2π/ω; then sweep γ to produce a bifurcation diagram and optionally compute the largest Lyapunov exponent vs γ. Classify regimes (periodic, quasi-periodic, chaotic) and identify period-doubling cascades and windows.",
        "language": "en",
        "detected_tasks": [
            "differential_equations",
            "numerical_analysis",
            "dynamical_systems",
            "bifurcation",
            "plot"
        ]
    },
    "classification": {
        "grade_band": "college_intro",
        "domain": "dynamical_systems",
        "topic": "Duffing oscillator; chaos; Poincaré section; bifurcation",
        "difficulty": "hard"
    },
    "steps": [
        {
            "index": 1,
            "title": "Convert to first-order system and state parameters",
            "explanation": "Rewrite the second-order Duffing equation as a first-order system to prepare for numerical integration and variational equations for Lyapunov computation.",
            "math_latex": [
                "x_1 = x",
                "x_2 = x'",
                "x_1' = x_2",
                "x_2' = -2\\zeta x_2 - x_1 - \\beta x_1^3 + \\gamma \\cos(\\omega t)",
                "\\zeta = 0.15, \\beta = 1, \\omega = 1"
            ],
            "rules_used": [
                "state-space formulation",
                "ODE existence and uniqueness"
            ],
            "checks": [
                "Dimensions: one second-order → two first-order variables"
            ],
            "plots_used": [],
            "notes": null
        },
        {
            "index": 2,
            "title": "Select integrator, tolerances, and initial condition",
            "explanation": "Choose an adaptive, non-stiff integrator (RK45 Dormand–Prince) with tight tolerances to avoid numerical artifacts that mimic chaos.",
            "math_latex": [
                "\\text{Use RK45 with reltol}=10^{-9},\\;\\text{abstol}=10^{-9}",
                "x(0)=0.1,\\;x'(0)=0",
                "T_{period}=2\\pi/\\omega = 2\\pi"
            ],
            "rules_used": [
                "adaptive Runge-Kutta",
                "sampling theorem"
            ],
            "checks": [
                "Ensure at least 200 samples per forcing period"
            ],
            "plots_used": [],
            "notes": null
        }
    ],
    "final_answer": {
        "answer_text": "Procedure and expected qualitative findings: with ζ=0.15, β=1, ω=1 and IC x(0)=0.1, x'(0)=0, expect γ=0.2 periodic, γ=0.3 near period-doubling/quasi-periodic behavior, γ=0.37 typically in or near a chaotic band (dense Poincaré scatter and positive LCE), and γ=0.45 often chaotic. The bifurcation diagram over γ∈[0.10,0.60] should show period-doubling cascades to chaos with embedded periodic windows. Follow the provided numerical recipe and robustness checks to reproduce plots and Lyapunov estimates.",
        "answer_latex": "x_1'=x_2,\\;x_2'=-2\\zeta x_2 - x_1 - \\beta x_1^3 + \\gamma\\cos(\\omega t);\\;\\zeta=0.15,\\;\\beta=1,\\;\\omega=1\\\\\\text{Expected classification: }\\gamma=0.2:\\text{periodic};\\;\\gamma=0.3:\\text{period-doubling/quasi-periodic};\\;\\gamma=0.37:\\text{chaotic};\\;\\gamma=0.45:\\text{chaotic}",
        "values": [
            {
                "label": "IC_and_parameters",
                "value": {
                    "x0": 0.1,
                    "v0": 0,
                    "zeta": 0.15,
                    "beta": 1,
                    "omega": 1
                },
                "value_latex": "x(0)=0.1,\\;x'(0)=0,\\;\\zeta=0.15,\\;\\beta=1,\\;\\omega=1"
            },
            {
                "label": "time_settings",
                "value": {
                    "period": 6.283185307179586,
                    "T_total_periods": 400,
                    "T_transient_periods": 200,
                    "samples_per_period": 200
                },
                "value_latex": "T_{period}=2\\pi,\\;T_{total}=400\\cdot2\\pi,\\;T_{transient}=200\\cdot2\\pi"
            },
            {
                "label": "bifurcation_sweep",
                "value": {
                    "gamma_range": [0.1, 0.6],
                    "ngamma": 501,
                    "poincare_points_per_gamma": 200
                },
                "value_latex": "\\gamma\\in[0.10,0.60],\\;N_{\\gamma}=501,\\;N_{poincare}=200"
            },
            {
                "label": "lyapunov_settings",
                "value": {
                    "method": "Benettin",
                    "perturbation": 1e-8,
                    "periods_for_estimate": 2000
                },
                "value_latex": "\\text{Benettin algorithm},\\;\\|\\delta(0)\\|=10^{-8},\\;N_{periods}=2000"
            }
        ],
        "units": null
    },
    "visuals": {
        "should_visualize": false,
        "decision_reason": "User requested plots but this JSON response supplies a reproducible recipe and expected qualitative results; plots are not embedded here.",
        "plots": [],
        "alternative_visual": {
            "kind": "instructions",
            "description": "Provide reproducible plotting recipe and settings for generating time series, phase portraits, Poincaré sections, and bifurcation diagrams using the specified integrator, tolerances, and sampling; optionally compute Lyapunov exponents via the Benettin method.",
            "data": []
        }
    },
    "verification": {
        "checks": []
    },
    "quality": {
        "confidence": 0.9,
        "common_mistakes": [
            "Using too-large integrator tolerances or timestep, producing numerical chaos artifacts.",
            "Insufficient transient removal that mixes transient dynamics with attractor sampling.",
            "Too-coarse γ resolution in the sweep, missing narrow periodic windows or bifurcation points.",
            "Failure to interpolate when strobing for Poincaré sections, causing phase misalignment.",
            "Estimating Lyapunov exponents with too-short integration time or without reorthonormalization, giving unreliable signs."
        ],
        "warnings": []
    },
    "debug": {
        "tier": null,
        "mode": null,
        "llm_provider": null,
        "model": null,
        "request_id": null,
        "latency_ms": null
    },
    "_raw_llm_output": null
};
