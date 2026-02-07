import katex from "katex";
import type { ExportSolutionPayload } from "../docx/validate";

export function renderHtmlFromPayload(payload: ExportSolutionPayload): string {
    const renderMath = (latex: string) => {
        try {
            return katex.renderToString(latex, {
                throwOnError: false,
                displayMode: true,
            });
        } catch (err) {
            console.error("KaTeX error:", err);
            return `<pre class="math-error">${latex}</pre>`;
        }
    };

    const renderMathInline = (latex: string) => {
        try {
            return katex.renderToString(latex, {
                throwOnError: false,
                displayMode: false,
            });
        } catch (err) {
            console.error("KaTeX error:", err);
            return `<span class="math-error">${latex}</span>`;
        }
    };

    // Helper to process body text for potential inline math (simple check)
    const formatBody = (text: string) => {
        // This is a simple implementation. For production, you might want a more robust LaTeX parser/renderer.
        // If the body contains $...$, we could try to replace it.
        // For now, we'll just return the text and rely on the 'math' array in the payload for blocks.
        return text.split("\n").map(line => `<p>${line}</p>`).join("");
    };

    const renderBlocks = (blocks: ExportSolutionPayload["pages"][0]["blocks"]) => {
        return blocks.map(block => {
            let content = "";
            let mathContent = "";

            if (block.type === "problem") {
                mathContent = block.math?.map(renderMath).join("") || "";
                content = `
                    <div class="card problem-card">
                        <div class="card-title">${block.title}</div>
                        <div class="card-body">${formatBody(block.body)}</div>
                        <div class="math-blocks">${mathContent}</div>
                    </div>
                `;
            } else if (block.type === "step") {
                mathContent = block.math?.map(renderMath).join("") || "";
                content = `
                    <div class="card step-card">
                        <div class="step-header">
                            <div class="step-badge">STEP ${block.k}</div>
                            <div class="step-title">${block.title}</div>
                        </div>
                        <div class="card-body">${formatBody(block.body)}</div>
                        <div class="math-blocks">${mathContent}</div>
                    </div>
                `;
            } else if (block.type === "final") {
                mathContent = block.math?.map(renderMath).join("") || "";
                content = `
                    <div class="card final-card">
                        <div class="card-title">${block.label || "Final Answer"}</div>
                        <div class="card-body bold">${formatBody(block.body)}</div>
                        <div class="math-blocks">${mathContent}</div>
                    </div>
                `;
            } else if (block.type === "note") {
                content = `
                    <div class="card note-card">
                        ${block.title ? `<div class="card-title">${block.title}</div>` : ""}
                        <div class="card-body italic">${formatBody(block.body)}</div>
                    </div>
                `;
            }

            return content;
        }).join("");
    };

    const pages = payload.pages.map((page, index) => `
        <div class="page" id="page-${index + 1}">
            <h1 class="page-title">${page.pageTitle}</h1>
            ${renderBlocks(page.blocks)}
        </div>
    `).join("");

    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${payload.docTitle}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1e40af;
            --primary-light: #eff6ff;
            --success: #10b981;
            --success-dark: #059669;
            --success-light: #ecfdf5;
            --border: #e5e7eb;
            --text-main: #111827;
            --text-muted: #4b5563;
            --bg-page: #ffffff;
            --bg-card: #ffffff;
            --bg-note: #f9fafb;
            --bg-problem: #f8faff;
        }

        @page {
            margin: 1.5cm;
            size: A4;
        }

        * {
            box-sizing: border-box;
            -webkit-print-color-adjust: exact;
        }

        body {
            font-family: 'Inter', -apple-system, system-ui, sans-serif;
            color: var(--text-main);
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background: var(--bg-page);
        }

        h1, h2, h3, .step-title, .card-title {
            font-family: 'Outfit', sans-serif;
            margin: 0;
            letter-spacing: -0.01em;
        }

        .header {
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
        }

        .doc-title {
            font-size: 28pt;
            font-weight: 800;
            color: var(--primary-dark);
            margin-bottom: 0.25rem;
            line-height: 1.2;
        }

        .doc-subtitle {
            font-size: 13pt;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            font-weight: 500;
        }

        .doc-meta {
            font-size: 9pt;
            color: #9ca3af;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .page {
            page-break-after: always;
        }

        .page:last-child {
            page-break-after: auto;
        }

        .page-title {
            font-size: 18pt;
            margin-bottom: 1.5rem;
            color: var(--text-main);
            border-left: 5px solid var(--primary);
            padding-left: 1.25rem;
            font-weight: 700;
        }

        .card {
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.75rem;
            margin-bottom: 2rem;
            background: var(--bg-card);
            page-break-inside: avoid;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }

        .problem-card {
            background-color: var(--bg-problem);
            border-color: #dee9fc;
        }

        .final-card {
            background: linear-gradient(135deg, var(--success), var(--success-dark));
            color: white;
            border: none;
            box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.2);
        }

        .final-card .card-title, .final-card .card-body {
            color: white;
        }

        .note-card {
            background-color: var(--bg-note);
            border-style: dashed;
            border-color: #d1d5db;
        }

        .card-title {
            font-size: 14pt;
            font-weight: 700;
            margin-bottom: 1rem;
            color: var(--text-main);
        }

        .final-card .card-title {
            color: white;
            font-size: 16pt;
        }

        .card-body {
            font-size: 11.5pt;
        }

        .card-body p {
            margin: 0 0 0.75rem 0;
        }

        .card-body p:last-child {
            margin-bottom: 0;
        }

        .bold { font-weight: 700; }
        .italic { font-style: italic; color: var(--text-muted); }

        .step-card {
            padding: 0;
            overflow: hidden;
            border-color: var(--border);
        }

        .step-header {
            display: flex;
            align-items: center;
            background: linear-gradient(to right, var(--primary-light), white);
            border-bottom: 1px solid var(--border);
            padding: 1rem 1.75rem;
        }

        .step-badge {
            background: var(--primary);
            color: white;
            padding: 0.35rem 0.85rem;
            border-radius: 8px;
            font-weight: 800;
            font-size: 8.5pt;
            margin-right: 1.25rem;
            text-transform: uppercase;
            letter-spacing: 0.075em;
            box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
        }

        .step-title {
            font-size: 13.5pt;
            font-weight: 700;
            color: var(--primary-dark);
        }

        .step-card .card-body, .step-card .math-blocks {
            padding: 1.75rem;
        }

        .math-blocks {
            margin-top: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            align-items: center;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 12px;
        }

        .math-error {
            color: #dc2626;
            background: #fee2e2;
            padding: 0.75rem;
            border-radius: 6px;
            font-family: monospace;
            font-size: 9pt;
            border: 1px solid #fecaca;
        }

        /* Pagination & Headers/Footers are handled by Playwright */
    </style>
</head>
<body>
    <div class="header">
        <div class="doc-title">${payload.docTitle}</div>
        ${payload.subtitle ? `<div class="doc-subtitle">${payload.subtitle}</div>` : ""}
        <div class="doc-meta">Exported: ${new Date(payload.createdAtISO).toLocaleString()}</div>
    </div>
    
    <main>
        ${pages}
    </main>
</body>
</html>
    `;
}
