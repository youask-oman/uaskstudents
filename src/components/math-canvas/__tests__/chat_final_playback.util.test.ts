import { resolvePlaybackFromMessage, stripProtocolMarkers } from "@/lib/chat_final_playback";
import type { SessionMessage } from "@/components/math-canvas/types";

describe("chat_final_playback resolver", () => {
  test("chooses structured_data.solutions steps before synthesized sections", () => {
    const msg: SessionMessage = {
      id: 108,
      role: "assistant",
      content: "0.9513",
      structured_data: {
        raw_user_extraction: {
          sections: [
            {
              heading: "Question Q1",
              steps: [{ index: 1, blocks: [{ kind: "text", content: "BROKEN SECTION LINE" }] }],
            },
          ],
        },
        solutions: [
          {
            question_id: "q1",
            steps: [
              { index: 1, title: "Step 1", explanation: "Use Bayes theorem." },
              { index: 2, title: "Step 2", explanation: "Compute posterior probability." },
            ],
            final_answer: { answer_latex: "\\boxed{0.3896}", answer_text: "0.3896" },
          },
        ],
      },
    };

    const resolved = resolvePlaybackFromMessage(msg);

    expect(resolved.source).toBe("solutions_steps");
    expect(resolved.content).toContain("Use Bayes theorem.");
    expect(resolved.content).toContain("\\boxed{0.3896}");
    expect(resolved.content).not.toContain("BROKEN SECTION LINE");
  });

  test("strips protocol markers", () => {
    const clean = stripProtocolMarkers("BEGIN_SOLUTION begin_steps Step 1 END_STEPS end_solution");
    expect(clean).toBe("Step 1");
  });

  test("uses solutions final_answer and does not append global_final_answer", () => {
    const msg: SessionMessage = {
      id: "m1",
      role: "assistant",
      content: "x",
      structured_data: {
        global_final_answer: "2*0.03",
        solutions: [
          {
            question_id: "q2",
            steps: [{ index: 1, explanation: "Posterior after two positives." }],
            final_answer: { answer_latex: "\\boxed{0.9513}", answer_text: "0.9513" },
          },
        ],
      },
    };

    const resolved = resolvePlaybackFromMessage(msg);
    expect(resolved.content).toContain("\\boxed{0.9513}");
    expect(resolved.content).not.toContain("2*0.03");
  });
});

