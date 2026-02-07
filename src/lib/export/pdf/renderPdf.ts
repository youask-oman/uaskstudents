import { chromium } from "playwright";

export type RenderPdfOptions = {
    html: string;
    docTitle: string;
    footerText?: string;
};

export async function renderPdf(options: RenderPdfOptions): Promise<Buffer> {
    const { html, docTitle, footerText } = options;

    const browser = await chromium.launch({
        headless: true,
        args: ["--no-sandbox", "--disable-setuid-sandbox"]
    });

    try {
        const page = await browser.newPage();

        // Wait until network is idle to ensure Google Fonts and KaTeX CDN CSS are loaded
        await page.setContent(html, { waitUntil: "networkidle" });

        const headerTemplate = `
            <div style="font-size: 8px; width: 100%; text-align: right; padding-right: 1.5cm; color: #999; font-family: 'Inter', sans-serif;">
                <span class="title"></span>
            </div>
        `;

        const footerTemplate = `
            <div style="font-size: 8px; width: 100%; display: flex; justify-content: space-between; padding: 0 1.5cm; color: #999; font-family: 'Inter', sans-serif;">
                <div>${footerText || ""}</div>
                <div>Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>
            </div>
        `;

        const pdfBuffer = await page.pdf({
            format: "A4",
            printBackground: true,
            displayHeaderFooter: true,
            headerTemplate,
            footerTemplate,
            margin: {
                top: "1.5cm",
                bottom: "1.5cm",
                left: "1.5cm",
                right: "1.5cm"
            },
        });

        return pdfBuffer;
    } finally {
        await browser.close();
    }
}
