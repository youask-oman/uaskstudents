export const normalizeProseMath = (content: unknown): string => {
    if (!content) return "";
    let text = typeof content === 'string' ? content : JSON.stringify(content);

    // Canonicalize over-escaped math delimiters from persisted JSON/text payloads.
    // Example: "\\(" should become "\(" before segmentation.
    text = text
        .replace(/\\\\\(/g, "\\(")
        .replace(/\\\\\)/g, "\\)")
        .replace(/\\\\\[/g, "\\[")
        .replace(/\\\\\]/g, "\\]");

    // Check if it's a JSON array string ["...", "..."]
    if (text.trim().startsWith("[") && text.trim().endsWith("]")) {
        try {
            const parsed = JSON.parse(text);
            if (Array.isArray(parsed)) {
                text = parsed.join("\n");
            }
        } catch {
            // Not valid JSON array, treat as text
        }
    }

    text = autoFixMath(text);

    // Check if entire content is raw LaTeX (no delimiters but has LaTeX commands)
    if (isRawLatex(text)) {
        return `\\(${text.trim()}\\)`;
    }

    text = convertLatexFences(text);
    text = convertDisplayMath(text);

    const lines = text.split("\n");
    const normalized = lines.map((line) => {
        const n = normalizeInlineDollars(line);
        const fixed = autoFixMath(n);
        return wrapCommonNakedInlineLatex(fixed);
    });
    return normalized.join("\n");
};

const wrapCommonNakedInlineLatex = (line: string): string => {
    let out = String(line || "");

    // Render common naked inline commands when mixed with prose, e.g.
    // "Final Answer: \boxed{y = x + 1}".
    // Keep this conservative to avoid over-wrapping normal prose.
    const patterns = [
        /\\boxed\{[^{}]*\}/g,
        /\\sqrt\{[^{}]*\}/g,
        /\\frac\{[^{}]*\}\{[^{}]*\}/g,
        /\\tfrac\{[^{}]*\}\{[^{}]*\}/g,
    ];

    for (const pattern of patterns) {
        out = out.replace(pattern, (match, offset, src) => {
            const start = Number(offset);
            const before = start > 0 ? src[start - 1] : "";
            const afterIndex = start + String(match).length;
            const after = afterIndex < src.length ? src[afterIndex] : "";

            // Skip if already inside inline/block delimiters.
            if (before === "$" || after === "$") return match;
            if (src.slice(Math.max(0, start - 2), start) === "\\(") return match;
            if (src.slice(afterIndex, afterIndex + 2) === "\\)") return match;
            if (src.slice(Math.max(0, start - 2), start) === "\\[") return match;
            if (src.slice(afterIndex, afterIndex + 2) === "\\]") return match;

            return `\\(${match}\\)`;
        });
    }

    return out;
};

// Automatically prepend backslashes to known math commands if missing
export const autoFixMath = (text: string): string => {
    if (!text) return text;
    // Common terms that should be math commands if they look like standalone words or prefixes
    const commands = [
        "frac", "tfrac", "sqrt", "sin", "cos", "tan", "log", "ln", "pm", "mp", "le", "ge", "leq", "geq", "neq", "approx", "alpha", "beta", "gamma", "delta", "theta", "pi", "infty", "begin", "end", "times", "div", "cdot", "hat", "bar", "tilde", "vec",
        "sigma", "mu", "lambda", "phi", "psi", "omega", "tau", "zeta", "eta", "epsilon", "rho", "chi", "nu", "kappa", "Xi", "Gamma", "Delta", "Theta", "Lambda", "Sigma", "Phi", "Psi", "Omega"
    ];

    // Sort by length descending to match longest commands first
    commands.sort((a, b) => b.length - a.length);

    let repaired = text;
    commands.forEach(cmd => {
        // Matches "sqrt" but not "\sqrt" and not "sqrtx" (must be standalone command)
        const regex = new RegExp(`(?<![\\\\a-zA-Z])${cmd}(?![a-zA-Z])`, "g");
        repaired = repaired.replace(regex, `\\${cmd}`);
    });

    // Handle common non-standard parentheses for square roots (e.g. \sqrt(x) -> \sqrt{x})
    repaired = repaired.replace(/\\sqrt\(([^)]+)\)/g, "\\sqrt{$1}");

    // Handle non-standard \root variations
    repaired = repaired.replace(/\\root\s*\{?([^}\s]+)\}?\s*\\of\s*\{([^}]+)\}/g, "\\sqrt[$1]{$2}");
    repaired = repaired.replace(/\\root\s*\{([^}]+)\}\s*\{([^}]+)\}/g, "\\sqrt[$1]{$2}");
    repaired = repaired.replace(/\\root\s+([0-9a-z]+)\s+\{([^}]+)\}/g, "\\sqrt[$1]{$2}");

    // Surgical Fix for left/right
    repaired = repaired.replace(/(?<![\\a-zA-Z])left([(\[{])/g, "\\left$1");
    repaired = repaired.replace(/(?<![\\a-zA-Z])right([)\]}])/g, "\\right$1");

    return repaired;
};

// Detect if content is raw LaTeX without delimiters
const isRawLatex = (text: string): boolean => {
    const trimmed = text.trim();
    if (trimmed.startsWith("\\(") || trimmed.startsWith("\\[") ||
        trimmed.startsWith("$") || trimmed.startsWith("$$")) {
        return false;
    }

    const spaceCount = (trimmed.match(/\s+/g) || []).length;
    const isJsonArray = trimmed.startsWith("[");
    const startsWithText = trimmed.startsWith("\\text{");

    if (spaceCount > 0 && !isJsonArray && !startsWithText) return false;

    const strictLatexPattern = /\\(frac|tfrac|sqrt|root|sum|int|lim|sin|cos|tan|log|ln|alpha|beta|gamma|delta|theta|pi|infty|cdot|times|div|pm|mp|le|ge|leq|geq|neq|approx|equiv|subset|supset|notin|forall|exists|partial|nabla|left|right|begin|end|to|Rightarrow|rightarrow|leftrightarrow|in|sigma|mu|lambda)(?![a-zA-Z])/;
    const permissiveLatexPattern = /(?<![a-zA-Z])(Rightarrow|rightarrow|leftrightarrow|neq|approx|equiv)(?![a-zA-Z])/;

    return strictLatexPattern.test(trimmed) || permissiveLatexPattern.test(trimmed);
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
        const lastDollar = dollarIndexes[dollarIndexes.length - 1];
        const escapedLine = `${line.slice(0, lastDollar)}\\$${line.slice(lastDollar + 1)}`;
        return normalizeInlineDollars(escapedLine);
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

const isSafeInlinePair = (inner: string) => {
    const trimmed = inner.trim();
    if (!trimmed) return false;
    let cleanValue = trimmed;
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
        try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) cleanValue = parsed.join(" \\\\ ");
        } catch { }
    }
    if (/^[\d.,]+$/.test(cleanValue)) return false;
    if (/\\[a-zA-Z]+/.test(cleanValue)) return true;
    if (/[=+\-*/^_<>]/.test(cleanValue)) return true;
    if (/\\begin\{/.test(cleanValue)) return true;
    if (/^[a-zA-Z]$/.test(cleanValue)) return true;
    return false;
};
