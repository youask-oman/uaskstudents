/**
 * @jest-environment node
 */

import { renderHtmlFromPayload } from "../renderHtmlFromPayload";
import { renderPdf } from "../renderPdf";
import type { ExportSolutionPayload } from "../../docx/validate";
import fs from "fs";
import path from "path";

describe("PDF Export Logic", () => {
    // Increase timeout for Playwright
    jest.setTimeout(30000);

    const testPayload: ExportSolutionPayload = {
        docTitle: "Advanced Calculus Solution",
        subtitle: "Unit 4: Integration Techniques",
        createdAtISO: new Date().toISOString(),
        pages: [
            {
                pageTitle: "Problem & Initial Analysis",
                blocks: [
                    {
                        type: "problem",
                        title: "Definite Integral",
                        body: "Evaluate the following definite integral using substitution and partial fractions if necessary.",
                        math: ["\\int_{0}^{\\pi} \\frac{\\sin(x)}{1 + \\cos^2(x)} dx"]
                    }
                ]
            },
            {
                pageTitle: "Step-by-Step Solution",
                blocks: [
                    {
                        type: "step",
                        k: 1,
                        title: "Substitution",
                        body: "Let $u = \\cos(x)$. Then $du = -\\sin(x)dx$. Changing the limits: when $x=0, u=1$; when $x=\\pi, u=-1$.",
                        math: ["du = -\\sin(x)dx", "x=0 \\implies u=1", "x=\\pi \\implies u=-1"]
                    },
                    {
                        type: "step",
                        k: 2,
                        title: "Transform Integral",
                        body: "Substitute $u$ and $du$ into the integral. Don't forget to flip the limits due to the negative sign.",
                        math: ["- \\int_{1}^{-1} \\frac{1}{1 + u^2} du = \\int_{-1}^{1} \\frac{1}{1 + u^2} du"]
                    },
                    {
                        type: "step",
                        k: 3,
                        title: "Integration",
                        body: "The integral of $1/(1+u^2)$ is $\\arctan(u)$.",
                        math: ["[ \\arctan(u) ]_{-1}^{1}"]
                    },
                    {
                        type: "final",
                        label: "Final Result",
                        body: "Evaluating the antiderivative at the limits gives the final answer.",
                        math: ["\\arctan(1) - \\arctan(-1) = \\frac{\\pi}{4} - (-\\frac{\\pi}{4}) = \\frac{\\pi}{2}"]
                    },
                    {
                        type: "note",
                        title: "Verification",
                        body: "You can verify this by checking the symmetry of the integrand."
                    }
                ]
            }
        ]
    };

    it("generates a PDF buffer from payload", async () => {
        const html = renderHtmlFromPayload(testPayload);
        expect(html).toContain("Advanced Calculus Solution");
        expect(html).toContain("katex.min.css");
        expect(html).toContain("STEP 1");

        const buffer = await renderPdf({
            html,
            docTitle: testPayload.docTitle,
            footerText: "Integration Techniques Test"
        });

        expect(buffer).toBeDefined();
        expect(buffer.length).toBeGreaterThan(1000); // PDF should be at least a few KB

        // Optional: Save to tmp for manual review
        const tmpDir = path.join(process.cwd(), "tmp");
        if (!fs.existsSync(tmpDir)) {
            fs.mkdirSync(tmpDir);
        }
        const testFilePath = path.join(tmpDir, "test_pdf_export.pdf");
        fs.writeFileSync(testFilePath, buffer);
        console.log(`Test PDF saved to: ${testFilePath}`);
    });

    it("handles matrices and complex math in PDF", async () => {
        const matrixPayload: ExportSolutionPayload = {
            docTitle: "Linear Algebra",
            createdAtISO: new Date().toISOString(),
            pages: [{
                pageTitle: "Matrix Ops",
                blocks: [
                    {
                        type: "step",
                        k: 1,
                        title: "Eigenvalues",
                        body: "Find the characteristic polynomial of matrix A.",
                        math: [
                            "A = \\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}",
                            "\\det(A - \\lambda I) = 0"
                        ]
                    }
                ]
            }]
        };

        const html = renderHtmlFromPayload(matrixPayload);
        const buffer = await renderPdf({ html, docTitle: "Matrices" });
        expect(buffer.length).toBeGreaterThan(500);
    });
});
