import { extractBatchSolutionsFromSessionMessages } from "@/components/math-canvas/normalizer";
import { DEMO_BATCH_MESSAGES } from "@/lib/mock-batch-session";

describe("chat batch normalizer", () => {
  it("extracts and sorts batch solutions while preserving question mapping", () => {
    const entries = extractBatchSolutionsFromSessionMessages(DEMO_BATCH_MESSAGES);
    expect(entries).toHaveLength(7);
    expect(entries.map((entry) => entry.questionId)).toEqual(["q1", "q2", "q3", "q4", "q5", "q6", "q7"]);
    expect(entries[0].questionText).toContain("sqrt(3x + 4) = 2");
    expect(entries[6].questionText).toContain("d/dx (x^3 * ln(x))");
    expect(entries[0].solution.finalAnswer?.answer_latex).toBe("x=0");
  });
});
