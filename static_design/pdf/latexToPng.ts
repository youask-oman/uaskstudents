// lib/export/docx/latexToPng.ts
import { chromium } from "playwright";

type PngResult = { png: Buffer; width: number; height: number };

const HTML = (latex: string) => `
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css">
  <style>
    body { margin: 0; padding: 0; background: white; }
    .wrap { display: inline-block; padding: 16px 18px; }
  </style>
</head>
<body>
  <div class="wrap" id="root"></div>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js"></script>
  <script>
    const latex = ${JSON.stringify(latex)};
    const root = document.getElementById("root");
    try {
      katex.render(latex, root, { throwOnError: false, displayMode: true });
    } catch (e) {
      root.innerText = latex;
    }
  </script>
</body>
</html>
`;

export async function latexToPng(latex: string): Promise<PngResult> {
    const browser = await chromium.launch();
    try {
        const page = await browser.newPage({ deviceScaleFactor: 2 });
        await page.setContent(HTML(latex), { waitUntil: "load" });

        const el = await page.$("#root");
        if (!el) throw new Error("KaTeX root not found");

        const box = await el.boundingBox();
        if (!box) throw new Error("No bounding box for KaTeX output");

        // screenshot only the equation
        const png = await el.screenshot({ type: "png" });
        return { png: Buffer.from(png), width: Math.ceil(box.width), height: Math.ceil(box.height) };
    } finally {
        await browser.close();
    }
}
