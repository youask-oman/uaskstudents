import {
  buildExportHtml,
  hasExportableSolution,
  suggestExportFileName,
  type SolutionExportPayload,
} from "@/components/math-canvas/export/exportDocument";

const payload: SolutionExportPayload = {
  solveId: "158",
  tier: "RESEARCH",
  generatedAt: "2026-02-03T21:30:00.000Z",
  pages: [
    {
      id: "page-1",
      title: "Identity",
      blocks: [
        { id: "rec-1", type: "recognition", latex: "\\(\\sin^2(x)+\\cos^2(x)=1\\)" },
        {
          id: "steps-1",
          type: "steps",
          steps: [
            { title: "Use Identity", explanation: "Apply \\(\\sin^2(x)+\\cos^2(x)=1\\)." },
            { title: "Conclude", mathLatex: "\\sin^2(x)+\\cos^2(x)=1" },
          ],
          result: "\\sin^2(x)+\\cos^2(x)=1",
          verificationChecks: [{ checkId: "check_1", verdict: "pass", message: "Holds for all real x." }],
        },
      ],
      elements: [],
    },
  ],
};

describe("math-canvas export layout", () => {
  test("detects exportable solve payload", () => {
    expect(hasExportableSolution(payload.pages)).toBe(true);
  });

  test("suggests deterministic filename", () => {
    expect(suggestExportFileName(payload, "pdf")).toBe("uask-solution-sin-2-x-cos-2-x-1-2026-02-03.pdf");
  });

  test("builds clean export HTML without action controls", () => {
    const html = buildExportHtml(payload);
    expect(html).toContain("Step-by-step Solution");
    expect(html).not.toContain("Edit");
    expect(html).not.toContain("Delete");
    expect(html).toMatchSnapshot();
  });
});
