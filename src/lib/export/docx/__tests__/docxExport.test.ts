
import { buildDocxFromPayload } from "../buildDocxFromPayload";
import { docxToBuffer } from "../docxToBuffer";
import type { ExportSolutionPayload } from "../validate";

// We might need to mock latexToPng if playwright is flaky in this env
// But for now let's try real execution if possible, or mock it.
// To ensure stability and speed, we mock latexToPng logic.
jest.mock("../latexToPng", () => ({
    latexToPng: async (_latex: string) => {
        // Return a 1x1 png buffer mock
        const mockPng = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAFhAJ/wlseKgAAAABJRU5ErkJggg==", "base64");
        return { png: mockPng, width: 10, height: 10 };
    }
}));

describe("DOCX Export Logic", () => {
    it("builds a docx buffer from payload", async () => {
        const payload: ExportSolutionPayload = {
            docTitle: "Test Solution",
            createdAtISO: new Date().toISOString(),
            pages: [
                {
                    pageTitle: "Page 1 - Analysis",
                    blocks: [
                        {
                            type: "problem",
                            title: "Problem Statement",
                            body: "Solve for x",
                            math: ["x^2 + 2x + 1 = 0"]
                        },
                        {
                            type: "step",
                            k: 1,
                            title: "Factorize",
                            body: "We can factor the quadratic equation.",
                            math: ["(x+1)^2 = 0"]
                        },
                        {
                            type: "final",
                            label: "Final Answer",
                            body: "The solution is:",
                            math: ["x = -1"]
                        },
                        {
                            type: "note",
                            body: "Check verification steps."
                        }
                    ]
                }
            ]
        };

        const doc = await buildDocxFromPayload(payload);
        const buffer = await docxToBuffer(doc);

        expect(buffer).toBeDefined();
        expect(buffer.length).toBeGreaterThan(100); // Empty doc is usually larger
    });

    it("handles complex payloads with multiple steps and math", async () => {
        const payload: ExportSolutionPayload = {
            docTitle: "Complex Matrix",
            createdAtISO: new Date().toISOString(),
            pages: [{
                pageTitle: "Matrix Ops",
                blocks: [
                    {
                        type: "step",
                        k: 1,
                        title: "Invert Matrix",
                        body: "Using Gaussian elimination",
                        math: ["\\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}"]
                    }
                ]
            }]
        };

        const doc = await buildDocxFromPayload(payload);
        const buffer = await docxToBuffer(doc);
        expect(buffer.length).toBeGreaterThan(500);
    });
});
