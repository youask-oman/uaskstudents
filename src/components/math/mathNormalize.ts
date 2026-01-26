export const normalizeProseMath = (content: any): string => {
    if (!content) return "";
    let text = typeof content === 'string' ? content : JSON.stringify(content);

    // Check if it's a JSON array string ["...", "..."]
    if (text.trim().startsWith("[") && text.trim().endsWith("]")) {
        try {
            const parsed = JSON.parse(text);
            if (Array.isArray(parsed)) {
                text = parsed.join("\n");
            }
        } catch (e) {
            // Not valid JSON array, treat as text
        }
    }

    // Check if entire content is raw LaTeX (no delimiters but has LaTeX commands)
    if (isRawLatex(text)) {
        return `\\(${text.trim()}\\)`;
    }

    text = convertLatexFences(text);
    text = convertDisplayMath(text);

    const lines = text.split("\n");
    const normalized = lines.map((line) => {
        const n = normalizeInlineDollars(line);
        return autoFixMath(n);
    });
    return normalized.join("\n");
};

// Automatically prepend backslashes to known math commands if missing
export const autoFixMath = (text: string): string => {
    if (!text) return text;
    // Common terms that should be math commands if they look like standalone words or prefixes
    let commands = ["frac", "tfrac", "sqrt", "sin", "cos", "tan", "log", "ln", "pm", "mp", "le", "ge", "leq", "geq", "neq", "approx", "alpha", "beta", "gamma", "delta", "theta", "pi", "infty", "left", "right", "begin", "end", "times", "div", "cdot"];

    // Sort by length descending to match longest commands first
    commands.sort((a, b) => b.length - a.length);

    let repaired = text;
    commands.forEach(cmd => {
        // Matches "sqrt" but not "\sqrt"
        // Lookbehind: Not preceded by \ or a letter.
        // We now allow characters to follow (e.g., sqrtx)
        const regex = new RegExp(`(?<![\\\\a-zA-Z])${cmd}`, "g");
        repaired = repaired.replace(regex, `\\${cmd}`);
    });

    // Handle common non-standard parentheses for square roots (e.g. \sqrt(x) -> \sqrt{x})
    repaired = repaired.replace(/\\sqrt\(([^)]+)\)/g, "\\sqrt{$1}");

    return repaired;
};

// Detect if content is raw LaTeX without delimiters
const isRawLatex = (text: string): boolean => {
    const trimmed = text.trim();
    // Skip if already has delimiters
    if (trimmed.startsWith("\\(") || trimmed.startsWith("\\[") ||
        trimmed.startsWith("$") || trimmed.startsWith("$$")) {
        return false;
    }

    // Heuristic: If it has more than 3 spaces, it's likely prose and should NOT be wrapped 
    // entirely in math mode (prevents the "italics prose" bug).
    // EXCEPTIONS:
    // 1. Strings starting with \text{ (likely AI-generated session titles)
    // 2. Strings containing a backslash (likely intended as LaTeX)
    // 3. JSON arrays (common for multi-step math blocks)
    const spaceCount = (trimmed.match(/\s+/g) || []).length;
    const hasBackslash = trimmed.includes("\\");
    const isJsonArray = trimmed.startsWith("[");
    const startsWithText = trimmed.startsWith("\\text{");

    if (spaceCount > 3 && !isJsonArray && !hasBackslash && !startsWithText) return false;

    // Check for common LaTeX commands, permitting missing backslashes for common math terms
    const latexCommandPattern = /\\?(frac|tfrac|sqrt|sum|int|lim|sin|cos|tan|log|ln|alpha|beta|gamma|delta|theta|pi|infty|cdot|times|div|pm|mp|le|ge|leq|geq|neq|approx|equiv|subset|supset|in|notin|forall|exists|partial|nabla|left|right|begin|end|to|Rightarrow|rightarrow|leftrightarrow)(?![a-zA-Z])/;
    return latexCommandPattern.test(trimmed);
};

const isEscaped = (text: string, index: number) => {
    let backslashes = 0;
    let cursor = index - 1;
    while (cursor >= 0 && text[cursor] === "\\") {
        backslashes += 1;
        cursor -= 1;
    }
    return backslashes % 2 === 1;
};

const findDelimiter = (text: string, delimiter: string, fromIndex: number) => {
    let location = text.indexOf(delimiter, fromIndex);
    while (location !== -1) {
        if (!isEscaped(text, location)) return location;
        location = text.indexOf(delimiter, location + 1);
    }
    return -1;
};

const convertLatexFences = (text: string) => {
    return text.replace(/```(?:latex|tex)\s*([\s\S]*?)```/g, (_match, inner) => {
        const trimmed = String(inner || "").trim();
        if (!trimmed) return "";
        return `\\[\n${trimmed}\n\\]`;
    });
};

const convertDisplayMath = (text: string) => {
    let cursor = 0;
    let output = "";

    while (cursor < text.length) {
        const start = findDelimiter(text, "$$", cursor);
        if (start === -1) {
            output += text.slice(cursor);
            break;
        }

        output += text.slice(cursor, start);
        const closing = findDelimiter(text, "$$", start + 2);
        if (closing === -1) {
            output += "\\$\\$";
            cursor = start + 2;
            continue;
        }

        const block = text.slice(start + 2, closing);
        output += `\\[\n${block}\n\\]`;
        cursor = closing + 2;
    }

    return output;
};

const normalizeInlineDollars = (line: string) => {
    const dollarIndexes: number[] = [];
    for (let i = 0; i < line.length; i += 1) {
        if (line[i] === "$" && !isEscaped(line, i)) {
            dollarIndexes.push(i);
        }
    }

    if (dollarIndexes.length === 0) return line;
    if (dollarIndexes.length % 2 === 1) {
        return escapeAllDollars(line);
    }

    let output = "";
    let cursor = 0;
    for (let i = 0; i < dollarIndexes.length; i += 2) {
        const start = dollarIndexes[i];
        const end = dollarIndexes[i + 1];
        output += line.slice(cursor, start);

        const inner = line.slice(start + 1, end);
        if (isSafeInlinePair(inner)) {
            output += `\\(${inner.trim()}\\)`;
        } else {
            output += `\\$${inner}\\$`;
        }
        cursor = end + 1;
    }

    output += line.slice(cursor);
    return output;
};

const escapeAllDollars = (text: string) => {
    let output = "";
    for (let i = 0; i < text.length; i += 1) {
        const ch = text[i];
        if (ch === "$" && !isEscaped(text, i)) {
            output += "\\$";
        } else {
            output += ch;
        }
    }
    return output;
};

const isSafeInlinePair = (inner: string) => {
    const trimmed = inner.trim();
    if (!trimmed) return false;

    // Double check if value is still an array/object-like string that needs cleaning before render
    let cleanValue = trimmed;
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
        try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) cleanValue = parsed.join(" \\\\ ");
        } catch (e) { }
    }

    if (/^[\d.,]+$/.test(cleanValue)) return false;
    if (/\\[a-zA-Z]+/.test(cleanValue)) return true;
    if (/[=+\-*/^_<>]/.test(cleanValue)) return true;
    if (/\\begin\{/.test(cleanValue)) return true;
    if (/^[a-zA-Z]$/.test(cleanValue)) return true;
    return false;
};
