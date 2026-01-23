
// =============================================================================
// MATH PREPROCESSING UTILS
// Extracted from MathRenderer.tsx for testing and isolation
// =============================================================================

/**
 * Fix A: Convert fenced ```latex or ```tex code blocks into \[...\]
 * We use \[...\] for block math now, not $$
 */
export function convertLatexFencesToMath(md: string): string {
    return md.replace(/```(?:latex|tex)\s*\n([\s\S]*?)```/gi, (_, body) => {
        const inner = String(body).trim();
        return `\\[\n${inner}\n\\]`;
    });
}

/**
 * Sanitize common LaTeX artifacts from LLM output
 */
export function sanitizeLatex(input: string): string {
    let clean = input;

    // Fix .textLine patterns
    clean = clean.split('.textLine :').join('. \\text{Line: }');
    clean = clean.split('.textLine:').join('. \\text{Line: }');
    clean = clean.split(').textLine :').join('). \\text{Line: }');
    clean = clean.split(').textLine:').join('). \\text{Line: }');
    clean = clean.split('textLine: ').join('\\text{Line: } ');
    clean = clean.split('textLine:').join('\\text{Line: } ');
    clean = clean.split('textPlot: ').join('\\text{Plot: } ');
    clean = clean.split('textPlot:').join('\\text{Plot: } ');
    clean = clean.split('textOtherpoints:').join('\\text{Other points } ');
    clean = clean.split('textOtherpoints').join('\\text{Other points } ');
    clean = clean.split('textPlotdomainsuggestion').join('\\text{Plot domain suggestion }');
    clean = clean.split('textThus').join('\\text{Thus ');

    // Fix textParabola patterns
    clean = clean.split('.textParabola :').join('. \\text{Parabola: }');
    clean = clean.split('.textParabola:').join('. \\text{Parabola: }');

    // Fix double-escaped backslashes
    clean = clean.split('\\\\text').join('\\text');
    clean = clean.split('\\\\quad').join('\\quad');

    // Fix :; artifact
    clean = clean.split(':;').join(':');

    // Fix missing backslash in text{...}
    clean = clean.replace(/(^|[^\\])text\{/g, '$1\\text{');

    // AGGRESSIVE: Remove malformed $\X$ patterns (single char math that's broken)
    // e.g., "$\f$" => "" or "$\" => ""
    clean = clean.replace(/\$\\[a-zA-Z]?\$/g, '');

    // Remove stray $ followed immediately by backslash and letter (like "$\f'")
    clean = clean.replace(/\$\\([a-zA-Z])/g, '\\$1');

    // Remove trailing $ at end of line/string that's unmatched
    clean = clean.replace(/([^$])\$$/gm, '$1');

    // Remove $ immediately before = or ) when not matched
    clean = clean.replace(/\$([=)])/g, '$1');

    // Fix \big ( with space
    clean = clean.replace(/\\big\s+([([{|\\])/g, '\\big$1');

    return clean;
}

/**
 * Auto-wrap LaTeX environments in \[...\] if they are bare in prose.
 */
export function autoWrapEnvironments(input: string): string {
    if (!input) return "";
    // Split by protected regions
    const parts = input.split(/(```[\s\S]*?```|`[^`]*`|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))/g);
    return parts.map(part => {
        if (!part) return "";
        if (part.startsWith('```') || part.startsWith('`') || part.startsWith('\\[') || part.startsWith('\\(')) return part;

        // In prose parts, find \begin pairs and wrap them
        return part.replace(/\\begin\{([a-z*]+)\}([\s\S]*?)\\end\{\1\}/gi, (match) => {
            return `\\[${match}\\]`;
        });
    }).join('');
}

/**
 * Normalize LaTeX breaks and commands outside math regions
 * Converts \\ to paragraph breaks, \text{...} to plain text, etc.
 */
export function normalizeLatexBreaksOutsideMath(input: string): string {
    // Split by protected regions: code fences, inline code, strict block math, strict inline math, and bare begin/end envs
    const parts = input.split(/(```[\s\S]*?```|`[^`]*`|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\\begin\{[a-z*]+\}[\s\S]*?\\end\{[a-z*]+\})/gi);

    return parts
        .map((part) => {
            if (!part) return "";
            // Keep protected parts as-is
            if (
                part.startsWith("```") ||
                part.startsWith("`") ||
                part.startsWith("\\[") ||
                part.startsWith("\\(") ||
                part.toLowerCase().startsWith("\\begin")
            ) return part;

            // Outside math:
            let s = part;

            // 1) Treat LaTeX linebreaks as paragraph breaks in Markdown
            s = s.replace(/\\\\/g, "\n\n");

            // 2) If model uses \text{Label: } outside math, convert to plain text label
            s = s.replace(/\\text\{([^}]*)\}/g, "$1");

            // 3) Common stray spacing commands outside math
            s = s.replace(/\\quad/g, " ");
            s = s.replace(/\\,/g, " ");
            s = s.replace(/\\ /g, " ");

            // 4) Stray arrows outside math
            s = s.replace(/\\Rightarrow/g, "⇒");
            s = s.replace(/\\Leftarrow/g, "⇐");
            s = s.replace(/\\rightarrow/g, "→");
            s = s.replace(/\\leftarrow/g, "←");

            return s;
        })
        .join("");
}

/**
 * Fix C & D: Normalize unsupported macros and wrap prose in \text{}
 * Converts \blue{...} -> \textcolor{blue}{...}
 * Wraps prose in \text{...} so spaces are preserved.
 */
export function normalizeAndFixColors(text: string): string {
    let clean = text;
    const colors = ['blue', 'red', 'green', 'orange', 'purple', 'teal', 'violet', 'emerald', 'gray'];
    colors.forEach(color => {
        const regex = new RegExp(`\\\\${color}\\{([^{}]*)\\}`, 'g');
        clean = clean.replace(regex, `\\textcolor{${color}}{$1}`);
    });

    clean = clean.replace(
        /\\textcolor\{([a-zA-Z]+)\}\{([^{}]+)\}/g,
        (match, color, content) => {
            const trimmed = content.trim();
            const hasSpaces = trimmed.includes(' ');
            const hasMathCmd = /\\[a-zA-Z]+/.test(trimmed);

            if (hasSpaces && !hasMathCmd) {
                return `\\textcolor{${color}}{\\text{${content}}}`;
            }
            return match;
        }
    );

    return clean;
}

/**
 * Fix A: Escape ALL unescaped dollar signs ($) in prose.
 * Protects code blocks.
 * This completely disables $ as a math delimiter.
 */
export function escapeAllDollars(input: string): string {
    // Helper to process text outside code blocks
    const parts = input.split(/(```[\s\S]*?```|`[^`]*`)/g);
    return parts.map(part => {
        // Return code blocks as-is
        if (part.startsWith('```') || part.startsWith('`')) return part;
        // Escape unescaped dollars
        return part.replace(/(?<!\\)\$/g, '\\$');
    }).join('');
}

/**
 * Convert Strict Delimiters \( ... \) and \[ ... \] to Library Format
 * remark-math expects $ ... $ and $$ ... $$
 * We perform this conversion LAST, just before rendering.
 */
export function convertStrictToLibFormat(input: string): string {
    const parts = input.split(/(```[\s\S]*?```|`[^`]*`)/g);
    return parts.map(part => {
        if (part.startsWith('```') || part.startsWith('`')) return part;

        let s = part.replace(/\\\[([\s\S]*?)\\\]/g, '$$$$$1$$$$');
        s = s.replace(/\\\(([\s\S]*?)\\\)/g, '$$$1$$');

        return s;
    }).join('');
}

export function splitSolutionIntoLines(input: string) {
    if (!input) return [];
    return input
        .split(/\\\\|\r?\n/)
        .map(line => line.trim())
        .filter(Boolean);
}

/** 
 * AutoWrap Latex Environments (Legacy/Helper)
 * Included if needed, but currently unused/disabled in MathRenderer.
 * Keeping it here if we need it back, or omitting.
 * Omitted to keep clean.
 */

