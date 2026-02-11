# OpenAI API Payload Preview
**Generated for:** `Solve request`
**Problem:** `Find the value(s) of x that satisfy the linear equation 3(x - 2) = 15`
**Model:** `gpt-5-mini` (or `gpt-5-mini`)
**Mode:** `Strict JSON Schema`

---

## 1. System Prompt
*(Loaded from `solver_system.txt`, Version: v3)*

```text
OUTPUT FORMAT: Return ONLY strict JSON that validates against the schema.

SCHEMA COMPLIANCE (STRICT):
- Include every property defined in the schema (even if empty).
- Never use null; use empty arrays/strings or minimal objects with required keys.
- Always include plot.plan; if no meaningful plot exists, set should_plot=false, plot_type="other", use safe placeholder values in plan, and include visualization_alternative with clear instructions.

GRAPHING REQUIREMENT (NON-NEGOTIABLE):
1) Always compute whether a meaningful visualization exists.
2) If yes, set plot.should_plot = true and provide plot.plan with:
   - plot_type: function | implicit | parametric | inequality_region | system | scatter | histogram | boxplot | number_line | geometry | complex_plane | other
   - recommended_window (x/y bounds)
   - domain restrictions and discontinuities (if any)
   - key features to annotate (intercepts, vertex, asymptotes, turning points, intersections, endpoints)
   - sampling strategy (step size / resolution)
3) If no, set plot.should_plot = false, and provide plot.visualization_alternative with a clear diagram/number-line plan.

PEDAGOGY REQUIREMENT:
- Each major section must include: concept, rule/formula, and why it works.
- Include common mistakes and a quick checkpoint question after critical steps.

VERIFICATION REQUIREMENT:
- Provide at least 2 verification methods (e.g., substitution, expansion, inverse operation check, derivative check, numerical check, graph intersection check).
- If only one verification is possible, explain why and include at least one numeric sanity check.

ROBUSTNESS:
- Handle: equations, inequalities, systems, word problems, functions, calculus, vectors, complex numbers, statistics.
- For word problems: define variables, translate to equations, solve, interpret units and meaning.

STRICT JSON COMPLIANCE:
- The schema enforces "additionalProperties: false" and ALL fields are required.
- Do NOT output null for any field.
- If a field is optional but required by schema, provide a minimal valid value:
  - Empty string "" for text
  - Empty list [] for arrays
  - Minimal valid object for nested objects (e.g. {"x":0, "y":0} if point required but irrelevant)
- Do NOT omit any keys defined in the schema.
- Avoid nulls; when a field is required by the schema, supply a minimal valid value (empty list/string/object with required keys) instead of null
```

---

## 2. User Message
*(Constructed dynamically with Student Context)*

```text
Problem: Find the value(s) of x that satisfy the linear equation 3(x - 2) = 15

Context: 

[STUDENT CONTEXT - Trusted metadata, adapt to local conventions]
Grade Level: Grade 10
Location: CA, USA
Curriculum: California Common Core State Standards

NOTE: Use appropriate units (metric for Canada, customary for USA), spelling conventions, and grade-appropriate terminology.

**CRITICAL**: Return ONLY strictly valid JSON matching the schema. Include:
- At least 2 verification methods whenever possible
- plot.should_plot = true for any graphable content
- At least 2 similar_examples for practice
- meta.localization.region = "north_america"
- Each step must include: concept, rules_used, work, result, checkpoint
- Avoid nulls; when a field is required by the schema, supply a minimal valid value (empty list/string/object with required keys) instead of null
```

---

## 3. JSON Schema (Response Format)
*(Loaded from `solver_developer.txt`, Version: v3)*
*(Note: Passed to OpenAI as `response_format: { type: "json_schema", json_schema: { strict: true, schema: ... } }`)*

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/na-math-solver.schema.json",
  "title": "NorthAmericaMathSolverOutput",
  "description": "All properties must be present; do not use nulls. Use empty arrays/strings or minimal objects with required keys when data is unavailable.",
  "type": "object",
  "additionalProperties": false,
  "required": ["problem", "analysis", "solution", "verification", "plot", "similar_examples", "meta"],

  "properties": {
    "problem": {
      "type": "object",
      "additionalProperties": false,
      "required": ["input", "topic", "goal"],
      "properties": {
        "input": { "type": "string", "minLength": 1 },
        "topic": {
          "type": "string",
          "enum": [
            "algebra",
            "functions",
            "graphing",
            "geometry",
            "trigonometry",
            "calculus",
            "linear_algebra",
            "complex_numbers",
            "statistics_probability",
            "discrete",
            "word_problem",
            "other"
          ]
        },
        "goal": { "type": "string", "minLength": 1 },
        "assumptions": { "type": "array", "items": { "type": "string" } },
        "given_data": { "type": "array", "items": { "type": "string" } },
        "unknowns": { "type": "array", "items": { "type": "string" } }
      }
    },

    "analysis": {
      "type": "object",
      "additionalProperties": false,
      "required": ["plan", "detected_entities"],
      "properties": {
        "plan": { "type": "array", "minItems": 1, "items": { "type": "string" } },
        "detected_entities": {
          "type": "object",
          "additionalProperties": false,
          "required": ["expressions", "equations", "functions", "constraints"],
          "properties": {
            "expressions": { "type": "array", "items": { "type": "string" } },
            "equations": { "type": "array", "items": { "type": "string" } },
            "functions": { "type": "array", "items": { "type": "string" } },
            "constraints": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },

    "solution": {
      "type": "object",
      "additionalProperties": false,
      "required": ["final_answer", "final_forms", "steps", "key_concepts", "common_mistakes"],
      "properties": {
        "final_answer": { "type": "string", "minLength": 1 },

        "final_forms": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "simplified": { "type": "string" },
            "factored": { "type": "string" },
            "vertex_form": { "type": "string" },
            "standard_form": { "type": "string" },
            "general_solution_set": { "type": "string" }
          }
        },

        "steps": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["index", "title", "concept", "rules_used", "work", "result", "checkpoint"],
            "properties": {
              "index": { "type": "integer", "minimum": 1 },
              "title": { "type": "string" },
              "concept": { "type": "string", "minLength": 1 },
              "rules_used": {
                "type": "array",
                "minItems": 1,
                "items": { "type": "string" }
              },
              "work": {
                "type": "array",
                "minItems": 1,
                "items": { "type": "string" }
              },
              "result": { "type": "string", "minLength": 1 },
              "checkpoint": {
                "type": "object",
                "additionalProperties": false,
                "required": ["question", "expected_answer"],
                "properties": {
                  "question": { "type": "string" },
                  "expected_answer": { "type": "string" }
                }
              }
            }
          }
        },

        "key_concepts": { "type": "array", "items": { "type": "string" } },
        "common_mistakes": { "type": "array", "items": { "type": "string" } },

        "features": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "intercepts": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "x": { "type": "array", "items": { "$ref": "#/$defs/point" } },
                "y": { "$ref": "#/$defs/point" }
              }
            },
            "vertex": { "$ref": "#/$defs/point" },
            "axis_of_symmetry": { "type": "string" },
            "asymptotes": { "type": "array", "items": { "type": "string" } },
            "turning_points": { "type": "array", "items": { "$ref": "#/$defs/point" } },
            "domain": { "type": "string" },
            "range": { "type": "string" },
            "units": { "type": "string" }
          }
        }
      }
    },

    "verification": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["method", "why_it_works", "steps", "conclusion"],
        "properties": {
          "method": { "type": "string" },
          "why_it_works": { "type": "string" },
          "steps": { "type": "array", "minItems": 1, "items": { "type": "string" } },
          "conclusion": { "type": "string" }
        }
      }
    },

    "plot": {
      "type": "object",
      "additionalProperties": false,
      "required": ["should_plot", "plot_type", "plan"],
      "properties": {
        "should_plot": { "type": "boolean" },

        "plot_type": {
          "type": "string",
          "enum": [
            "function",
            "implicit",
            "parametric",
            "system",
            "inequality_region",
            "number_line",
            "geometry",
            "complex_plane",
            "scatter",
            "histogram",
            "boxplot",
            "other"
          ]
        },

        "plan": {
          "type": "object",
          "additionalProperties": false,
          "required": ["title", "axes", "recommended_window", "objects", "annotations", "sampling"],
          "properties": {
            "title": { "type": "string" },

            "axes": {
              "type": "object",
              "additionalProperties": false,
              "required": ["x_label", "y_label"],
              "properties": {
                "x_label": { "type": "string" },
                "y_label": { "type": "string" }
              }
            },

            "recommended_window": {
              "type": "object",
              "additionalProperties": false,
              "required": ["x_min", "x_max", "y_min", "y_max"],
              "properties": {
                "x_min": { "type": "number" },
                "x_max": { "type": "number" },
                "y_min": { "type": "number" },
                "y_max": { "type": "number" }
              }
            },

            "objects": {
              "type": "array",
              "minItems": 1,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["kind", "expression", "label"],
                "properties": {
                  "kind": {
                    "type": "string",
                    "enum": ["curve", "region", "points", "line", "vector", "shape"]
                  },
                  "expression": { "type": "string" },
                  "label": { "type": "string" },
                  "style_hints": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                      "dashed": { "type": "boolean" },
                      "shade": { "type": "boolean" }
                    }
                  }
                }
              }
            },

            "annotations": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["name", "detail"],
                "properties": {
                  "name": { "type": "string" },
                  "detail": { "type": "string" },
                  "point": { "$ref": "#/$defs/point" }
                }
              }
            },

            "sampling": {
              "type": "object",
              "additionalProperties": false,
              "required": ["strategy", "resolution"],
              "properties": {
                "strategy": {
                  "type": "string",
                  "enum": ["uniform", "adaptive", "piecewise", "grid"]
                },
                "resolution": { "type": "integer", "minimum": 50 },
                "domain_restrictions": { "type": "array", "items": { "type": "string" } },
                "discontinuities": { "type": "array", "items": { "type": "string" } }
              }
            }
          }
        },

        "visualization_alternative": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "type": { "type": "string" },
            "reason_no_standard_plot": { "type": "string" },
            "instructions": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },

    "similar_examples": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["problem", "key_idea", "short_solution"],
        "properties": {
          "problem": { "type": "string" },
          "key_idea": { "type": "string" },
          "short_solution": { "type": "string" }
        }
      }
    },

    "meta": {
      "type": "object",
      "additionalProperties": false,
      "required": ["confidence", "localization", "rounding_policy"],
      "properties": {
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "localization": {
          "type": "object",
          "additionalProperties": false,
          "required": ["region", "notation"],
          "properties": {
            "region": { "type": "string", "enum": ["north_america"] },
            "notation": { "type": "string", "enum": ["standard"] }
          }
        },
        "rounding_policy": { "type": "string" }
      }
    }
  },

  "$defs": {
    "point": {
      "type": "object",
      "additionalProperties": false,
      "required": ["x", "y"],
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" }
      }
    }
  }
}
```
