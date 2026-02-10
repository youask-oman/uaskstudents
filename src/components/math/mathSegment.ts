/**
 * MathSegment types
 */
export type MathSegment =
    | { type: "text"; value: string }
    | { type: "inline_math"; value: string }
    | { type: "block_math"; value: string };

/**
 * Robust Math Text Segmenter
 * 
 * Splits a string into text and math segments while preserving whitespace.
 */
export const segmentMath = (content: string): MathSegment[] => {
    if (!content) return [{ type: "text", value: "" }];

    const segments: MathSegment[] = [];
    let cursor = 0;

    // Commands that essentially require an argument (accents, fractions, etc.)
    // We want to be greedy with these even when they are "naked".
    const needsArgCommands = [
        "hat", "bar", "tilde", "vec", "dot", "ddot", "check", "acute", "grave",
        "sqrt", "frac", "tfrac", "sum", "int", "lim", "root"
    ];

    while (cursor < content.length) {
        // 1. Explicit Delimiters
        const nextInlineWrap = findDelimiter(content, "\\(", cursor);
        const nextBlockWrap = findDelimiter(content, "\\[", cursor);
        const nextDollarWrap = findDelimiter(content, "$", cursor);

        // 2. Naked triggers
        let nakedTrigger = -1;
        let triggerType: "command" | "script" = "command";
        let capturedCmd = "";

        // Check for backslash command
        const bsRegex = /\\([a-zA-Z]+)/g;
        bsRegex.lastIndex = cursor;
        const bsMatch = bsRegex.exec(content);
        if (bsMatch && !isEscaped(content, bsMatch.index)) {
            if (content[bsMatch.index + 1] !== '(' && content[bsMatch.index + 1] !== '[' && content[bsMatch.index + 1] !== '$') {
                nakedTrigger = bsMatch.index;
                triggerType = "command";
                capturedCmd = bsMatch[1];
            }
        }

        // Check for scripts like x^2, S_N
        const scriptRegex = /(?:^|[^a-zA-Z0-9])([a-zA-Z0-9])([_^])/g;
        scriptRegex.lastIndex = cursor;
        const scriptMatch = scriptRegex.exec(content);
        if (scriptMatch && (nakedTrigger === -1 || scriptMatch.index < nakedTrigger)) {
            const charStart = content[scriptMatch.index].match(/[a-zA-Z0-9]/) ? scriptMatch.index : scriptMatch.index + 1;
            if (charStart >= cursor) {
                nakedTrigger = charStart;
                triggerType = "script";
            }
        }

        const next = pickNext(
            nextInlineWrap,
            nextBlockWrap,
            nakedTrigger,
            nextDollarWrap
        );

        if (next.index === -1) {
            segments.push({ type: "text", value: content.slice(cursor) });
            break;
        }

        if (next.index > cursor) {
            segments.push({ type: "text", value: content.slice(cursor, next.index) });
        }

        // 3. Capture Math Block
        if (next.type === "naked_command") {
            const rest = content.slice(next.index);

            // Base pattern: command identifier
            const pattern = triggerType === "command"
                ? `^\\\\${capturedCmd}`
                : `^([a-zA-Z0-9]+)`;

            // Add optional arguments: {}, [], ()
            // And scripts
            const suffix = `(?:\\{[^{}]*\\}|\\[[^[\\]]*\\]|\\([^()]*\\)|[_^](?:\\{[^{}]*\\}|[a-zA-Z0-9]|\\\\[a-zA-Z]+(?:\\{[^{}]*\\}|\\[[^[\\]]*\\]|\\([^()]*\\))*))*`;

            let mathRegex = new RegExp(pattern + suffix);

            // Special handling for commands that NEED an argument following them (like \hat f)
            if (triggerType === "command" && needsArgCommands.includes(capturedCmd)) {
                // Allow a single space + one character or a braced group
                // Pattern: command + optional space + (braced group or single char)
                mathRegex = new RegExp(`^\\\\${capturedCmd}(?:\\s*(?:\\{[^{}]*\\}|[a-zA-Z0-9]))?` + suffix);
            }

            const fullMatch = rest.match(mathRegex);
            const value = fullMatch ? fullMatch[0] : (triggerType === "command" ? bsMatch![0] : scriptMatch![1] + scriptMatch![2]);

            if (isValidMath(value)) {
                segments.push({ type: "inline_math", value });
            } else {
                segments.push({ type: "text", value });
            }
            cursor = next.index + value.length;
            continue;
        }

        const delimPair = getDelimiters(next.type, content, next.index);
        const closeIndex = findDelimiter(content, delimPair.close, next.index + delimPair.open.length);

        if (closeIndex === -1) {
            segments.push({ type: "text", value: delimPair.open });
            cursor = next.index + delimPair.open.length;
            continue;
        }

        const blockValue = content.slice(next.index + delimPair.open.length, closeIndex);
        segments.push({
            type: next.type === "block_math" || next.type === "dollar_block" ? "block_math" : "inline_math",
            value: blockValue
        });
        cursor = closeIndex + delimPair.close.length;
    }

    return segments;
};

function isValidMath(tex: string): boolean {
    const trimmed = tex.trim();
    if (!trimmed) return false;

    // Commands that MUST take an argument. If rendered alone, they fail.
    const mustHaveArg = ["\\hat", "\\bar", "\\tilde", "\\vec", "\\sqrt", "\\frac", "\\tfrac", "\\sum", "\\int"];
    if (mustHaveArg.includes(trimmed)) return false;

    if (/[_^]$/.test(trimmed)) return false;

    let depth = 0;
    for (let i = 0; i < trimmed.length; i++) {
        const char = trimmed[i];
        if (char === '{' && (i === 0 || trimmed[i - 1] !== '\\')) depth++;
        if (char === '}' && (i === 0 || trimmed[i - 1] !== '\\')) depth--;
        if (depth < 0) return false;
    }
    return depth === 0;
}

const getDelimiters = (type: string, content: string, start: number) => {
    if (type === "inline_math") return { open: "\\(", close: "\\)" };
    if (type === "block_math") return { open: "\\[", close: "\\]" };
    if (type === "dollar_block") {
        if (content.startsWith("$$", start)) return { open: "$$", close: "$$" };
        return { open: "$", close: "$" };
    }
    return { open: "", close: "" };
};

const pickNext = (inline: number, block: number, naked: number, dollar: number) => {
    let best = { index: -1, type: "text" as "text" | "inline_math" | "block_math" | "naked_command" | "dollar_block" };

    const update = (idx: number, type: "inline_math" | "block_math" | "naked_command" | "dollar_block") => {
        if (idx !== -1 && (best.index === -1 || idx < best.index)) {
            best = { index: idx, type };
        }
    };

    update(inline, "inline_math");
    update(block, "block_math");
    update(naked, "naked_command");
    update(dollar, "dollar_block");

    return best;
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
