import { buildStandardEventsFromStructuredData } from "@/lib/chat_playback/buildStandardEventsFromStructured";

describe("buildStandardEventsFromStructuredData", () => {
  test("omits optional sections when fields are null or empty", () => {
    const payload = {
      schema_name: "youask_math_openai_detailed_v2",
      context: {
        country: null,
        region: "",
      },
      items: [
        {
          question_text: "Solve x+1=2",
          question_summary: null,
          tasks: [],
          steps: [],
          results: { task_results: [] },
          final_answer: { answer_text: "x=1", answer_latex: null, values: [] },
          plot: { should_visualize: true, recipe: null, python_code: "" },
          quality: { assumptions: [], warnings: [], confidence: null },
        },
      ],
    } as unknown as Record<string, unknown>;

    const events = buildStandardEventsFromStructuredData(payload, "attempt-1");
    const types = events.map((e) => e.type);
    expect(types).not.toContain("CONTEXT_SET");
    expect(types).not.toContain("VERIFICATION_SET");
    expect(types).not.toContain("PYTHON_CODE_SHOW");
    expect(types).not.toContain("PLOT_SHOW");
  });

  test("deterministic timeline for same attempt seed", () => {
    const payload = {
      items: [
        {
          question_text: "Find derivative of x^2",
          steps: [{ index: 1, title: "Differentiate", blocks: [{ kind: "text", content: "Use power rule." }] }],
        },
      ],
    } as unknown as Record<string, unknown>;

    const a = buildStandardEventsFromStructuredData(payload, "same-attempt");
    const b = buildStandardEventsFromStructuredData(payload, "same-attempt");
    expect(a.map((e) => e.at_ms)).toEqual(b.map((e) => e.at_ms));
    expect(a.map((e) => e.type)).toEqual(b.map((e) => e.type));
  });
});

