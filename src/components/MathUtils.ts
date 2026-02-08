
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

    // Surgical Fix for accents: \hat f -> \hat{f}
    clean = clean.replace(/\\(hat|bar|tilde|vec|dot|ddot|check|acute|grave)\s+([a-zA-Z0-9])/g, '\\$1{$2}');

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
                part.toLowerCase().includes("\\begin")
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

const parseGroup = (text: string, start: number, openChar: string, closeChar: string) => {
    let depth = 0;
    let cursor = start;
    while (cursor < text.length) {
        const ch = text[cursor];
        if (ch === openChar) depth += 1;
        if (ch === closeChar) {
            depth -= 1;
            if (depth === 0) {
                return cursor + 1;
            }
        }
        cursor += 1;
    }
    return -1;
};

export function normalizePlainSqrt(text: string): string {
    const sanitized = text.replace(/sqrt\s*([a-zA-Z0-9]+)/g, (match, expr, offset) => {
        if (offset > 0) {
            const prevChar = text[offset - 1];
            if (prevChar === "\\" || /[a-zA-Z0-9]/.test(prevChar)) {
                return match;
            }
        }
        return `\\sqrt{${expr}}`;
    });

    const parts = sanitized.split(/(```[\s\S]*?```|`[^`]*`|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))/g);

    return parts
        .map((part) => {
            if (
                part.startsWith("```") ||
                part.startsWith("`") ||
                part.startsWith("\\[") ||
                part.startsWith("\\(")
            ) {
                return part;
            }

            let output = "";
            let cursor = 0;
            while (cursor < part.length) {
                const match = part.slice(cursor).match(/\bsqrt\s*\(/);
                if (!match || match.index === undefined) {
                    output += part.slice(cursor);
                    break;
                }

                const start = cursor + match.index;
                output += part.slice(cursor, start);

                const openParen = part.indexOf("(", start);
                if (openParen === -1) {
                    output += part.slice(start);
                    break;
                }

                const closeParen = parseGroup(part, openParen, "(", ")");
                if (closeParen === -1) {
                    output += part.slice(start);
                    break;
                }

                const inner = part.slice(openParen + 1, closeParen - 1);
                output += `\\sqrt{${inner}}`;
                cursor = closeParen;
            }

            return output;
        })
        .join("");
}

export function escapeUnmatchedRightDelimiters(text: string): string {
    let leftStack = 0;
    return text.replace(/\\(left|right)/g, (match, direction) => {
        if (direction === "left") {
            leftStack += 1;
            return match;
        }
        if (direction === "right") {
            if (leftStack > 0) {
                leftStack -= 1;
                return match;
            }
            return `\\text{\\char92${direction}}`;
        }
        return match;
    });
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

