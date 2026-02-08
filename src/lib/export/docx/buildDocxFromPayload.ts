// lib/export/docx/buildDocxFromPayload.ts
import {
    Document, Paragraph, TextRun, HeadingLevel,
    Table, TableRow, TableCell,
    WidthType, BorderStyle, ShadingType, AlignmentType,
    PageBreak, ImageRun
} from "docx";
import type { ExportSolutionPayload } from "./validate";
import { latexToPng } from "./latexToPng";

const BORDER = {
    top: { style: BorderStyle.SINGLE, size: 6, color: "E5E8EE" },
    bottom: { style: BorderStyle.SINGLE, size: 6, color: "E5E8EE" },
    left: { style: BorderStyle.SINGLE, size: 6, color: "E5E8EE" },
    right: { style: BorderStyle.SINGLE, size: 6, color: "E5E8EE" },
};

function card(children: Paragraph[], fill?: string) {
    return new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows: [
            new TableRow({
                children: [
                    new TableCell({
                        margins: { top: 200, bottom: 200, left: 280, right: 280 },
                        shading: fill ? { type: ShadingType.CLEAR, fill, color: "auto" } : undefined,
                        borders: BORDER,
                        children,
                    }),
                ],
            }),
        ],
    });
}

function stepHeader(k: number, title: string) {
    return new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows: [
            new TableRow({
                children: [
                    new TableCell({
                        width: { size: 16, type: WidthType.PERCENTAGE },
                        shading: { type: ShadingType.CLEAR, fill: "EAF2FF", color: "auto" },
                        margins: { top: 120, bottom: 120, left: 180, right: 180 },
                        borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
                        children: [
                            new Paragraph({
                                children: [new TextRun({ text: `STEP ${k}`, bold: true })],
                            }),
                        ],
                    }),
                    new TableCell({
                        width: { size: 84, type: WidthType.PERCENTAGE },
                        margins: { top: 120, bottom: 120, left: 180, right: 180 },
                        borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
                        children: [
                            new Paragraph({
                                children: [new TextRun({ text: title, bold: true })],
                            }),
                        ],
                    }),
                ],
            }),
        ],
    });
}

function spacer(lines = 1) {
    return new Paragraph({ children: [new TextRun({ text: "\n".repeat(lines) })] });
}

async function mathParagraphs(math: string[] | undefined): Promise<Paragraph[]> {
    if (!math?.length) return [];
    const out: Paragraph[] = [];
    for (const latex of math) {
        const { png, width, height } = await latexToPng(latex);

        // scale down if too wide (Word page ~ 6.5in usable; approx 900px at 2x)
        const maxW = 760;
        const scale = width > maxW ? maxW / width : 1;
        const w = Math.round(width * scale);
        const h = Math.round(height * scale);

        out.push(
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new ImageRun({ data: png, transformation: { width: w, height: h } } as any)],
            })
        );
    }
    return out;
}

export async function buildDocxFromPayload(payload: ExportSolutionPayload): Promise<Document> {
    const children: any[] = [];

    // Title
    children.push(
        new Paragraph({
            heading: HeadingLevel.TITLE,
            children: [new TextRun({ text: payload.docTitle, bold: true })],
        })
    );

    if (payload.subtitle) {
        children.push(new Paragraph({ children: [new TextRun({ text: payload.subtitle })] }));
    }

    children.push(
        new Paragraph({
            children: [
                new TextRun({ text: `Exported: ${new Date(payload.createdAtISO).toLocaleString()}`, color: "666666" }),
            ],
        })
    );

    children.push(spacer(1));

    for (let p = 0; p < payload.pages.length; p++) {
        const page = payload.pages[p];

        if (p > 0) children.push(new Paragraph({ children: [new PageBreak()] }));

        children.push(
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: page.pageTitle, bold: true })],
            })
        );
        children.push(spacer(1));

        for (const block of page.blocks) {
            if (block.type === "problem") {
                const mathParts = await mathParagraphs(block.math);
                const items = [
                    new Paragraph({ children: [new TextRun({ text: block.title, bold: true })] }),
                    spacer(1),
                    new Paragraph({ children: [new TextRun({ text: block.body })] }),
                    ...mathParts,
                ];

                if (block.assumptions?.length) {
                    items.push(spacer(1));
                    items.push(new Paragraph({ children: [new TextRun({ text: "ASSUMPTIONS:", bold: true, size: 18 })] }));
                    for (const asm of block.assumptions) {
                        items.push(new Paragraph({ children: [new TextRun({ text: `• ${asm}` })] }));
                    }
                }

                children.push(card(items, "F7FAFF"));
                children.push(spacer(1));
            }

            if (block.type === "step") {
                const mathParts = await mathParagraphs(block.math);
                children.push(
                    new Table({
                        width: { size: 100, type: WidthType.PERCENTAGE },
                        rows: [
                            new TableRow({
                                children: [
                                    new TableCell({
                                        borders: BORDER,
                                        margins: { top: 180, bottom: 180, left: 240, right: 240 },
                                        children: [
                                            stepHeader(block.k, block.title),
                                            spacer(1),
                                            new Paragraph({ children: [new TextRun({ text: block.body })] }),
                                            ...mathParts,
                                        ],
                                    }),
                                ],
                            }),
                        ],
                    })
                );
                children.push(spacer(1));
            }

            if (block.type === "mistakes") {
                children.push(
                    card(
                        [
                            new Paragraph({ children: [new TextRun({ text: block.title, bold: true, color: "92400E" })] }),
                            spacer(1),
                            ...block.list.map(m => new Paragraph({ children: [new TextRun({ text: `⚠️ ${m}`, color: "78350F" })] }))
                        ],
                        "FFFBEB"
                    )
                );
                children.push(spacer(1));
            }

            if (block.type === "final") {
                const mathParts = await mathParagraphs(block.math);
                const items = [
                    new Paragraph({
                        children: [
                            new TextRun({ text: block.label || "Final Result", bold: true, color: "1FA971" }),
                        ],
                    }),
                    spacer(1),
                    new Paragraph({
                        children: [new TextRun({ text: block.body, bold: true })],
                    }),
                    ...mathParts,
                ];

                if (block.units || (block.values && block.values.length > 0)) {
                    items.push(spacer(1));
                    const details: Paragraph[] = [];
                    if (block.units) {
                        details.push(new Paragraph({ children: [new TextRun({ text: `UNITS: ${block.units}`, bold: true })] }));
                    }
                    if (block.values) {
                        for (const v of block.values) {
                            details.push(new Paragraph({ children: [new TextRun({ text: `${v.label}: ${v.value}` })] }));
                        }
                    }
                    items.push(...details);
                }

                children.push(card(items, undefined));
                children.push(spacer(1));
            }

            if (block.type === "note") {
                children.push(
                    card(
                        [
                            ...(block.title ? [new Paragraph({ children: [new TextRun({ text: block.title, bold: true })] })] : []),
                            new Paragraph({ children: [new TextRun({ text: block.body })] }),
                        ],
                        "FBFBFC"
                    )
                );
                children.push(spacer(1));
            }
        }
    }

    return new Document({
        sections: [{ children }],
    });
}
