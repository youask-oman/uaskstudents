import {
  buildExportHtml,
  exportCanvasToPdf,
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
  afterEach(() => {
    jest.restoreAllMocks();
    document.body.innerHTML = "";
  });

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

  test("exports to popup when available", () => {
    const popupDocument = {
      open: jest.fn(),
      write: jest.fn(),
      close: jest.fn(),
    };
    const popup = { document: popupDocument } as unknown as Window;
    const openSpy = jest.spyOn(window, "open").mockReturnValue(popup);

    exportCanvasToPdf(payload);

    expect(openSpy).toHaveBeenCalledWith("", "_blank", "noopener,noreferrer");
    expect(popupDocument.open).toHaveBeenCalledTimes(1);
    expect(popupDocument.write).toHaveBeenCalledTimes(1);
    expect(popupDocument.close).toHaveBeenCalledTimes(1);
  });

  test("falls back to hidden iframe when popup is blocked", () => {
    jest.spyOn(window, "open").mockReturnValue(null);

    expect(() => exportCanvasToPdf(payload)).not.toThrow();

    const frame = document.querySelector("iframe[aria-hidden='true']") as HTMLIFrameElement | null;
    expect(frame).not.toBeNull();
    expect(frame?.srcdoc).toContain("Step-by-step Solution");
  });
});
