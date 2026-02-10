
import { buildDocxFromPayload } from "../src/lib/export/docx/buildDocxFromPayload";
import { docxToBuffer } from "../src/lib/export/docx/docxToBuffer";
import { writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import type { ExportSolutionPayload } from "../src/lib/export/docx/validate";

// Ensure tmp directory exists
const tmpDir = join(process.cwd(), "tmp");
if (!existsSync(tmpDir)) {
    mkdirSync(tmpDir);
}

const run = async () => {
    console.log("Generating sample 1: Matrix Inversion...");
    const sample1 = {
        docTitle: "Linear Algebra: Matrix Inversion",
        subtitle: "Using Gaussian Elimination",
        createdAtISO: new Date().toISOString(),
        pages: [{
            pageTitle: "Problem & Solution",
            blocks: [
                {
                    type: "problem",
                    title: "Invert Matrix A",
                    body: "Find the inverse of the following matrix:",
                    math: ["A = \\begin{pmatrix} 1 & 2 & 3 \\\\ 0 & 1 & 4 \\\\ 5 & 6 & 0 \\end{pmatrix}"]
                },
                {
                    type: "step",
                    k: 1,
                    title: "Augment with Identity",
                    body: "Form the augmented matrix [A | I]:",
                    math: ["\\left(\\begin{array}{ccc|ccc} 1 & 2 & 3 & 1 & 0 & 0 \\\\ 0 & 1 & 4 & 0 & 1 & 0 \\\\ 5 & 6 & 0 & 0 & 0 & 1 \\end{array}\\right)"]
                },
                {
                    type: "step",
                    k: 2,
                    title: "Row Operations",
                    body: "Subtract 5 * R1 from R3:",
                    math: ["\\left(\\begin{array}{ccc|ccc} 1 & 2 & 3 & 1 & 0 & 0 \\\\ 0 & 1 & 4 & 0 & 1 & 0 \\\\ 0 & -4 & -15 & -5 & 0 & 1 \\end{array}\\right)"]
                },
                {
                    type: "final",
                    label: "Resulting Inverse",
                    body: "The inverse matrix is:",
                    math: ["A^{-1} = \\begin{pmatrix} -24 & 18 & 5 \\\\ 20 & -15 & -4 \\\\ -5 & 4 & 1 \\end{pmatrix}"]
                }
            ]
        }]
    };

    const doc1 = await buildDocxFromPayload(sample1 as ExportSolutionPayload);
    const buf1 = await docxToBuffer(doc1);
    writeFileSync(join(tmpDir, "sample_1_matrix.docx"), buf1);
    console.log("Saved tmp/sample_1_matrix.docx");

    console.log("Generating sample 2: Calculus Integral...");
    const sample2 = {
        docTitle: "Calculus: Definite Integral",
        createdAtISO: new Date().toISOString(),
        pages: [{
            pageTitle: "Integration by Parts",
            blocks: [
                {
                    type: "problem",
                    title: "Evaluate Integral",
                    body: "Calculate the following definite integral:",
                    math: ["\\int_0^{\\pi} x \\sin(x) \\, dx"]
                },
                {
                    type: "step",
                    k: 1,
                    title: "Setup Parts",
                    body: "Let u = x and dv = sin(x) dx. Then:",
                    math: ["du = dx, \\quad v = -\\cos(x)"]
                },
                {
                    type: "step",
                    k: 2,
                    title: "Apply Formula",
                    body: "Using integration by parts formula:",
                    math: ["\\int u \\, dv = uv - \\int v \\, du", "= -x\\cos(x)\\Big|_0^{\\pi} - \\int_0^{\\pi} (-\\cos(x)) \\, dx"]
                },
                {
                    type: "final",
                    label: "Computed Value",
                    body: "The value is:",
                    math: ["\\pi"]
                }
            ]
        }]
    };

    const doc2 = await buildDocxFromPayload(sample2 as ExportSolutionPayload);
    const buf2 = await docxToBuffer(doc2);
    writeFileSync(join(tmpDir, "sample_2_calculus.docx"), buf2);
    console.log("Saved tmp/sample_2_calculus.docx");
};

run().catch(console.error);
