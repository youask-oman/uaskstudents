import { buildRenderModel } from "@/lib/chat_playback/buildRenderModel";

describe("buildRenderModel", () => {
  test("keeps non-null metadata/context and prunes null/empty", () => {
    const payload = {
      attempt_id: "att-1",
      tier: "STANDARD",
      schema_name: "youask_math_openai_detailed_v2",
      schema_version: "v2",
      response_language: "en",
      mode: "solve",
      request_id: "req-1",
      context: {
        country: "US",
        region: null,
        course: "",
      },
      items: [
        {
          question_text: "Solve x+1=2",
          question_summary: "",
          steps: [{ index: 1, title: "Step 1", blocks: [{ kind: "math", content: "x+1=2", display: true }] }],
          final_answer: { answer_text: "x=1", answer_latex: "x=1", values: [] },
          results: { task_results: [] },
          quality: { confidence: 0.9, assumptions: [], warnings: [] },
          refusal: { is_refusal: false, refusal_code: null, refusal_message: null },
        },
      ],
    } as unknown as Record<string, unknown>;

    const model = buildRenderModel(payload);
    expect(model.header.attempt_id).toBe("att-1");
    expect(model.context).toEqual({ country: "US" });
    expect(model.items[0]?.question.text).toBe("Solve x+1=2");
    expect(model.items[0]?.raw_non_null).toHaveProperty("question_text");
    expect(model.raw_non_null).not.toHaveProperty("context.region");
  });
});

